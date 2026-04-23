"""Fetch live CLOB microstructure for tokens (public read only)."""

import asyncio
from datetime import datetime, timezone

from app.config import Settings, get_settings
from app.models.market import MarketPrice
from app.services.polymarket_clob_client import PolymarketClobClient


class LivePriceAgent:
    """Wraps Polymarket CLOB for midpoint, spread, top of book — no trading."""

    def __init__(
        self,
        clob: PolymarketClobClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._clob = clob or PolymarketClobClient(settings or get_settings())

    async def snapshot_token(
        self, market_id: str, token_id: str, *, side: str = "BUY"
    ) -> MarketPrice:
        price, mid, spread, book = await self._gather(token_id, side=side)
        bids = book.get("bids") if isinstance(book.get("bids"), list) else []
        asks = book.get("asks") if isinstance(book.get("asks"), list) else []
        return MarketPrice(
            market_id=market_id,
            token_id=token_id,
            side=side,
            price=price,
            midpoint=mid,
            spread=spread,
            bids=bids,
            asks=asks,
            as_of=datetime.now(timezone.utc),
        )

    async def _gather(self, token_id: str, *, side: str) -> tuple:
        price, mid, spread, book = await asyncio.gather(
            self._clob.get_price(token_id, side=side),
            self._clob.get_midpoint(token_id),
            self._clob.get_spread(token_id),
            self._clob.get_order_book(token_id),
        )
        return price, mid, spread, book
