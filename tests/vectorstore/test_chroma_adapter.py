"""Tests for the Chroma adapter (using mock vector store)."""

from __future__ import annotations

import pytest

from app.core.schemas import Chunk, DocumentMetadata


class TestMockVectorStoreAdapter:
    """Tests using the mock vector store adapter from conftest."""

    @pytest.mark.asyncio
    async def test_add_and_search(self, mock_vector_store, sample_chunks):
        embeddings = [[0.1, 0.2, 0.3]] * len(sample_chunks)
        ids = await mock_vector_store.add_documents(sample_chunks, embeddings)
        assert len(ids) == len(sample_chunks)

        results = await mock_vector_store.similarity_search([0.1, 0.2, 0.3], k=2)
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_get_by_id(self, mock_vector_store, sample_chunks):
        embeddings = [[0.1, 0.2, 0.3]] * len(sample_chunks)
        await mock_vector_store.add_documents(sample_chunks, embeddings)

        doc = await mock_vector_store.get_by_id(sample_chunks[0].chunk_id)
        assert doc is not None
        assert doc.content == sample_chunks[0].content

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, mock_vector_store):
        doc = await mock_vector_store.get_by_id("nonexistent-id")
        assert doc is None

    @pytest.mark.asyncio
    async def test_delete(self, mock_vector_store, sample_chunks):
        embeddings = [[0.1, 0.2, 0.3]] * len(sample_chunks)
        ids = await mock_vector_store.add_documents(sample_chunks, embeddings)

        deleted = await mock_vector_store.delete([ids[0]])
        assert deleted == 1

    @pytest.mark.asyncio
    async def test_health_check(self, mock_vector_store):
        assert await mock_vector_store.health_check() is True
