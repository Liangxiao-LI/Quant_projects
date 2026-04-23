"""Data API client smoke tests (mocked)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.polymarket_data_client import PolymarketDataClient


@pytest.mark.asyncio
async def test_get_activity_returns_list() -> None:
    c = PolymarketDataClient()
    r = MagicMock()
    r.raise_for_status = MagicMock()
    r.json.return_value = []
    c._client.get = AsyncMock(return_value=r)  # type: ignore[method-assign]
    out = await c.get_activity()
    assert out == []
    await c.aclose()
