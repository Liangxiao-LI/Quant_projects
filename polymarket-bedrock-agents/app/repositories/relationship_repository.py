"""Persistence for detected market relationships."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.relationship import Relationship


class RelationshipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def clear_all(self) -> None:
        await self._session.execute(text("DELETE FROM relationships"))

    async def upsert_relationship(self, rel: Relationship) -> None:
        evidence = json.dumps(rel.evidence)
        await self._session.execute(
            text(
                """
                INSERT INTO relationships (source_market_id, target_market_id, relationship_type,
                    confidence_score, evidence, explanation)
                VALUES (:s, :t, :rtype, :score, CAST(:evidence AS jsonb), :explanation)
                ON CONFLICT (source_market_id, target_market_id, relationship_type) DO UPDATE SET
                    confidence_score = EXCLUDED.confidence_score,
                    evidence = EXCLUDED.evidence,
                    explanation = EXCLUDED.explanation
                """
            ),
            {
                "s": rel.source_market_id,
                "t": rel.target_market_id,
                "rtype": rel.relationship_type.value,
                "score": rel.confidence_score,
                "evidence": evidence,
                "explanation": rel.explanation,
            },
        )

    async def list_related(
        self, market_id: str, *, min_confidence: float = 0.0, limit: int = 50
    ) -> list[dict[str, Any]]:
        res = await self._session.execute(
            text(
                """
                SELECT * FROM (
                    SELECT r.target_market_id AS mid, m.question AS title,
                           r.relationship_type, r.confidence_score,
                           r.evidence, r.explanation
                    FROM relationships r
                    JOIN markets m ON m.id = r.target_market_id
                    WHERE r.source_market_id = :mid AND r.confidence_score >= :minc
                    UNION
                    SELECT r.source_market_id AS mid, m.question AS title,
                           r.relationship_type, r.confidence_score,
                           r.evidence, r.explanation
                    FROM relationships r
                    JOIN markets m ON m.id = r.source_market_id
                    WHERE r.target_market_id = :mid AND r.confidence_score >= :minc
                ) u
                ORDER BY u.confidence_score DESC
                LIMIT :lim
                """
            ),
            {"mid": market_id, "minc": min_confidence, "lim": limit},
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
                    "market_id": row["mid"],
                    "title": row["title"],
                    "relationship_type": row["relationship_type"],
                    "confidence_score": float(row["confidence_score"]),
                    "evidence": ev if isinstance(ev, list) else [],
                    "explanation": row["explanation"] or "",
                }
            )
        return rows
