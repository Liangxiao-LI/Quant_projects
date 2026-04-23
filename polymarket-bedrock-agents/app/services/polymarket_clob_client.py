"""Async client for Polymarket CLOB public read endpoints (no trading)."""

from typing import Any

import httpx

from app.config import Settings, get_settings
from app.utils.logging import get_logger
from app.utils.retry import async_http_retry

logger = get_logger(__name__)


class PolymarketClobClient:
    """
    Public CLOB client for https://clob.polymarket.com
    Order placement / signing is intentionally not implemented.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._base = self._settings.polymarket_clob_base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base,
            timeout=self._settings.http_timeout_seconds,
            headers={"User-Agent": "polymarket-bedrock-agents/1.0"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    @async_http_retry(max_attempts=3)
    async def get_price(self, token_id: str, *, side: str = "BUY") -> float | None:
        r = await self._client.get("/price", params={"token_id": token_id, "side": side})
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and "price" in data:
            try:
                return float(data["price"])
            except (TypeError, ValueError):
                return None
        try:
            return float(data)
        except (TypeError, ValueError):
            return None

    @async_http_retry(max_attempts=3)
    async def get_midpoint(self, token_id: str) -> float | None:
        r = await self._client.get("/midpoint", params={"token_id": token_id})
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and "mid" in data:
            try:
                return float(data["mid"])
            except (TypeError, ValueError):
                return None
        try:
            return float(data)
        except (TypeError, ValueError):
            return None

    @async_http_retry(max_attempts=3)
    async def get_spread(self, token_id: str) -> float | None:
        r = await self._client.get("/spread", params={"token_id": token_id})
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict):
            for key in ("spread", "spd"):
                if key in data:
                    try:
                        return float(data[key])
                    except (TypeError, ValueError):
                        return None
        try:
            return float(data)
        except (TypeError, ValueError):
            return None

    @async_http_retry(max_attempts=3)
    async def get_order_book(self, token_id: str) -> dict[str, Any]:
        r = await self._client.get("/book", params={"token_id": token_id})
        r.raise_for_status()
        return r.json()

    async def get_price_history(self, token_id: str) -> list[dict[str, Any]]:
        """
        Historical prices for a token.
        TODO: Confirm official path and params (`interval`, `startTs`, `endTs`, `fidelity`).
        Polymarket docs evolve; adjust if this returns 404 in your environment.
        """
        try:
            r = await self._client.get(
                "/prices-history",
                params={"market": token_id},
            )
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "history" in data:
                return list(data["history"])
            return []
        except httpx.HTTPStatusError as e:
            logger.warning(
                "clob_price_history_unavailable",
                extra={"status": e.response.status_code, "token_id": token_id},
            )
            return []
