"""Persistence for events, markets, embeddings, and extracted entities."""

from __future__ import annotations

import json
from typing import Any, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity import Entity
from app.models.market import Event, Market, Outcome


class MarketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_event(self, event: Event) -> None:
        payload = {**(event.raw or {})}
        if event.tags:
            payload["tags"] = event.tags
        await self._session.execute(
            text(
                """
                INSERT INTO events (id, slug, title, description, series_id, active, closed,
                    start_date, end_date, payload, updated_at)
                VALUES (:id, :slug, :title, :description, :series_id, :active, :closed,
                    :start_date, :end_date, CAST(:payload AS jsonb), NOW())
                ON CONFLICT (id) DO UPDATE SET
                    slug = EXCLUDED.slug,
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    series_id = EXCLUDED.series_id,
                    active = EXCLUDED.active,
                    closed = EXCLUDED.closed,
                    start_date = EXCLUDED.start_date,
                    end_date = EXCLUDED.end_date,
                    payload = EXCLUDED.payload,
                    updated_at = NOW()
                """
            ),
            {
                "id": event.id,
                "slug": event.slug,
                "title": event.title,
                "description": event.description,
                "series_id": event.series_id,
                "active": event.active,
                "closed": event.closed,
                "start_date": event.start_date,
                "end_date": event.end_date,
                "payload": json.dumps(payload),
            },
        )

    async def upsert_market(self, market: Market) -> None:
        await self._session.execute(
            text(
                """
                INSERT INTO markets (id, event_id, slug, question, description, condition_id,
                    series_id, active, closed, volume, liquidity, start_date, end_date,
                    tags, outcome_names, clob_token_ids, payload, updated_at)
                VALUES (:id, :event_id, :slug, :question, :description, :condition_id,
                    :series_id, :active, :closed, :volume, :liquidity, :start_date, :end_date,
                    :tags, :outcome_names, :clob_token_ids, CAST(:payload AS jsonb), NOW())
                ON CONFLICT (id) DO UPDATE SET
                    event_id = EXCLUDED.event_id,
                    slug = EXCLUDED.slug,
                    question = EXCLUDED.question,
                    description = EXCLUDED.description,
                    condition_id = EXCLUDED.condition_id,
                    series_id = EXCLUDED.series_id,
                    active = EXCLUDED.active,
                    closed = EXCLUDED.closed,
                    volume = EXCLUDED.volume,
                    liquidity = EXCLUDED.liquidity,
                    start_date = EXCLUDED.start_date,
                    end_date = EXCLUDED.end_date,
                    tags = EXCLUDED.tags,
                    outcome_names = EXCLUDED.outcome_names,
                    clob_token_ids = EXCLUDED.clob_token_ids,
                    payload = EXCLUDED.payload,
                    updated_at = NOW()
                """
            ),
            {
                "id": market.id,
                "event_id": market.event_id,
                "slug": market.slug,
                "question": market.question,
                "description": market.description,
                "condition_id": market.condition_id,
                "series_id": market.series_id,
                "active": market.active,
                "closed": market.closed,
                "volume": market.volume,
                "liquidity": market.liquidity,
                "start_date": market.start_date,
                "end_date": market.end_date,
                "tags": market.tags,
                "outcome_names": [o.name for o in market.outcomes],
                "clob_token_ids": market.clob_token_ids,
                "payload": json.dumps(market.raw),
            },
        )

    async def upsert_embedding(self, market_id: str, vector: Sequence[float]) -> None:
        literal = "[" + ",".join(str(float(x)) for x in vector) + "]"
        await self._session.execute(
            text(
                """
                INSERT INTO market_embeddings (market_id, embedding)
                VALUES (:market_id, CAST(:embedding AS vector))
                ON CONFLICT (market_id) DO UPDATE SET
                    embedding = EXCLUDED.embedding
                """
            ),
            {"market_id": market_id, "embedding": literal},
        )

    async def replace_entities(self, market_id: str, entities: list[Entity]) -> None:
        await self._session.execute(
            text("DELETE FROM market_entities WHERE market_id = :mid"),
            {"mid": market_id},
        )
        for ent in entities:
            await self._session.execute(
                text(
                    "INSERT INTO market_entities (market_id, entity) VALUES (:mid, CAST(:e AS jsonb))"
                ),
                {"mid": market_id, "e": ent.model_dump_json()},
            )

    async def list_markets(self, *, limit: int = 5000) -> list[Market]:
        res = await self._session.execute(
            text(
                """
                SELECT id, event_id, slug, question, description, condition_id, series_id,
                       active, closed, volume, liquidity, start_date, end_date,
                       tags, outcome_names, clob_token_ids, payload
                FROM markets
                ORDER BY updated_at DESC
                LIMIT :lim
                """
            ),
            {"lim": limit},
        )
        rows = res.mappings().all()
        markets: list[Market] = []
        for row in rows:
            outcomes = [Outcome(name=n, price=None, token_id=None) for n in (row["outcome_names"] or [])]
            raw_payload = row["payload"]
            if isinstance(raw_payload, str):
                try:
                    raw_payload = json.loads(raw_payload)
                except json.JSONDecodeError:
                    raw_payload = {}
            markets.append(
                Market(
                    id=row["id"],
                    event_id=row["event_id"],
                    slug=row["slug"],
                    question=row["question"] or "",
                    description=row["description"],
                    outcomes=outcomes,
                    tags=list(row["tags"] or []),
                    series_id=row["series_id"],
                    condition_id=row["condition_id"],
                    clob_token_ids=list(row["clob_token_ids"] or []),
                    volume=row["volume"],
                    liquidity=row["liquidity"],
                    active=row["active"],
                    closed=row["closed"],
                    start_date=row["start_date"],
                    end_date=row["end_date"],
                    raw=raw_payload if isinstance(raw_payload, dict) else {},
                )
            )
        return markets

    async def get_market(self, market_id: str) -> Market | None:
        res = await self._session.execute(
            text(
                """
                SELECT id, event_id, slug, question, description, condition_id, series_id,
                       active, closed, volume, liquidity, start_date, end_date,
                       tags, outcome_names, clob_token_ids, payload
                FROM markets WHERE id = :id
                """
            ),
            {"id": market_id},
        )
        row = res.mappings().first()
        if not row:
            return None
        outcomes = [Outcome(name=n, price=None, token_id=None) for n in (row["outcome_names"] or [])]
        raw_payload = row["payload"]
        if isinstance(raw_payload, str):
            try:
                raw_payload = json.loads(raw_payload)
            except json.JSONDecodeError:
                raw_payload = {}
        return Market(
            id=row["id"],
            event_id=row["event_id"],
            slug=row["slug"],
            question=row["question"] or "",
            description=row["description"],
            outcomes=outcomes,
            tags=list(row["tags"] or []),
            series_id=row["series_id"],
            condition_id=row["condition_id"],
            clob_token_ids=list(row["clob_token_ids"] or []),
            volume=row["volume"],
            liquidity=row["liquidity"],
            active=row["active"],
            closed=row["closed"],
            start_date=row["start_date"],
            end_date=row["end_date"],
            raw=raw_payload if isinstance(raw_payload, dict) else {},
        )

    async def search_markets(self, q: str, *, limit: int = 50) -> list[Market]:
        like = f"%{q.lower()}%"
        res = await self._session.execute(
            text(
                """
                SELECT id, event_id, slug, question, description, condition_id, series_id,
                       active, closed, volume, liquidity, start_date, end_date,
                       tags, outcome_names, clob_token_ids, payload
                FROM markets
                WHERE lower(question) LIKE :q OR lower(coalesce(description,'')) LIKE :q
                ORDER BY updated_at DESC
                LIMIT :lim
                """
            ),
            {"q": like, "lim": limit},
        )
        rows = res.mappings().all()
        out: list[Market] = []
        for row in rows:
            outcomes = [Outcome(name=n, price=None, token_id=None) for n in (row["outcome_names"] or [])]
            raw_payload = row["payload"]
            if isinstance(raw_payload, str):
                try:
                    raw_payload = json.loads(raw_payload)
                except json.JSONDecodeError:
                    raw_payload = {}
            out.append(
                Market(
                    id=row["id"],
                    event_id=row["event_id"],
                    slug=row["slug"],
                    question=row["question"] or "",
                    description=row["description"],
                    outcomes=outcomes,
                    tags=list(row["tags"] or []),
                    series_id=row["series_id"],
                    condition_id=row["condition_id"],
                    clob_token_ids=list(row["clob_token_ids"] or []),
                    volume=row["volume"],
                    liquidity=row["liquidity"],
                    active=row["active"],
                    closed=row["closed"],
                    start_date=row["start_date"],
                    end_date=row["end_date"],
                    raw=raw_payload if isinstance(raw_payload, dict) else {},
                )
            )
        return out

    async def load_embeddings_map(self) -> dict[str, list[float]]:
        res = await self._session.execute(
            text("SELECT market_id, embedding::text AS e FROM market_embeddings")
        )
        mapping: dict[str, list[float]] = {}
        for row in res.mappings().all():
            s = row["e"]
            if isinstance(s, str) and s.startswith("[") and s.endswith("]"):
                try:
                    mapping[row["market_id"]] = [float(x) for x in s.strip("[]").split(",") if x.strip()]
                except ValueError:
                    continue
        return mapping

    async def load_entities_map(self) -> dict[str, list[Entity]]:
        res = await self._session.execute(text("SELECT market_id, entity FROM market_entities"))
        out: dict[str, list[Entity]] = {}
        for row in res.mappings().all():
            mid = row["market_id"]
            ent = Entity.model_validate(row["entity"])
            out.setdefault(mid, []).append(ent)
        return out
