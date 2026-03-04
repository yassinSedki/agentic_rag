"""Batch upsert — push chunks and embeddings to the vector store.

Deduplicates by ``chunk_id`` before upserting to avoid storing
identical chunks multiple times.
"""

from __future__ import annotations

import structlog

from app.core.schemas import Chunk
from app.vectorstore.base import VectorStoreAdapter

logger = structlog.get_logger()

# Maximum number of chunks per batch (prevents OOM on large docs)
_BATCH_SIZE = 100


async def batch_upsert(
    chunks: list[Chunk],
    embeddings: list[list[float]],
    adapter: VectorStoreAdapter,
) -> list[str]:
    """Deduplicate and upsert chunks in batches.

    Parameters
    ----------
    chunks:
        Chunks produced by the chunking step.
    embeddings:
        Pre-computed embedding vectors aligned 1:1 with *chunks*.
    adapter:
        The vector store backend to write into.

    Returns
    -------
    list[str]
        IDs of all upserted chunks.
    """
    # Deduplicate by chunk_id (keep first occurrence)
    seen: set[str] = set()
    unique_chunks: list[Chunk] = []
    unique_embeddings: list[list[float]] = []

    for chunk, emb in zip(chunks, embeddings):
        if chunk.chunk_id not in seen:
            seen.add(chunk.chunk_id)
            unique_chunks.append(chunk)
            unique_embeddings.append(emb)

    dedup_count = len(chunks) - len(unique_chunks)
    if dedup_count:
        logger.info("batch_dedup", removed=dedup_count, remaining=len(unique_chunks))

    # Upsert in batches
    all_ids: list[str] = []
    for i in range(0, len(unique_chunks), _BATCH_SIZE):
        batch_chunks = unique_chunks[i : i + _BATCH_SIZE]
        batch_embeds = unique_embeddings[i : i + _BATCH_SIZE]
        ids = await adapter.add_documents(batch_chunks, batch_embeds)
        all_ids.extend(ids)
        logger.info(
            "batch_upserted",
            batch_num=i // _BATCH_SIZE + 1,
            count=len(batch_chunks),
        )

    return all_ids
