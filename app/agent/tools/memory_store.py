"""Memory store tool — placeholder for future memory integration.

⚠️  This module is intentionally a stub.  Long-term memory will be
implemented in a later phase.  For now, all conversation context flows
through ``AgentState.history`` (short-term) and the vector store
(document retrieval).
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger()


async def store_summary(conversation_id: str, summary: str) -> dict:
    """Store a conversation summary (stub — not yet implemented).

    Parameters
    ----------
    conversation_id:
        Session identifier.
    summary:
        Summary text to store.

    Returns
    -------
    dict
        Status of the operation.
    """
    logger.debug(
        "memory_store_stub",
        conversation_id=conversation_id,
        hint="Memory integration not yet implemented",
    )
    return {"status": "skipped", "reason": "memory_not_implemented"}


async def retrieve_context(conversation_id: str) -> str:
    """Retrieve conversation context (stub — not yet implemented).

    Parameters
    ----------
    conversation_id:
        Session identifier.

    Returns
    -------
    str
        Empty string (memory not yet integrated).
    """
    logger.debug(
        "memory_retrieve_stub",
        conversation_id=conversation_id,
        hint="Memory integration not yet implemented",
    )
    return ""
