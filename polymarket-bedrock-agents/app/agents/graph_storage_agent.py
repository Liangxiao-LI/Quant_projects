"""Persist markets, embeddings, entities, and relationships to PostgreSQL (+ optional Neo4j hook)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity import Entity
from app.models.market import Event, Market
from app.models.relationship import Relationship
from app.repositories.market_repository import MarketRepository
from app.repositories.relationship_repository import RelationshipRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class GraphStorageAgent:
    """Writes structured Gamma-derived data and graph edges to SQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._markets = MarketRepository(session)
        self._rels = RelationshipRepository(session)

    async def save_events(self, events: list[Event]) -> int:
        count = 0
        for ev in events:
            await self._markets.upsert_event(ev)
            for m in ev.markets:
                await self._markets.upsert_market(m)
                count += 1
        await self._session.commit()
        return count

    async def save_embeddings(self, embeddings: dict[str, list[float]]) -> None:
        for mid, vec in embeddings.items():
            await self._markets.upsert_embedding(mid, vec)
        await self._session.commit()

    async def save_entities(self, entities: dict[str, list[Entity]]) -> None:
        for mid, ents in entities.items():
            await self._markets.replace_entities(mid, ents)
        await self._session.commit()

    async def save_relationships(self, relationships: list[Relationship]) -> None:
        for rel in relationships:
            await self._rels.upsert_relationship(rel)
        await self._session.commit()

    async def replace_all_relationships(self, relationships: list[Relationship]) -> None:
        await self._rels.clear_all()
        await self._session.commit()
        for rel in relationships:
            await self._rels.upsert_relationship(rel)
        await self._session.commit()

    async def neo4j_dual_write(self, _relationships: list[Relationship]) -> None:
        """
        Optional Neo4j graph layer (Version 2+).
        TODO: stream (:Market)-[:RELATES]->(:Market) with properties when NEO4J_URI set.
        """
        logger.info("neo4j_dual_write_skipped", extra={"reason": "not_configured_in_mvp"})
