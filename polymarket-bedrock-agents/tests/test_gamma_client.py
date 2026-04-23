"""Gamma client tests (mocked HTTP)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.polymarket_gamma_client import PolymarketGammaClient


@pytest.mark.asyncio
async def test_fetch_active_events_parses_list() -> None:
    client = PolymarketGammaClient()
    mock_response = MagicMock()
    mock_response.json.return_value = [{"id": "evt1", "title": "T", "markets": []}]
    mock_response.raise_for_status = MagicMock()

    async def _get(*_a, **_k):
        return mock_response

    client._client.get = AsyncMock(side_effect=_get)  # type: ignore[method-assign]
    rows = await client.fetch_active_events(limit=10, offset=0)
    assert rows and rows[0]["id"] == "evt1"
    await client.aclose()


@pytest.mark.asyncio
async def test_fetch_all_active_events_stops_on_short_page() -> None:
    client = PolymarketGammaClient()

    async def _get(*_a, **_k):
        r = MagicMock()
        r.raise_for_status = MagicMock()
        r.json.return_value = [{"id": "x", "markets": []}]
        return r

    client._client.get = AsyncMock(side_effect=_get)  # type: ignore[method-assign]
    all_rows = await client.fetch_all_active_events(page_size=100, max_pages=3)
    assert len(all_rows) == 1
    await client.aclose()
