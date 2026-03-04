"""Validate output node — parse raw_answer into a structured schema.

Sets ``final_answer`` on success, or ``error`` on parse failure.
Uses Pydantic to enforce the expected answer format.
"""

from __future__ import annotations

import structlog
from pydantic import BaseModel, ValidationError

from app.agent.state import AgentState

logger = structlog.get_logger()


class ValidatedAnswer(BaseModel):
    """Schema for a valid agent answer."""

    answer: str
    source_ids: list[str] = []


async def validate_output(state: AgentState) -> dict:
    """Validate and normalise the raw answer into the final format."""
    raw_answer = state.get("raw_answer", "")
    source_ids = state.get("source_ids", [])

    if not raw_answer:
        logger.warning("validate_empty_answer")
        return {
            "error": "Empty answer produced by synthesis step.",
            "final_answer": "",
        }

    try:
        validated = ValidatedAnswer(
            answer=raw_answer,
            source_ids=source_ids,
        )

        logger.info(
            "output_validated",
            answer_len=len(validated.answer),
            source_count=len(validated.source_ids),
        )

        return {
            "final_answer": validated.answer,
            "error": None,
        }

    except ValidationError as exc:
        logger.error("output_validation_failed", errors=exc.errors())
        return {
            "error": f"Output validation failed: {exc}",
            "final_answer": "",
        }
