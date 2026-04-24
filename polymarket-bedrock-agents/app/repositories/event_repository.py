"""Event-only persistence: snapshots, event embeddings, event–event edges."""

from __future__ import annotations

import json
from typing import Any, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event_link import EventRelationship
from app.models.market import Event


def _parse_payload(val: Any) -> dict[str, Any]:
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return {}
    return {}


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert_snapshot(
        self, *, event_count: int, markets_in_gamma: int, source: str = "gamma"
    ) -> int:
        res = await self._session.execute(
            text(
                """
                INSERT INTO event_count_snapshots (event_count, markets_in_gamma, source)
                VALUES (:ec, :mg, :src)
                RETURNING id
                """
            ),
            {"ec": event_count, "mg": markets_in_gamma, "src": source},
        )
        row = res.mappings().first()
        await self._session.commit()
        return int(row["id"]) if row else 0

    async def list_snapshots(self, *, limit: int = 20) -> list[dict[str, Any]]:
        res = await self._session.execute(
            text(
                """
                SELECT id, event_count, markets_in_gamma, source, captured_at
                FROM event_count_snapshots
                ORDER BY captured_at DESC
                LIMIT :lim
                """
            ),
            {"lim": limit},
        )
        return [dict(r) for r in res.mappings().all()]

    async def list_events(self, *, limit: int = 5000) -> list[Event]:
        res = await self._session.execute(
            text(
                """
                SELECT id, slug, title, description, series_id, active, closed,
                       start_date, end_date, payload
                FROM events
                ORDER BY updated_at DESC
                LIMIT :lim
                """
            ),
            {"lim": limit},
        )
        out: list[Event] = []
        for row in res.mappings().all():
            raw = _parse_payload(row["payload"])
            tags = raw.get("tags")
            if not isinstance(tags, list):
                tags = []
            out.append(
                Event(
                    id=row["id"],
                    slug=row["slug"],
                    title=row["title"] or "",
                    description=row["description"],
                    tags=[str(t) for t in tags],
                    series_id=row["series_id"],
                    active=row["active"],
                    closed=row["closed"],
                    start_date=row["start_date"],
                    end_date=row["end_date"],
                    markets=[],
                    raw=raw,
                )
            )
        return out

    async def upsert_event_embedding(self, event_id: str, vector: Sequence[float]) -> None:
        literal = "[" + ",".join(str(float(x)) for x in vector) + "]"
        await self._session.execute(
            text(
                """
                INSERT INTO event_embeddings (event_id, embedding)
                VALUES (:eid, CAST(:emb AS vector))
                ON CONFLICT (event_id) DO UPDATE SET embedding = EXCLUDED.embedding
                """
            ),
            {"eid": event_id, "emb": literal},
        )

    async def load_event_embeddings_map(self) -> dict[str, list[float]]:
        res = await self._session.execute(
            text("SELECT event_id, embedding::text AS e FROM event_embeddings")
        )
        m: dict[str, list[float]] = {}
        for row in res.mappings().all():
            s = row["e"]
            if isinstance(s, str) and s.startswith("["):
                try:
                    m[row["event_id"]] = [float(x) for x in s.strip("[]").split(",") if x.strip()]
                except ValueError:
                    continue
        return m

    async def clear_event_relationships(self) -> None:
        await self._session.execute(text("DELETE FROM event_relationships"))
        await self._session.commit()

    async def upsert_event_relationship(self, rel: EventRelationship) -> None:
        """Insert/update one row; caller should commit after batch."""
        await self._session.execute(
            text(
                """
                INSERT INTO event_relationships (source_event_id, target_event_id, relationship_type,
                    confidence_score, evidence, explanation)
                VALUES (:s, :t, :rtype, :score, CAST(:evidence AS jsonb), :explanation)
                ON CONFLICT (source_event_id, target_event_id, relationship_type) DO UPDATE SET
                    confidence_score = EXCLUDED.confidence_score,
                    evidence = EXCLUDED.evidence,
                    explanation = EXCLUDED.explanation
                """
            ),
            {
                "s": rel.source_event_id,
                "t": rel.target_event_id,
                "rtype": rel.relationship_type.value,
                "score": rel.confidence_score,
                "evidence": json.dumps(rel.evidence),
                "explanation": rel.explanation,
            },
        )

    async def list_related_events(self, event_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        res = await self._session.execute(
            text(
                """
                SELECT * FROM (
                    SELECT r.target_event_id AS eid, e.title,
                           r.relationship_type, r.confidence_score, r.evidence, r.explanation
                    FROM event_relationships r
                    JOIN events e ON e.id = r.target_event_id
                    WHERE r.source_event_id = :eid
                    UNION
                    SELECT r.source_event_id AS eid, e.title,
                           r.relationship_type, r.confidence_score, r.evidence, r.explanation
                    FROM event_relationships r
                    JOIN events e ON e.id = r.source_event_id
                    WHERE r.target_event_id = :eid
                ) u
                ORDER BY u.confidence_score DESC
                LIMIT :lim
                """
            ),
            {"eid": event_id, "lim": limit},
        )
        rows: list[dict[str, Any]] = []
        for row in res.mappings().all():
            ev = row["evidence"]
            if isinstance(ev, str):
                try:
                    ev = json.loads(ev)
                except json.JSONDecodeError:
                    ev = []
            rows.append(
                {
                    "event_id": row["eid"],
                    "title": row["title"],
                    "relationship_type": row["relationship_type"],
                    "confidence_score": float(row["confidence_score"]),
                    "evidence": ev if isinstance(ev, list) else [],
                    "explanation": row["explanation"] or "",
                }
            )
        return rows
