"""Relationships between Polymarket *events* (not individual markets)."""

from enum import Enum

from pydantic import BaseModel, Field


class EventRelationshipType(str, Enum):
    """Directed edge semantics: source_event *relates to* target_event."""

    EVENT_A_CONTAINS_B = "EVENT_A_CONTAINS_B"
    """A's time range and/or market scope subsumes B (e.g. parent election vs single race)."""

    EVENT_B_CONTAINS_A = "EVENT_B_CONTAINS_A"
    EVENT_TEMPORAL_OVERLAP = "EVENT_TEMPORAL_OVERLAP"
    EVENT_SAME_TOPIC = "EVENT_SAME_TOPIC"
    EVENT_NEAR_DUPLICATE = "EVENT_NEAR_DUPLICATE"
    UNRELATED = "UNRELATED"


class EventRelationship(BaseModel):
    source_event_id: str
    target_event_id: str
    relationship_type: EventRelationshipType
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    explanation: str = ""
