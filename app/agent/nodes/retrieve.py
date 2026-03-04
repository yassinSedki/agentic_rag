"""Retrieve node — hybrid retrieval (dense + BM25) with RRF fusion.

Steps:
    1. Embed the rewritten query.
    2. Dense vector search via the vector store adapter.
    3. In-process BM25 keyword search on retrieved candidates.
    4. Fuse with Reciprocal Rank Fusion (RRF).
"""

from __future__ import annotations

import time

import structlog
from rank_bm25 import BM25Okapi

from app.agent.state import AgentState
from app.core.config import get_settings
from app.core.metrics import RETRIEVAL_LATENCY
from app.embedding.embedding_factory import get_embedder
from app.vectorstore.base import VectorStoreAdapter
from app.vectorstore.reranker import ScoredItem, reciprocal_rank_fusion

logger = structlog.get_logger()

# Module-level reference — wired by the graph builder
_vector_store: VectorStoreAdapter | None = None


def set_vector_store(vs: VectorStoreAdapter) -> None:
    """Wire the vector store instance (called once at startup)."""
    global _vector_store
    _vector_store = vs


async def retrieve(state: AgentState) -> dict:
    """Perform hybrid retrieval and return ranked documents."""
    assert _vector_store is not None, "Vector store not initialised — call set_vector_store()"

    settings = get_settings()
    query = state.get("rewritten_query", state["question"])
    start = time.monotonic()

    # 1. Embed query
    embedder = get_embedder()
    query_embedding = embedder.embed_query(query)

    # 2. Dense search
    dense_docs = await _vector_store.similarity_search(
        query_embedding=query_embedding,
        k=settings.top_k * 2,  # over-fetch for fusion
    )

    # 3. BM25 keyword search (in-process on dense candidates)
    bm25_results: list[ScoredItem] = []
    if dense_docs:
        tokenized_corpus = [doc.content.lower().split() for doc in dense_docs]
        bm25 = BM25Okapi(tokenized_corpus)
        bm25_scores = bm25.get_scores(query.lower().split())

        bm25_results = [
            ScoredItem(
                item_id=doc.doc_id,
                content=doc.content,
                metadata=doc.metadata.model_dump(),
                score=float(score),
            )
            for doc, score in zip(dense_docs, bm25_scores)
        ]
        bm25_results.sort(key=lambda x: x.score, reverse=True)

    # Dense results as ScoredItems (score = rank-based)
    dense_scored = [
        ScoredItem(
            item_id=doc.doc_id,
            content=doc.content,
            metadata=doc.metadata.model_dump(),
            score=1.0 / (i + 1),  # rank-based score
        )
        for i, doc in enumerate(dense_docs)
    ]

    # 4. RRF fusion
    fused = reciprocal_rank_fusion(dense_scored, bm25_results)
    top_results = fused[: settings.top_k]

    # Convert back to serializable dicts
    retrieved_docs = [
        {
            "doc_id": item.item_id,
            "content": item.content,
            "metadata": item.metadata,
            "score": item.score,
        }
        for item in top_results
    ]

    elapsed = time.monotonic() - start
    RETRIEVAL_LATENCY.observe(elapsed)

    logger.info(
        "retrieval_complete",
        query=query[:80],
        dense_count=len(dense_docs),
        fused_count=len(retrieved_docs),
        latency_ms=int(elapsed * 1000),
    )

    return {"retrieved_docs": retrieved_docs}
