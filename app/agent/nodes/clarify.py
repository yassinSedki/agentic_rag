"""Clarify node — asks the user for clarification.

Used when the ``decide`` node determines the user's question is too
ambiguous or vague to answer meaningfully.
"""

from __future__ import annotations

import structlog

from app.agent.state import AgentState
from app.llm.llm_factory import get_chat_llm

logger = structlog.get_logger()

_CLARIFY_PROMPT = """You are a helpful assistant. The user's question is ambiguous or too vague.
Ask a brief, friendly clarification question to help you understand what they need.

Do NOT attempt to answer the question — just ask for clarification.

User's question: {question}

Clarification question:"""


async def clarify(state: AgentState) -> dict:
    """Generate a clarification question for an ambiguous user query."""
    question = state["question"]

    llm = get_chat_llm()
    prompt = _CLARIFY_PROMPT.format(question=question)

    try:
        response = await llm.ainvoke(prompt)
        clarification = response.content.strip()

        logger.info("clarification_generated", question=question[:80])
        return {
            "final_answer": clarification,
            "error": None,
        }

    except Exception as exc:
        logger.error("clarify_failed", error=str(exc))
        return {
            "final_answer": "Could you please provide more details about your question?",
            "error": None,
        }
