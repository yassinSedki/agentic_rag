"""Top-level test fixtures for the Agentic RAG test suite.

Provides mock LLM, mock vector store, and test settings available to
all test modules. Import fixtures by placing conftest.py here — pytest
discovers it automatically.
"""

from __future__ import annotations

from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.schemas import Chunk, Document, DocumentMetadata
from app.vectorstore.base import VectorStoreAdapter


# ── Mock Settings ────────────────────────────────────────────────────────────
@pytest.fixture
def test_settings(monkeypatch):
    """Override settings for testing."""
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("CHROMA_HOST", "localhost")
    monkeypatch.setenv("CHROMA_PORT", "8001")
    monkeypatch.setenv("ENABLE_PII_REDACTION", "true")
    monkeypatch.setenv("ENABLE_MEMORY", "false")

    # Clear lru_cache
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ── Mock LLM ─────────────────────────────────────────────────────────────────
@pytest.fixture
def mock_llm():
    """Return a mock LLM that returns canned responses."""
    llm = MagicMock()
    response = MagicMock()
    response.content = "This is a mock LLM response."
    llm.ainvoke = AsyncMock(return_value=response)
    llm.astream = AsyncMock(return_value=iter([response]))
    return llm


# ── Mock Vector Store ────────────────────────────────────────────────────────
class MockVectorStoreAdapter(VectorStoreAdapter):
    """In-memory mock vector store for unit tests."""

    def __init__(self) -> None:
        self._store: dict[str, Document] = {}

    async def add_documents(
        self, chunks: list[Chunk], embeddings: list[list[float]]
    ) -> list[str]:
        ids = []
        for chunk in chunks:
            self._store[chunk.chunk_id] = Document(
                doc_id=chunk.doc_id,
                content=chunk.content,
                metadata=chunk.metadata,
            )
            ids.append(chunk.chunk_id)
        return ids

    async def similarity_search(
        self,
        query_embedding: list[float],
        k: int = 4,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[Document]:
        return list(self._store.values())[:k]

    async def get_by_id(self, doc_id: str) -> Optional[Document]:
        return self._store.get(doc_id)

    async def delete(self, doc_ids: list[str]) -> int:
        count = 0
        for did in doc_ids:
            if did in self._store:
                del self._store[did]
                count += 1
        return count

    async def health_check(self) -> bool:
        return True


@pytest.fixture
def mock_vector_store():
    """Return a mock in-memory vector store."""
    return MockVectorStoreAdapter()


# ── Sample Data ──────────────────────────────────────────────────────────────
@pytest.fixture
def sample_document():
    """Return a sample document for testing."""
    return Document(
        doc_id="test-doc-001",
        content="The refund policy allows returns within 30 days of purchase.",
        metadata=DocumentMetadata(source="policy.txt", tag="policy"),
    )


@pytest.fixture
def sample_chunks():
    """Return sample chunks for testing."""
    return [
        Chunk(
            chunk_id="chunk-001",
            doc_id="test-doc-001",
            content="The refund policy allows returns within 30 days.",
            metadata=DocumentMetadata(source="policy.txt", tag="policy"),
        ),
        Chunk(
            chunk_id="chunk-002",
            doc_id="test-doc-001",
            content="Items must be in original condition for a full refund.",
            metadata=DocumentMetadata(source="policy.txt", tag="policy"),
        ),
    ]
