"""Hybrid relationship detection: rules + embeddings + optional Bedrock reasoning."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from itertools import combinations
from typing import Any

from app.models.entity import Entity
from app.models.market import Market
from app.models.relationship import Relationship, RelationshipType
from app.services.bedrock_client import BedrockClient
from app.services.similarity_service import cosine_similarity, pearson_correlation
from app.utils.logging import get_logger

logger = get_logger(__name__)

_WEIGHT_EMB = 0.30
_WEIGHT_ENT = 0.25
_WEIGHT_TAG = 0.15
_WEIGHT_TIME = 0.10
_WEIGHT_SERIES = 0.10
_WEIGHT_PRICE = 0.10

_LLM_THRESHOLD = 0.55


def _canonical_pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _entity_keys(entities: Iterable[Entity]) -> set[str]:
    keys: set[str] = set()
    for e in entities:
        k = (e.normalized or e.text).strip().lower()
        if k:
            keys.add(k)
    return keys


def _temporal_score(m1: Market, m2: Market) -> float:
    starts = [m1.start_date, m2.start_date]
    ends = [m1.end_date, m2.end_date]
    if not all(isinstance(x, datetime) for x in (*starts, *ends)):
        return 0.3
    s1, e1, s2, e2 = m1.start_date, m1.end_date, m2.start_date, m2.end_date
    assert s1 and e1 and s2 and e2
    overlap_start = max(s1, s2)
    overlap_end = min(e1, e2)
    if overlap_end <= overlap_start:
        return 0.0
    overlap = (overlap_end - overlap_start).days + 1
    span = max((e1 - s1).days + 1, 1) + max((e2 - s2).days + 1, 1)
    return max(0.0, min(1.0, (2 * overlap) / span))


def _series_event_score(m1: Market, m2: Market) -> float:
    if m1.event_id and m1.event_id == m2.event_id:
        return 1.0
    if m1.series_id and m1.series_id == m2.series_id:
        return 0.6
    return 0.0


@dataclass(frozen=True)
class PairContext:
    market_by_id: dict[str, Market]
    embeddings: dict[str, list[float]]
    entities: dict[str, list[Entity]]
    price_series: dict[str, list[float]]


class RelationshipDetectionAgent:
    """Generates candidate pairs via buckets, scores, optionally refines with Bedrock."""

    def __init__(self, bedrock: BedrockClient | None = None) -> None:
        self._bedrock = bedrock

    def build_candidates(
        self,
        markets: Sequence[Market],
        *,
        max_pairs: int = 5000,
    ) -> set[tuple[str, str]]:
        mids = [m.id for m in markets if m.id]
        pairs: set[tuple[str, str]] = set()

        by_event: dict[str, list[str]] = defaultdict(list)
        by_series: dict[str, list[str]] = defaultdict(list)
        by_tag: dict[str, list[str]] = defaultdict(list)
        by_entity: dict[str, list[str]] = defaultdict(list)

        for m in markets:
            if m.event_id:
                by_event[m.event_id].append(m.id)
            if m.series_id:
                by_series[m.series_id].append(m.id)
            for t in m.tags:
                by_tag[t].append(m.id)

        entities_map: dict[str, list[Entity]] = getattr(self, "_entities_map", {})

        def add_bucket(group: list[str]) -> None:
            if len(group) < 2:
                return
            uniq = sorted(set(group))
            if len(uniq) > 200:
                uniq = uniq[:200]
            for a, b in combinations(uniq, 2):
                pairs.add(_canonical_pair(a, b))
                if len(pairs) >= max_pairs:
                    return

        for _eid, group in by_event.items():
            add_bucket(group)
            if len(pairs) >= max_pairs:
                return pairs

        for _sid, group in by_series.items():
            if len(group) <= 150:
                add_bucket(group)
            if len(pairs) >= max_pairs:
                return pairs

        for _tag, group in by_tag.items():
            if 2 <= len(group) <= 120:
                add_bucket(group)
            if len(pairs) >= max_pairs:
                return pairs

        # Embedding neighbourhood (lightweight): compare within each tag super-bucket
        embeddings: dict[str, list[float]] = getattr(self, "_embeddings_map", {})
        for _tag, group in by_tag.items():
            if len(group) > 120:
                continue
            for i, mid_a in enumerate(group):
                va = embeddings.get(mid_a)
                if not va:
                    continue
                for mid_b in group[i + 1 :]:
                    vb = embeddings.get(mid_b)
                    if vb and cosine_similarity(va, vb) >= 0.86:
                        pairs.add(_canonical_pair(mid_a, mid_b))
                if len(pairs) >= max_pairs:
                    return pairs

        # Entity buckets populated externally in detect()
        ent_map: dict[str, list[str]] = defaultdict(list)
        for mid, elist in entities_map.items():
            for e in elist:
                key = (e.normalized or e.text).lower()
                if key:
                    ent_map[key].append(mid)
        for _k, group in ent_map.items():
            if 2 <= len(group) <= 80:
                add_bucket(group)
            if len(pairs) >= max_pairs:
                break

        if len(pairs) < 200 and len(mids) <= 300:
            for i, a in enumerate(mids):
                va = embeddings.get(a)
                if not va:
                    continue
                for b in mids[i + 1 :]:
                    vb = embeddings.get(b)
                    if vb and cosine_similarity(va, vb) >= 0.9:
                        pairs.add(_canonical_pair(a, b))
                if len(pairs) >= max_pairs:
                    break

        return pairs

    def score_pair(
        self,
        mid_a: str,
        mid_b: str,
        ctx: PairContext,
    ) -> tuple[float, dict[str, float], list[str]]:
        m1 = ctx.market_by_id[mid_a]
        m2 = ctx.market_by_id[mid_b]
        emb_sim = cosine_similarity(
            ctx.embeddings.get(mid_a, []), ctx.embeddings.get(mid_b, [])
        )
        ent_sim = _jaccard(
            _entity_keys(ctx.entities.get(mid_a, [])),
            _entity_keys(ctx.entities.get(mid_b, [])),
        )
        tag_sim = _jaccard(set(m1.tags), set(m2.tags))
        time_sim = _temporal_score(m1, m2)
        series_sim = _series_event_score(m1, m2)

        s1 = ctx.price_series.get(mid_a)
        s2 = ctx.price_series.get(mid_b)
        price_sim = 0.0
        if s1 and s2 and len(s1) == len(s2):
            r = pearson_correlation(s1, s2)
            if r is not None:
                price_sim = max(0.0, min(1.0, abs(r)))

        score = (
            _WEIGHT_EMB * emb_sim
            + _WEIGHT_ENT * ent_sim
            + _WEIGHT_TAG * tag_sim
            + _WEIGHT_TIME * time_sim
            + _WEIGHT_SERIES * series_sim
            + _WEIGHT_PRICE * price_sim
        )
        parts = {
            "embedding": emb_sim,
            "entities": ent_sim,
            "tags": tag_sim,
            "time": time_sim,
            "series_event": series_sim,
            "price": price_sim,
        }
        evidence: list[str] = []
        if emb_sim >= 0.75:
            evidence.append(f"High embedding similarity ({emb_sim:.2f})")
        if ent_sim > 0:
            shared = _entity_keys(ctx.entities.get(mid_a, [])) & _entity_keys(
                ctx.entities.get(mid_b, [])
            )
            if shared:
                evidence.append("Shared entities: " + ", ".join(sorted(shared)[:8]))
        if tag_sim > 0:
            shared_tags = set(m1.tags) & set(m2.tags)
            if shared_tags:
                evidence.append("Shared tags: " + ", ".join(sorted(shared_tags)[:8]))
        if series_sim >= 1.0:
            evidence.append("Same Gamma event grouping")
        elif series_sim >= 0.6:
            evidence.append("Same Polymarket series id")
        if price_sim >= 0.5:
            evidence.append("Historically correlated token prices (Pearson magnitude)")
        return score, parts, evidence

    def _llm_classify(self, m1: Market, m2: Market, draft_evidence: list[str]) -> dict[str, Any] | None:
        if self._bedrock is None:
            return None
        system = (
            "You classify relationships between prediction markets. "
            "Answer JSON only with keys: relationship_type, confidence, evidence (string[]), explanation. "
            f"relationship_type must be one of: {[t.value for t in RelationshipType]}."
        )
        user = json.dumps(
            {
                "market_a": {"id": m1.id, "question": m1.question, "tags": m1.tags},
                "market_b": {"id": m2.id, "question": m2.question, "tags": m2.tags},
                "heuristic_evidence": draft_evidence,
            },
            ensure_ascii=False,
        )
        raw = self._bedrock.invoke_reasoning(system, user, max_tokens=800)
        text = raw.strip()
        if "```" in text:
            m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
            if m:
                text = m.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("llm_relationship_parse_failed")
            return None

    def detect(
        self,
        markets: Sequence[Market],
        embeddings: dict[str, list[float]],
        entities: dict[str, list[Entity]],
        *,
        price_series: dict[str, list[float]] | None = None,
        max_pairs: int = 5000,
        use_llm: bool = True,
    ) -> list[Relationship]:
        self._embeddings_map = embeddings
        self._entities_map = entities
        market_by_id = {m.id: m for m in markets if m.id}
        ctx = PairContext(
            market_by_id=market_by_id,
            embeddings=embeddings,
            entities=entities,
            price_series=price_series or {},
        )
        pairs = self.build_candidates(markets, max_pairs=max_pairs)
        out: list[Relationship] = []
        for mid_a, mid_b in pairs:
            if mid_a not in market_by_id or mid_b not in market_by_id:
                continue
            score, _parts, evidence = self.score_pair(mid_a, mid_b, ctx)
            rel_type = RelationshipType.SHARED_ENTITY
            conf = float(score)
            explanation = "Heuristic composite score across embeddings, entities, tags, time, and series."
            if use_llm and self._bedrock and score >= _LLM_THRESHOLD:
                llm = self._llm_classify(market_by_id[mid_a], market_by_id[mid_b], evidence)
                if isinstance(llm, dict):
                    try:
                        rel_type = RelationshipType(str(llm.get("relationship_type", rel_type.value)))
                    except ValueError:
                        rel_type = RelationshipType.SHARED_ENTITY
                    try:
                        llm_conf = float(llm.get("confidence", conf))
                    except (TypeError, ValueError):
                        llm_conf = conf
                    conf = max(0.0, min(1.0, 0.55 * score + 0.45 * llm_conf))
                    expl = llm.get("explanation")
                    if isinstance(expl, str) and expl.strip():
                        explanation = expl.strip()
                    ev2 = llm.get("evidence")
                    if isinstance(ev2, list):
                        evidence = [str(x) for x in ev2 if str(x).strip()][:12]
            if rel_type == RelationshipType.UNRELATED:
                continue
            if conf < 0.2:
                continue
            s_id, t_id = _canonical_pair(mid_a, mid_b)
            out.append(
                Relationship(
                    source_market_id=s_id,
                    target_market_id=t_id,
                    relationship_type=rel_type,
                    confidence_score=conf,
                    evidence=evidence,
                    explanation=explanation,
                )
            )
        out.sort(key=lambda r: r.confidence_score, reverse=True)
        return out
