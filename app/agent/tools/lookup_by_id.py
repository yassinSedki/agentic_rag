"""Lookup-by-ID tool — fetch a full document from the vector store by ID.

Designed to be called as a LangGraph tool node when the agent needs to
inspect a specific document in detail.
"""

from __future__ import annotations

import structlog

from app.vectorstore.base import VectorStoreAdapter

logger = structlog.get_logger()

# Module-level reference — wired by the graph builder
_vector_store: VectorStoreAdapter | None = None


def set_vector_store(vs: VectorStoreAdapter) -> None:
    """Wire the vector store instance (called once at startup)."""
    global _vector_store
    _vector_store = vs


async def lookup_by_id(doc_id: str) -> dict:
    """Fetch a full document by its ``doc_id`` from the vector store.

    Parameters
    ----------
    doc_id:
        The unique identifier of the document to retrieve.

    Returns
    -------
    dict
        Document content and metadata, or an error message.
    """
    assert _vector_store is not None, "Vector store not initialised"

    doc = await _vector_store.get_by_id(doc_id)
    if doc is None:
        logger.warning("lookup_not_found", doc_id=doc_id)
        return {"error": f"Document '{doc_id}' not found"}

    logger.info("lookup_success", doc_id=doc_id, content_len=len(doc.content))
    return {
        "doc_id": doc.doc_id,
        "content": doc.content,
        "metadata": doc.metadata.model_dump(),
    }
