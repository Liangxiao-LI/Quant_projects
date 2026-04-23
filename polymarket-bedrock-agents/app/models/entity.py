"""Entity extraction domain models."""

from enum import Enum

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    PERSON = "PERSON"
    ORGANISATION = "ORGANISATION"
    COUNTRY = "COUNTRY"
    CITY = "CITY"
    ASSET = "ASSET"
    CRYPTO = "CRYPTO"
    STOCK = "STOCK"
    COMMODITY = "COMMODITY"
    SPORTS_TEAM = "SPORTS_TEAM"
    POLITICAL_PARTY = "POLITICAL_PARTY"
    EVENT = "EVENT"
    DATE = "DATE"
    MACRO_INDICATOR = "MACRO_INDICATOR"
    TOPIC = "TOPIC"


class Entity(BaseModel):
    """Structured entity mention."""

    text: str = Field(..., description="Surface form as in the market text")
    entity_type: EntityType
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    normalized: str | None = Field(
        default=None,
        description="Canonical name if different from surface form",
    )
