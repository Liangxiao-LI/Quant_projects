"""Entity extraction agent tests."""

from unittest.mock import MagicMock

from app.agents.entity_extraction_agent import EntityExtractionAgent
from app.models.entity import EntityType
from app.models.market import Market, Outcome


def test_parse_entities_json() -> None:
    agent = EntityExtractionAgent(bedrock=MagicMock())
    raw = '{"entities":[{"text":"Bitcoin","entity_type":"CRYPTO","confidence":0.9,"normalized":"BTC"}]}'
    ents = agent._parse_entities(raw)
    assert len(ents) == 1
    assert ents[0].entity_type == EntityType.CRYPTO


def test_extract_for_market_uses_bedrock() -> None:
    bedrock = MagicMock()
    bedrock.invoke_reasoning.return_value = (
        '{"entities":[{"text":"Fed","entity_type":"MACRO_INDICATOR","confidence":1,"normalized":null}]}'
    )
    agent = EntityExtractionAgent(bedrock=bedrock)
    m = Market(
        id="m1",
        question="Will the Fed cut rates?",
        outcomes=[Outcome(name="Yes")],
    )
    ents = agent.extract_for_market(m)
    assert ents and ents[0].text == "Fed"
    bedrock.invoke_reasoning.assert_called_once()
