"""Persist markets, embeddings, entities, and relationships to PostgreSQL (+ optional Neo4j hook)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity import Entity
from app.models.market import Event, Market
from app.models.relationship import Relationship
from app.models.event_link import EventRelationship
from app.repositories.event_repository import EventRepository
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
        self._events = EventRepository(session)

    async def save_events_metadata_only(self, events: list[Event]) -> int:
        """
        Persist only Gamma *events* (no rows in `markets`).
        Embeds nested market questions/ids into `events.payload` for later event–event analysis.
        """
        n = 0
        for ev in events:
            summary = {
                "market_count": len(ev.markets),
                "market_questions": [m.question for m in ev.markets[:120]],
                "market_ids": [m.id for m in ev.markets[:120] if m.id],
            }
            merged_raw = {**(ev.raw or {}), "gamma_market_summary": summary}
            to_save = ev.model_copy(update={"raw": merged_raw})
            await self._markets.upsert_event(to_save)
            n += 1
        await self._session.commit()
        return n

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

    async def save_event_embeddings(self, embeddings: dict[str, list[float]]) -> None:
        for eid, vec in embeddings.items():
            await self._events.upsert_event_embedding(eid, vec)
        await self._session.commit()

    async def replace_all_event_relationships(self, rels: list[EventRelationship]) -> None:
        await self._events.clear_event_relationships()
        for rel in rels:
            await self._events.upsert_event_relationship(rel)
        await self._session.commit()

    async def neo4j_dual_write(self, _relationships: list[Relationship]) -> None:
        """
        Optional Neo4j graph layer (Version 2+).
        TODO: stream (:Market)-[:RELATES]->(:Market) with properties when NEO4J_URI set.
        """
        logger.info("neo4j_dual_write_skipped", extra={"reason": "not_configured_in_mvp"})
