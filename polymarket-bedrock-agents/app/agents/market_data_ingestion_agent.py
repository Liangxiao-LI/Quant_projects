"""Ingest active Polymarket events via Gamma and normalise into domain models."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.config import Settings, get_settings
from app.models.market import Event, Market, Outcome
from app.services.polymarket_gamma_client import PolymarketGammaClient
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _parse_dt(val: Any) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _parse_json_list(val: Any) -> list[Any]:
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _normalise_tags(raw: Any) -> list[str]:
    tags = _parse_json_list(raw) if not isinstance(raw, list) else raw
    out: list[str] = []
    for t in tags:
        if isinstance(t, str) and t.strip():
            out.append(t.strip().lower())
        elif isinstance(t, dict):
            slug = t.get("slug") or t.get("label") or t.get("name")
            if isinstance(slug, str) and slug.strip():
                out.append(slug.strip().lower())
    return sorted(set(out))


def _gamma_market_to_market(
    m: dict[str, Any],
    *,
    event_id: str,
    event_tags: list[str],
    series_id: str | None,
) -> Market:
    mid = str(m.get("id") or m.get("marketId") or "")
    question = str(m.get("question") or m.get("title") or "")
    description = m.get("description")
    desc_str = str(description) if description is not None else None

    outcomes_raw = m.get("outcomes")
    outcome_prices = m.get("outcomePrices") or m.get("outcome_prices")
    prices_list = _parse_json_list(outcome_prices) if not isinstance(outcome_prices, list) else outcome_prices
    names: list[str] = []
    if isinstance(outcomes_raw, str):
        try:
            names = [str(x) for x in json.loads(outcomes_raw)]
        except json.JSONDecodeError:
            names = []
    elif isinstance(outcomes_raw, list):
        for item in outcomes_raw:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                n = item.get("name") or item.get("title")
                if isinstance(n, str):
                    names.append(n)
    outcomes: list[Outcome] = []
    token_ids = [str(x) for x in _parse_json_list(m.get("clobTokenIds") or m.get("clob_token_ids"))]
    if not names and token_ids:
        names = [f"Outcome_{i}" for i in range(len(token_ids))]

    for i, name in enumerate(names):
        price = None
        if i < len(prices_list):
            try:
                price = float(prices_list[i])
            except (TypeError, ValueError):
                price = None
        tok = None
        if i < len(token_ids):
            tok = str(token_ids[i])
        outcomes.append(Outcome(name=name, price=price, token_id=tok))

    clob_token_ids = token_ids

    m_tags = _normalise_tags(m.get("tags"))
    merged_tags = sorted(set(event_tags) | set(m_tags))

    return Market(
        id=mid,
        event_id=event_id,
        slug=m.get("slug"),
        question=question,
        description=desc_str,
        outcomes=outcomes,
        tags=merged_tags,
        series_id=m.get("series_id") or series_id,
        condition_id=str(m["conditionId"]) if m.get("conditionId") else None,
        clob_token_ids=clob_token_ids,
        volume=float(m["volume"]) if m.get("volume") is not None else None,
        liquidity=float(m["liquidity"]) if m.get("liquidity") is not None else None,
        active=m.get("active"),
        closed=m.get("closed"),
        start_date=_parse_dt(m.get("startDate") or m.get("start_date")),
        end_date=_parse_dt(m.get("endDate") or m.get("end_date")),
        raw={k: m[k] for k in list(m.keys())[:40]},
    )


def gamma_event_to_event(row: dict[str, Any]) -> Event:
    eid = str(row.get("id") or "")
    ev_tags = _normalise_tags(row.get("tags"))
    series_id = str(row["series_id"]) if row.get("series_id") else None
    markets_raw = row.get("markets") or []
    if not isinstance(markets_raw, list):
        markets_raw = []
    markets: list[Market] = []
    for m in markets_raw:
        if not isinstance(m, dict):
            continue
        try:
            mk = _gamma_market_to_market(
                m, event_id=eid, event_tags=ev_tags, series_id=series_id
            )
            if mk.id:
                markets.append(mk)
        except Exception as exc:  # noqa: BLE001
            logger.warning("skip_market_parse", extra={"error": str(exc), "event_id": eid})
    return Event(
        id=eid,
        slug=row.get("slug"),
        title=str(row.get("title") or ""),
        description=str(row.get("description") or "") if row.get("description") else None,
        tags=ev_tags,
        series_id=series_id,
        active=row.get("active"),
        closed=row.get("closed"),
        start_date=_parse_dt(row.get("startDate") or row.get("start_date")),
        end_date=_parse_dt(row.get("endDate") or row.get("end_date")),
        markets=markets,
        raw={k: row[k] for k in list(row.keys())[:40]},
    )


class MarketDataIngestionAgent:
    """Discovers active events and nested markets from Gamma."""

    def __init__(
        self,
        gamma: PolymarketGammaClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._gamma = gamma or PolymarketGammaClient(self._settings)

    async def ingest_active_events(
        self, *, max_pages: int | None = None
    ) -> list[Event]:
        rows = await self._gamma.fetch_all_active_events(max_pages=max_pages)
        events: list[Event] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                events.append(gamma_event_to_event(row))
            except Exception as exc:  # noqa: BLE001
                logger.warning("skip_event_parse", extra={"error": str(exc)})
        return events
