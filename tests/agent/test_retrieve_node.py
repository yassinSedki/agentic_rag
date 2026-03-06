"""Unit tests for the retrieval module (hybrid dense + BM25 + RRF)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.agent.nodes.retrieve import retrieve, set_vector_store
from app.core.schemas import Document, DocumentMetadata


class _FakeEmbedder:
    def embed_query(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_retrieve_returns_top_k_results(monkeypatch):
    """Retrieve should return up to TOP_K fused documents."""
    # Ensure deterministic TOP_K for test
    monkeypatch.setenv("TOP_K", "2")
    from app.core.config import get_settings

    get_settings.cache_clear()

    # Mock embedder
    monkeypatch.setattr("app.agent.nodes.retrieve.get_embedder", lambda: _FakeEmbedder())

    # Mock vector store dense search
    mock_vs = AsyncMock()
    mock_vs.similarity_search = AsyncMock(
        return_value=[
            Document(
                doc_id="doc-1",
                content="Refunds within 30 days of purchase.",
                metadata=DocumentMetadata(source="policy.txt", tag="policy"),
            ),
            Document(
                doc_id="doc-2",
                content="Items must be in original condition.",
                metadata=DocumentMetadata(source="policy.txt", tag="policy"),
            ),
            Document(
                doc_id="doc-3",
                content="Shipping is non-refundable.",
                metadata=DocumentMetadata(source="policy.txt", tag="policy"),
            ),
        ]
    )

    set_vector_store(mock_vs)

    out = await retrieve({"question": "What is the refund policy?"})
    assert "retrieved_docs" in out
    assert len(out["retrieved_docs"]) == 2
    assert all("doc_id" in d and "content" in d for d in out["retrieved_docs"])


@pytest.mark.asyncio
async def test_retrieve_empty_dense_results_returns_empty_list(monkeypatch):
    """Empty vector DB results should produce empty retrieved_docs."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr("app.agent.nodes.retrieve.get_embedder", lambda: _FakeEmbedder())

    mock_vs = AsyncMock()
    mock_vs.similarity_search = AsyncMock(return_value=[])
    set_vector_store(mock_vs)

    out = await retrieve({"question": "Any policy?"})
    assert out["retrieved_docs"] == []

