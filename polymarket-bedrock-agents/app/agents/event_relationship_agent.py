"""Detect relationships between Polymarket *events* (containment, overlap, topic)."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from itertools import combinations
from typing import Any

from app.models.event_link import EventRelationship, EventRelationshipType
from app.models.market import Event
from app.services.bedrock_client import BedrockClient
from app.services.similarity_service import cosine_similarity
from app.utils.logging import get_logger

logger = get_logger(__name__)

_LLM_THRESHOLD = 0.42


def _canonical(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def _temporal_a_contains_b(a: Event, b: Event) -> bool:
    if not all([a.start_date, a.end_date, b.start_date, b.end_date]):
        return False
    assert a.start_date and a.end_date and b.start_date and b.end_date
    return a.start_date <= b.start_date and a.end_date >= b.end_date


def _question_coverage_score(a_questions: list[str], b_questions: list[str]) -> float:
    """Fraction of B's market questions 'covered' by A's question text blob (proxy for A's scope ⊇ B)."""
    if not b_questions:
        return 0.0
    blob = " ".join(a_questions).lower()
    hits = 0
    for q in b_questions:
        if not q or not q.strip():
            continue
        ql = q.lower()
        if ql in blob or any(ql in (aq or "").lower() for aq in a_questions):
            hits += 1
    return hits / len(b_questions)


class EventRelationshipAgent:
    """Rule + embedding hybrid; optional Bedrock LLM for borderline event pairs."""

    def __init__(self, bedrock: BedrockClient | None = None) -> None:
        self._bedrock = bedrock

    def _build_pairs(self, events: Sequence[Event], *, max_pairs: int) -> set[tuple[str, str]]:
        by_tag: dict[str, list[str]] = defaultdict(list)
        by_series: dict[str, list[str]] = defaultdict(list)
        ids = [e.id for e in events if e.id]
        index = {e.id: e for e in events if e.id}
        for e in events:
            if not e.id:
                continue
            for t in e.tags[:12]:
                by_tag[t].append(e.id)
            if e.series_id:
                by_series[e.series_id].append(e.id)
        pairs: set[tuple[str, str]] = set()

        def add_group(group: list[str]) -> None:
            u = sorted(set(group))
            if len(u) > 150:
                u = u[:150]
            for x, y in combinations(u, 2):
                pairs.add(_canonical(x, y))
                if len(pairs) >= max_pairs:
                    return

        for _k, g in by_tag.items():
            if 2 <= len(g) <= 80:
                add_group(g)
                if len(pairs) >= max_pairs:
                    return pairs
        for _k, g in by_series.items():
            if 2 <= len(g) <= 60:
                add_group(g)
                if len(pairs) >= max_pairs:
                    return pairs

        emb = getattr(self, "_emb", {})
        if len(ids) <= 400:
            for i, ia in enumerate(ids):
                va = emb.get(ia)
                if not va:
                    continue
                for ib in ids[i + 1 :]:
                    vb = emb.get(ib)
                    if vb and cosine_similarity(va, vb) >= 0.82:
                        pairs.add(_canonical(ia, ib))
                    if len(pairs) >= max_pairs:
                        return pairs
        return pairs

    def _llm_classify(self, a: Event, b: Event, hints: list[str]) -> dict[str, Any] | None:
        if not self._bedrock:
            return None
        system = (
            "You compare two prediction-market *events* from Polymarket. "
            "Reply JSON only: {"
            '"relationship_type": one of '
            "[EVENT_A_CONTAINS_B, EVENT_B_CONTAINS_A, EVENT_TEMPORAL_OVERLAP, "
            "EVENT_SAME_TOPIC, EVENT_NEAR_DUPLICATE, UNRELATED], "
            '"confidence": float 0-1, "evidence": string[], "explanation": string}. '
            "EVENT_A_CONTAINS_B means event A's scope logically or temporally subsumes B "
            "(e.g. parent contest vs child proposition)."
        )
        user = json.dumps(
            {
                "event_a": {"id": a.id, "title": a.title, "tags": a.tags, "markets": a.market_questions_from_payload()[:15]},
                "event_b": {"id": b.id, "title": b.title, "tags": b.tags, "markets": b.market_questions_from_payload()[:15]},
                "heuristics": hints,
            },
            ensure_ascii=False,
        )
        raw = self._bedrock.invoke_reasoning(system, user, max_tokens=900)
        text = raw.strip()
        if "```" in text:
            m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
            if m:
                text = m.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("event_rel_llm_parse_failed")
            return None

    def detect(
        self,
        events: Sequence[Event],
        embeddings: dict[str, list[float]],
        *,
        max_pairs: int = 4000,
        use_llm: bool = True,
    ) -> list[EventRelationship]:
        self._emb = embeddings
        ev_map = {e.id: e for e in events if e.id}
        pairs = self._build_pairs(events, max_pairs=max_pairs)
        out: list[EventRelationship] = []
        for x, y in pairs:
            a, b = ev_map.get(x), ev_map.get(y)
            if not a or not b:
                continue
            aq = a.market_questions_from_payload()
            bq = b.market_questions_from_payload()
            hints: list[str] = []
            score = 0.0
            rel = EventRelationshipType.EVENT_SAME_TOPIC
            expl = ""

            if _temporal_a_contains_b(a, b):
                hints.append("A's active window fully covers B's window")
                score += 0.35
                rel = EventRelationshipType.EVENT_A_CONTAINS_B
            elif _temporal_a_contains_b(b, a):
                hints.append("B's active window fully covers A's window")
                score += 0.35
                rel = EventRelationshipType.EVENT_B_CONTAINS_A
            elif all(
                [a.start_date, a.end_date, b.start_date, b.end_date]
            ) and max(a.start_date, b.start_date) < min(a.end_date, b.end_date):  # type: ignore[operator]
                hints.append("Date ranges overlap")
                score += 0.2
                rel = EventRelationshipType.EVENT_TEMPORAL_OVERLAP

            cov_ab = _question_coverage_score(aq, bq)
            cov_ba = _question_coverage_score(bq, aq)
            if cov_ab >= 0.85 and len(bq) > 0:
                hints.append(f"B's markets mostly described inside A's scope ({cov_ab:.0%})")
                score += 0.35
                rel = EventRelationshipType.EVENT_A_CONTAINS_B
            elif cov_ba >= 0.85 and len(aq) > 0:
                hints.append(f"A's markets mostly described inside B's scope ({cov_ba:.0%})")
                score += 0.35
                rel = EventRelationshipType.EVENT_B_CONTAINS_A

            tag_j = len(set(a.tags) & set(b.tags)) / max(1, len(set(a.tags) | set(b.tags)))
            if tag_j > 0:
                score += 0.15 * tag_j
                hints.append(f"Tag overlap Jaccard={tag_j:.2f}")

            sim = cosine_similarity(embeddings.get(a.id, []), embeddings.get(b.id, []))
            score += 0.25 * sim
            if sim >= 0.78:
                hints.append(f"High title+scope embedding similarity ({sim:.2f})")

            if a.series_id and a.series_id == b.series_id:
                score += 0.1
                hints.append("Same Gamma series id")

            conf = max(0.0, min(1.0, score))
            if use_llm and self._bedrock and conf >= _LLM_THRESHOLD and conf < 0.92:
                llm = self._llm_classify(a, b, hints)
                if isinstance(llm, dict):
                    try:
                        rel = EventRelationshipType(str(llm.get("relationship_type", rel.value)))
                    except ValueError:
                        pass
                    try:
                        conf = max(conf, float(llm.get("confidence", conf)))
                    except (TypeError, ValueError):
                        pass
                    ex = llm.get("explanation")
                    if isinstance(ex, str) and ex.strip():
                        expl = ex.strip()
                    evl = llm.get("evidence")
                    if isinstance(evl, list):
                        hints = [str(s) for s in evl if str(s).strip()][:10]

            if rel == EventRelationshipType.UNRELATED or conf < 0.18:
                continue

            # Containment is directed (container → contained). Other types use stable ordering.
            if rel == EventRelationshipType.EVENT_A_CONTAINS_B:
                src, tgt, rtype = a.id, b.id, EventRelationshipType.EVENT_A_CONTAINS_B
            elif rel == EventRelationshipType.EVENT_B_CONTAINS_A:
                src, tgt, rtype = b.id, a.id, EventRelationshipType.EVENT_A_CONTAINS_B
            elif rel == EventRelationshipType.EVENT_TEMPORAL_OVERLAP:
                src, tgt, rtype = a.id, b.id, EventRelationshipType.EVENT_TEMPORAL_OVERLAP
            elif rel == EventRelationshipType.EVENT_NEAR_DUPLICATE:
                ca, cb = _canonical(a.id, b.id)
                src, tgt, rtype = ca, cb, EventRelationshipType.EVENT_NEAR_DUPLICATE
            else:
                ca, cb = _canonical(a.id, b.id)
                src, tgt, rtype = ca, cb, EventRelationshipType.EVENT_SAME_TOPIC

            out.append(
                EventRelationship(
                    source_event_id=src,
                    target_event_id=tgt,
                    relationship_type=rtype,
                    confidence_score=conf,
                    evidence=hints,
                    explanation=expl or "Hybrid rules on dates, tags, nested market text, and embeddings.",
                )
            )
        out.sort(key=lambda r: r.confidence_score, reverse=True)
        return out
