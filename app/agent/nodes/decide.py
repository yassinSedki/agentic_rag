"""Decide node — classifies user intent and sets the routing decision.

Routes:
    ``"rag"``     — question requires document retrieval.
    ``"direct"``  — simple question the LLM can answer directly.
    ``"clarify"`` — question is ambiguous and needs clarification.
"""

from __future__ import annotations

import structlog

from app.agent.state import AgentState
from app.llm.llm_factory import get_chat_llm

logger = structlog.get_logger()

_CLASSIFY_PROMPT = """You are a routing classifier for a RAG system.
Given the user's question and conversation history, classify the intent.

Rules:
- If the question requires information from documents/knowledge base → respond with "rag"
- If the question is a simple greeting, math, or general knowledge → respond with "direct"
- If the question is ambiguous or too vague to answer → respond with "clarify"

Respond with ONLY one word: rag, direct, or clarify

Question: {question}
History: {history}

Classification:"""


async def decide(state: AgentState) -> dict:
    """Classify the user's intent and determine the graph route."""
    question = state["question"]
    history = state.get("history", [])

    llm = get_chat_llm()
    prompt = _CLASSIFY_PROMPT.format(
        question=question,
        history=str(history[-5:]) if history else "[]",
    )

    try:
        response = await llm.ainvoke(prompt)
        route_text = response.content.strip().lower()

        # Normalise — accept only known routes
        if "direct" in route_text:
            route = "direct"
        elif "clarify" in route_text:
            route = "clarify"
        else:
            route = "rag"  # default fallback

        logger.info("decide_route", route=route, question=question[:80])
        return {"route": route}

    except Exception as exc:
        logger.error("decide_failed", error=str(exc))
        return {"route": "rag"}  # safe fallback
