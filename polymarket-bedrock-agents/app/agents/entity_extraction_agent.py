"""LLM-based entity extraction via Amazon Bedrock."""

import json
import re

from app.config import Settings, get_settings
from app.models.entity import Entity, EntityType
from app.models.market import Market
from app.services.bedrock_client import BedrockClient


_SYSTEM = """You extract structured entities from prediction market text.
Return JSON only: {"entities":[{"text":str,"entity_type":str,"confidence":float,"normalized":str|null}]}.
entity_type must be one of: PERSON, ORGANISATION, COUNTRY, CITY, ASSET, CRYPTO, STOCK, COMMODITY,
SPORTS_TEAM, POLITICAL_PARTY, EVENT, DATE, MACRO_INDICATOR, TOPIC."""


class EntityExtractionAgent:
    def __init__(
        self,
        bedrock: BedrockClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._bedrock = bedrock or BedrockClient(settings or get_settings())

    def extract_for_market(self, market: Market) -> list[Entity]:
        user = (
            f"Market question: {market.question}\n"
            f"Description: {market.description or ''}\n"
            f"Tags: {', '.join(market.tags)}\n"
            f"Outcomes: {', '.join(o.name for o in market.outcomes)}\n"
        )
        raw = self._bedrock.invoke_reasoning(_SYSTEM, user, max_tokens=1024)
        return self._parse_entities(raw)

    def _parse_entities(self, raw: str) -> list[Entity]:
        text = raw.strip()
        if "```" in text:
            m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
            if m:
                text = m.group(1).strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return []
        items = payload.get("entities") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            return []
        out: list[Entity] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            try:
                et = EntityType(str(it.get("entity_type", "TOPIC")).upper())
            except ValueError:
                et = EntityType.TOPIC
            try:
                conf = float(it.get("confidence", 1.0))
            except (TypeError, ValueError):
                conf = 1.0
            surface = str(it.get("text", "")).strip()
            if not surface:
                continue
            norm = it.get("normalized")
            out.append(
                Entity(
                    text=surface,
                    entity_type=et,
                    confidence=max(0.0, min(1.0, conf)),
                    normalized=str(norm) if norm else None,
                )
            )
        return out
