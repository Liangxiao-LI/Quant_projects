"""CLOB client tests (mocked HTTP)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.polymarket_clob_client import PolymarketClobClient


@pytest.mark.asyncio
async def test_get_price_parses_float() -> None:
    c = PolymarketClobClient()
    r = MagicMock()
    r.raise_for_status = MagicMock()
    r.json.return_value = {"price": "0.42"}
    c._client.get = AsyncMock(return_value=r)  # type: ignore[method-assign]
    p = await c.get_price("tok", side="BUY")
    assert p == pytest.approx(0.42)
    await c.aclose()


@pytest.mark.asyncio
async def test_get_order_book_returns_dict() -> None:
    c = PolymarketClobClient()
    r = MagicMock()
    r.raise_for_status = MagicMock()
    r.json.return_value = {"bids": [], "asks": []}
    c._client.get = AsyncMock(return_value=r)  # type: ignore[method-assign]
    book = await c.get_order_book("tok")
    assert book["bids"] == []
    await c.aclose()
