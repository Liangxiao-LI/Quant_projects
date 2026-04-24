"""Core Polymarket ingestion models (normalised from Gamma / CLOB)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Outcome(BaseModel):
    name: str
    price: float | None = None
    token_id: str | None = None


class Market(BaseModel):
    """A single tradeable market (may sit under an Event)."""

    id: str
    event_id: str | None = None
    slug: str | None = None
    question: str = ""
    description: str | None = None
    outcomes: list[Outcome] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    series_id: str | None = None
    condition_id: str | None = None
    clob_token_ids: list[str] = Field(default_factory=list)
    volume: float | None = None
    liquidity: float | None = None
    active: bool | None = None
    closed: bool | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    raw: dict[str, Any] = Field(default_factory=dict, description="Subset of Gamma payload for debugging")

    def embedding_text(self) -> str:
        parts = [
            self.question or "",
            self.description or "",
            " ".join(o.name for o in self.outcomes),
            " ".join(self.tags),
        ]
        return "\n".join(p for p in parts if p).strip()


class Event(BaseModel):
    """Gamma event grouping one or more markets."""

    id: str
    slug: str | None = None
    title: str = ""
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    series_id: str | None = None
    active: bool | None = None
    closed: bool | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    markets: list[Market] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)

    @field_validator("markets", mode="before")
    @classmethod
    def _default_markets(cls, v: Any) -> Any:
        return v if v is not None else []

    def embedding_text(self) -> str:
        """Text used for event-level embeddings (title, description, tags, nested market questions)."""
        parts = [self.title or "", self.description or "", " ".join(self.tags)]
        g = (self.raw or {}).get("gamma_market_summary") or {}
        qs = g.get("market_questions") or []
        if isinstance(qs, list):
            parts.append(" | ".join(str(q) for q in qs[:50]))
        return "\n".join(p for p in parts if p).strip()

    def market_questions_from_payload(self) -> list[str]:
        g = (self.raw or {}).get("gamma_market_summary") or {}
        qs = g.get("market_questions")
        return [str(q) for q in qs] if isinstance(qs, list) else []


class MarketPrice(BaseModel):
    """Live or historical price snapshot from CLOB."""

    market_id: str
    token_id: str
    side: str = "BUY"
    price: float | None = None
    midpoint: float | None = None
    spread: float | None = None
    bids: list[dict[str, Any]] = Field(default_factory=list)
    asks: list[dict[str, Any]] = Field(default_factory=list)
    as_of: datetime | None = None
