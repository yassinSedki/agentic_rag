"""Query rewrite node — rewrites the user's question for better retrieval.

Uses the LLM to produce a more precise, search-friendly version of the
original question, incorporating conversation history for context.
"""

from __future__ import annotations

import structlog

from app.agent.state import AgentState
from app.llm.llm_factory import get_chat_llm

logger = structlog.get_logger()

_REWRITE_PROMPT = """You are a query rewriting assistant for a RAG system.
Rewrite the user's question to be more precise and search-friendly.
- Resolve pronouns using conversation history.
- Add relevant keywords that would improve document retrieval.
- Keep the rewritten query concise (1-2 sentences max).
- Do NOT answer the question — just rewrite it.

Conversation history: {history}

Original question: {question}

Rewritten query:"""


async def query_rewrite(state: AgentState) -> dict:
    """Rewrite the user's question for improved retrieval precision."""
    question = state["question"]
    history = state.get("history", [])

    llm = get_chat_llm()
    prompt = _REWRITE_PROMPT.format(
        question=question,
        history=str(history[-5:]) if history else "[]",
    )

    try:
        response = await llm.ainvoke(prompt)
        rewritten = response.content.strip()

        # Validation: if the rewrite is suspiciously short or empty, keep original
        if len(rewritten) < 5:
            rewritten = question

        logger.info(
            "query_rewritten",
            original=question[:80],
            rewritten=rewritten[:80],
        )
        return {"rewritten_query": rewritten}

    except Exception as exc:
        logger.error("query_rewrite_failed", error=str(exc))
        return {"rewritten_query": question}  # fallback to original
