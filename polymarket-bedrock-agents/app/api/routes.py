"""FastAPI HTTP routes."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.entity_extraction_agent import EntityExtractionAgent
from app.agents.graph_storage_agent import GraphStorageAgent
from app.agents.market_data_ingestion_agent import MarketDataIngestionAgent
from app.agents.query_answering_agent import QueryAnsweringAgent
from app.agents.relationship_detection_agent import RelationshipDetectionAgent
from app.agents.supervisor_agent import SupervisorAgent
from app.db.session import get_session_factory
from app.models.entity import Entity
from app.repositories.market_repository import MarketRepository
from app.repositories.relationship_repository import RelationshipRepository
from app.services.bedrock_client import BedrockClient
from app.services.embedding_service import EmbeddingService
from app.services.polymarket_gamma_client import PolymarketGammaClient
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


async def get_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        yield session


class IngestRequest(BaseModel):
    max_pages: int | None = Field(default=None, description="Gamma pagination cap")
    max_markets: int = Field(default=200, ge=1, le=5000)
    run_relationships: bool = Field(default=False)
    use_llm_relationships: bool = Field(default=True)
    relationship_max_pairs: int = Field(default=5000, ge=10, le=100_000)


class DetectRelationshipsRequest(BaseModel):
    market_ids: list[str] | None = None
    limit_pairs: int = Field(default=5000, ge=10, le=100_000)
    use_llm: bool = True


class QueryBody(BaseModel):
    query: str
    market_id: str | None = None


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/ingest/active-markets")
async def ingest_active_markets(
    body: IngestRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    gamma = PolymarketGammaClient()
    ingestion = MarketDataIngestionAgent(gamma=gamma)
    try:
        events = await ingestion.ingest_active_events(max_pages=body.max_pages)
    finally:
        await gamma.aclose()

    graph = GraphStorageAgent(session)
    saved = await graph.save_events(events)

    markets = [m for ev in events for m in ev.markets][: body.max_markets]
    embedder = EmbeddingService()
    extractor = EntityExtractionAgent()
    embeddings: dict[str, list[float]] = {}
    entities: dict[str, list[Entity]] = {}
    embed_failures: list[str] = []
    entity_failures: list[str] = []
    for m in markets:
        if not m.id:
            continue
        try:
            embeddings[m.id] = embedder.embed(m.embedding_text())
        except Exception as exc:  # noqa: BLE001
            msg = f"{m.id}: {exc}"
            embed_failures.append(msg)
            logger.warning("embed_failed market_id=%s error=%s", m.id, exc)
        try:
            entities[m.id] = extractor.extract_for_market(m)
        except Exception as exc:  # noqa: BLE001
            msg = f"{m.id}: {exc}"
            entity_failures.append(msg)
            logger.warning("entity_failed market_id=%s error=%s", m.id, exc)

    await graph.save_embeddings(embeddings)
    await graph.save_entities(entities)

    rel_count = 0
    if body.run_relationships and markets:
        detector = RelationshipDetectionAgent(
            bedrock=BedrockClient() if body.use_llm_relationships else None
        )
        rels = detector.detect(
            markets,
            embeddings,
            entities,
            max_pairs=body.relationship_max_pairs,
            use_llm=body.use_llm_relationships,
        )
        await graph.save_relationships(rels)
        rel_count = len(rels)

    return {
        "events": len(events),
        "markets_saved": saved,
        "markets_embed_attempted": len(markets),
        "embeddings": len(embeddings),
        "entities_markets": len(entities),
        "embedding_failures": len(embed_failures),
        "entity_failures": len(entity_failures),
        "first_embedding_error": embed_failures[0] if embed_failures else None,
        "first_entity_error": entity_failures[0] if entity_failures else None,
        "relationships_saved": rel_count,
    }


@router.get("/markets/search")
async def markets_search(
    q: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    repo = MarketRepository(session)
    hits = await repo.search_markets(q, limit=50)
    return {
        "query": q,
        "markets": [{"market_id": m.id, "title": m.question, "tags": m.tags} for m in hits],
    }


@router.get("/markets/{market_id}/related")
async def markets_related(
    market_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    repo = MarketRepository(session)
    m = await repo.get_market(market_id)
    if not m:
        raise HTTPException(status_code=404, detail="market not found")
    rel_repo = RelationshipRepository(session)
    rows = await rel_repo.list_related(market_id, limit=50)
    return {"market_id": market_id, "related_markets": rows}


@router.post("/relationships/detect")
async def relationships_detect(
    body: DetectRelationshipsRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    repo = MarketRepository(session)
    graph = GraphStorageAgent(session)
    markets = await repo.list_markets(limit=5000)
    if body.market_ids:
        wanted = set(body.market_ids)
        markets = [m for m in markets if m.id in wanted]
    embeddings = await repo.load_embeddings_map()
    entities = await repo.load_entities_map()
    detector = RelationshipDetectionAgent(bedrock=BedrockClient() if body.use_llm else None)
    if not markets:
        return {"relationships_saved": 0, "note": "no markets in database; run /ingest/active-markets first"}
    rels = detector.detect(
        markets,
        embeddings,
        entities,
        max_pairs=body.limit_pairs,
        use_llm=body.use_llm,
    )
    await graph.replace_all_relationships(rels)
    return {"relationships_saved": len(rels)}


@router.post("/query")
async def natural_query(
    body: QueryBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    sup = SupervisorAgent(session)
    if body.market_id:
        qa = QueryAnsweringAgent(session)
        return {
            "intent": "related",
            "result": await qa.related_for_market(body.market_id),
        }
    return await sup.handle_query(body.query)
