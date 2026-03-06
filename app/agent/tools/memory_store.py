"""Stub implementation of memory tools for the agent."""

from __future__ import annotations

import structlog

logger = structlog.get_logger()

async def store_summary(conversation_id: str, summary: str) -> dict[str, str]:
    """Stub for storing a conversation summary.
    
    Currently a no-op as memory integration is handled later.
    """
    logger.info("memory_tool_store_summary_skipped", conversation_id=conversation_id)
    return {"status": "skipped", "message": "Memory summary store not implemented yet"}

async def retrieve_context(conversation_id: str) -> str:
    """Stub for retrieving conversation context.
    
    Currently a no-op as memory integration is handled later.
    """
    logger.info("memory_tool_retrieve_context_skipped", conversation_id=conversation_id)
    return ""
