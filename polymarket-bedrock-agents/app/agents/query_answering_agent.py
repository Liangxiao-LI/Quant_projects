"""Evidence-first answers using stored relationships and text search."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.market_repository import MarketRepository
from app.repositories.relationship_repository import RelationshipRepository


class QueryAnsweringAgent:
    def __init__(self, session: AsyncSession) -> None:
        self._markets = MarketRepository(session)
        self._rels = RelationshipRepository(session)

    async def related_for_market(self, market_id: str) -> dict[str, Any]:
        rows = await self._rels.list_related(market_id, min_confidence=0.0, limit=50)
        return {"market_id": market_id, "related_markets": rows}

    async def search_keyword(self, q: str) -> dict[str, Any]:
        hits = await self._markets.search_markets(q, limit=30)
        return {
            "query": q,
            "markets": [
                {"market_id": m.id, "title": m.question, "tags": m.tags} for m in hits
            ],
        }
