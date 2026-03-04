"""Evaluate relevance node — scores retrieved documents against the query.

Sets ``retrieval_sufficient`` and ``retrieval_score`` in state.
Uses a simple heuristic (document count + average score) — swap with
an LLM-based evaluator for higher precision.
"""

from __future__ import annotations

import structlog

from app.agent.state import AgentState
from app.core.metrics import RETRIEVAL_EMPTY

logger = structlog.get_logger()

# Thresholds
_MIN_DOCS = 1
_MIN_SCORE = 0.01  # RRF scores are typically small positive numbers


async def evaluate_relevance(state: AgentState) -> dict:
    """Evaluate whether retrieved documents are sufficient to answer the query."""
    docs = state.get("retrieved_docs", [])

    if not docs:
        RETRIEVAL_EMPTY.inc()
        logger.warning("retrieval_empty", query=state.get("rewritten_query", ""))
        return {
            "retrieval_score": 0.0,
            "retrieval_sufficient": False,
        }

    # Compute average score
    scores = [d.get("score", 0.0) for d in docs if isinstance(d, dict)]
    avg_score = sum(scores) / len(scores) if scores else 0.0

    sufficient = len(docs) >= _MIN_DOCS and avg_score >= _MIN_SCORE

    logger.info(
        "relevance_evaluated",
        doc_count=len(docs),
        avg_score=round(avg_score, 4),
        sufficient=sufficient,
    )

    return {
        "retrieval_score": avg_score,
        "retrieval_sufficient": sufficient,
    }
