"""Lightweight async wrappers for Polymarket Data API (analytics — optional for MVP)."""

from typing import Any

import httpx

from app.config import Settings, get_settings
from app.utils.logging import get_logger
from app.utils.retry import async_http_retry

logger = get_logger(__name__)


class PolymarketDataClient:
    """
    https://data-api.polymarket.com — positions, trades, activity, holders, OI, leaderboards.
    Methods are stubs with TODOs for exact paths/query params; not required for relationship MVP.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._base = self._settings.polymarket_data_base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base,
            timeout=self._settings.http_timeout_seconds,
            headers={"User-Agent": "polymarket-bedrock-agents/1.0"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    @async_http_retry(max_attempts=3)
    async def get_activity(self, **kwargs: Any) -> list[dict[str, Any]]:
        # TODO: confirm endpoint e.g. /activity and filters (user, market, limit)
        r = await self._client.get("/activity", params=kwargs)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []

    @async_http_retry(max_attempts=3)
    async def get_trades(self, **kwargs: Any) -> list[dict[str, Any]]:
        # TODO: confirm `/trades` vs `/live-trades` and required params
        r = await self._client.get("/trades", params=kwargs)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []

    @async_http_retry(max_attempts=3)
    async def get_positions(self, **kwargs: Any) -> list[dict[str, Any]]:
        # TODO: confirm path for public positions snapshots
        r = await self._client.get("/positions", params=kwargs)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []

    @async_http_retry(max_attempts=3)
    async def get_open_interest(self, **kwargs: Any) -> dict[str, Any]:
        # TODO: confirm open interest endpoint shape
        r = await self._client.get("/open-interest", params=kwargs)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, dict) else {}

    @async_http_retry(max_attempts=3)
    async def get_holders(self, **kwargs: Any) -> list[dict[str, Any]]:
        # TODO: confirm holders leaderboard path
        r = await self._client.get("/holders", params=kwargs)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []

    @async_http_retry(max_attempts=3)
    async def get_leaderboards(self, **kwargs: Any) -> list[dict[str, Any]]:
        r = await self._client.get("/leaderboards", params=kwargs)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
