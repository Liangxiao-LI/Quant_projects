"""Relationship graph domain models."""

from enum import Enum

from pydantic import BaseModel, Field


class RelationshipType(str, Enum):
    SAME_EVENT = "SAME_EVENT"
    NEAR_DUPLICATE = "NEAR_DUPLICATE"
    SHARED_ENTITY = "SHARED_ENTITY"
    SAME_TOPIC = "SAME_TOPIC"
    CAUSAL_UPSTREAM = "CAUSAL_UPSTREAM"
    CAUSAL_DOWNSTREAM = "CAUSAL_DOWNSTREAM"
    MUTUALLY_EXCLUSIVE = "MUTUALLY_EXCLUSIVE"
    LOGICAL_DEPENDENCY = "LOGICAL_DEPENDENCY"
    PRICE_CORRELATED = "PRICE_CORRELATED"
    HEDGE_OR_OPPOSITE_VIEW = "HEDGE_OR_OPPOSITE_VIEW"
    UNRELATED = "UNRELATED"


class RelationshipEvidence(BaseModel):
    """Single piece of evidence supporting a relationship."""

    kind: str = Field(..., description="e.g. shared_tag, embedding, llm, price_corr")
    detail: str


class Relationship(BaseModel):
    """Directed or undirected market relationship (store both directions if needed)."""

    source_market_id: str
    target_market_id: str
    relationship_type: RelationshipType
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    explanation: str = ""
