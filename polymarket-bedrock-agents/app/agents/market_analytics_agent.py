"""Optional Data API analytics facade (MVP: interface only)."""

from typing import Any

from app.config import Settings, get_settings
from app.services.polymarket_data_client import PolymarketDataClient


class MarketAnalyticsAgent:
    """
    Uses https://data-api.polymarket.com for activity, trades, holders, OI, etc.
    Not required for MVP relationship scoring; methods delegate to client with TODOs.
    """

    def __init__(
        self,
        client: PolymarketDataClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._client = client or PolymarketDataClient(settings or get_settings())

    async def sample_activity(self, **kwargs: Any) -> list[dict[str, Any]]:
        return await self._client.get_activity(**kwargs)
