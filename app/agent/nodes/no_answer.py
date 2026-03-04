"""No-answer node — structured "I don't know" response with ingest hint.

This terminal-ish node is used when:
- Retrieval returned no relevant documents.
- Grounding check failed.
- Output validation failed.
"""

from __future__ import annotations

import structlog

from app.agent.state import AgentState

logger = structlog.get_logger()


async def no_answer(state: AgentState) -> dict:
    """Generate a structured 'I don't know' response."""
    error = state.get("error")
    question = state.get("question", "your question")

    # Build a helpful response
    message_parts = [
        "I'm sorry, I don't have enough information to answer that question.",
    ]

    # Add context-specific hint
    if not state.get("retrieval_sufficient", True):
        message_parts.append(
            "No relevant documents were found in the knowledge base."
        )
        message_parts.append(
            "**Hint:** Try ingesting documents related to this topic using the `/ingest` endpoint."
        )
    elif not state.get("grounding_ok", True):
        message_parts.append(
            "The generated answer could not be verified against the available documents."
        )
    elif error:
        message_parts.append(
            "An internal error occurred while processing your request."
        )

    final_answer = "\n\n".join(message_parts)

    logger.info(
        "no_answer_generated",
        reason=error or "insufficient_retrieval",
        question=question[:80],
    )

    return {
        "final_answer": final_answer,
        "error": error or "no_relevant_information",
    }
