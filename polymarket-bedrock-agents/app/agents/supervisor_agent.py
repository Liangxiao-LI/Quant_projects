"""Lightweight orchestration: route natural-language tasks to specialised agents."""

from __future__ import annotations

import re
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.query_answering_agent import QueryAnsweringAgent
from app.utils.logging import get_logger

logger = get_logger(__name__)

Intent = Literal["related", "search", "correlated", "duplicates", "logical", "unknown"]


class SupervisorAgent:
    """Decides which downstream agent to call for `/query` MVP heuristics."""

    def __init__(self, session: AsyncSession) -> None:
        self._qa = QueryAnsweringAgent(session)

    def classify_intent(self, user_query: str) -> Intent:
        q = user_query.lower()
        if re.search(r"related|similar|same (topic|event)", q):
            return "related"
        if re.search(r"duplicate|near-?duplicate|same market", q):
            return "duplicates"
        if re.search(r"correlat|co-?movement|move together", q):
            return "correlated"
        if re.search(r"mutual|exclusive|logically|implies|depend", q):
            return "logical"
        if re.search(r"find|search|which markets.*\b(trump|bitcoin|fed|cpi|nvidia|ukraine|premier)", q):
            return "search"
        if "find" in q or "search" in q:
            return "search"
        return "unknown"

    async def handle_query(self, user_query: str) -> dict[str, Any]:
        intent = self.classify_intent(user_query)
        logger.info("supervisor_intent", extra={"intent": intent})
        if intent == "search":
            # crude keyword extraction after last "search" or whole string
            m = re.search(r"(?:search|find)\s+(.+)$", user_query, re.IGNORECASE)
            kw = (m.group(1) if m else user_query).strip(" ?.")
            return {"intent": intent, "result": await self._qa.search_keyword(kw)}
        return {
            "intent": intent,
            "hint": "Provide market_id via /markets/{id}/related or run /ingest then /relationships/detect.",
        }
