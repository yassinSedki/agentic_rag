"""Stream answer node — terminal SSE emitter.

This is the **terminal node** of the graph.  It packages ``final_answer``,
``source_ids``, and ``metadata`` into the format expected by the SSE
streaming endpoint in the API layer.

The actual SSE byte-streaming happens in ``api/v1/chat.py`` — this node
simply prepares the final payload.
"""

from __future__ import annotations

import structlog

from app.agent.state import AgentState

logger = structlog.get_logger()


async def stream_answer(state: AgentState) -> dict:
    """Prepare the final answer payload for SSE streaming.

    This node doesn't perform the actual streaming — it formats the
    data so the API layer can emit SSE events.
    """
    final_answer = state.get("final_answer", "")
    source_ids = state.get("source_ids", [])
    metadata = state.get("metadata", {})
    retrieval_score = state.get("retrieval_score", 0.0)
    error = state.get("error")

    logger.info(
        "stream_answer_prepared",
        answer_len=len(final_answer),
        source_count=len(source_ids),
        has_error=error is not None,
    )

    return {
        "final_answer": final_answer,
        "metadata": {
            **metadata,
            "source_ids": source_ids,
            "retrieval_score": retrieval_score,
            "has_error": error is not None,
        },
    }
