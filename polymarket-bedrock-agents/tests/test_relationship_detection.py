"""Relationship detection scoring tests."""

from app.agents.relationship_detection_agent import RelationshipDetectionAgent
from app.models.entity import Entity, EntityType
from app.models.market import Market, Outcome


def _mk(
    mid: str,
    *,
    q: str,
    event: str | None = None,
    tags: list[str] | None = None,
) -> Market:
    return Market(
        id=mid,
        event_id=event,
        question=q,
        tags=tags or [],
        outcomes=[Outcome(name="Yes"), Outcome(name="No")],
    )


def test_detect_finds_shared_entity_and_tag() -> None:
    m1 = _mk("1", q="Will Trump win?", event="e1", tags=["politics"])
    m2 = _mk("2", q="Trump approval above 50%?", event="e2", tags=["politics"])
    emb = {"1": [1.0, 0.0, 0.0], "2": [0.99, 0.01, 0.0]}
    ents = {
        "1": [Entity(text="Trump", entity_type=EntityType.PERSON, confidence=1.0)],
        "2": [Entity(text="Donald Trump", entity_type=EntityType.PERSON, confidence=1.0, normalized="trump")],
    }
    agent = RelationshipDetectionAgent(bedrock=None)
    rels = agent.detect([m1, m2], emb, ents, max_pairs=100, use_llm=False)
    assert rels, "expected at least one relationship"
    top = rels[0]
    assert {top.source_market_id, top.target_market_id} == {"1", "2"}
    assert top.confidence_score >= 0.2
