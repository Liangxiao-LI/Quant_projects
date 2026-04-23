"""Async client for Polymarket Gamma API (discovery: events, markets, tags, series, search)."""

from typing import Any

import httpx

from app.config import Settings, get_settings
from app.utils.logging import get_logger
from app.utils.retry import async_http_retry

logger = get_logger(__name__)


class PolymarketGammaClient:
    """HTTP client for https://gamma-api.polymarket.com — primary ingestion API."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._base = self._settings.polymarket_gamma_base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base,
            timeout=self._settings.http_timeout_seconds,
            headers={"User-Agent": "polymarket-bedrock-agents/1.0"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    @async_http_retry(max_attempts=3)
    async def fetch_active_events(
        self, *, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Fetch a page of active, non-closed events (includes nested markets when provided)."""
        params: dict[str, Any] = {
            "active": "true",
            "closed": "false",
            "limit": limit,
            "offset": offset,
        }
        r = await self._client.get("/events", params=params)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list):
            logger.warning("gamma_events_non_list_response", extra={"type": type(data).__name__})
            return []
        return data

    async def fetch_all_active_events(
        self, *, page_size: int = 100, max_pages: int | None = None
    ) -> list[dict[str, Any]]:
        """Paginate through all active events until empty or max_pages reached."""
        all_rows: list[dict[str, Any]] = []
        offset = 0
        page = 0
        while True:
            batch = await self.fetch_active_events(limit=page_size, offset=offset)
            if not batch:
                break
            all_rows.extend(batch)
            offset += len(batch)
            page += 1
            if max_pages is not None and page >= max_pages:
                break
            if len(batch) < page_size:
                break
        return all_rows

    @async_http_retry(max_attempts=3)
    async def fetch_market(self, market_id: str) -> dict[str, Any]:
        """Fetch a single market by id (Gamma path may vary — TODO verify slug vs numeric id)."""
        r = await self._client.get(f"/markets/{market_id}")
        r.raise_for_status()
        return r.json()

    @async_http_retry(max_attempts=3)
    async def search(self, query: str, *, limit: int = 50) -> list[dict[str, Any]]:
        """
        Full-text style search across Gamma.
        TODO: Confirm exact query params (`q` vs `query`) for production.
        """
        r = await self._client.get("/public-search", params={"q": query, "limit": limit})
        if r.status_code == 404:
            r = await self._client.get("/search", params={"q": query, "limit": limit})
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and "events" in data:
            return list(data.get("events") or [])
        if isinstance(data, list):
            return data
        return []

    @async_http_retry(max_attempts=3)
    async def fetch_tags(self) -> list[dict[str, Any]]:
        r = await self._client.get("/tags")
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []

    @async_http_retry(max_attempts=3)
    async def fetch_series(self) -> list[dict[str, Any]]:
        r = await self._client.get("/series")
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
