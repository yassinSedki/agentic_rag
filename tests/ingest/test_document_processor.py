"""Tests for the document processing pipeline."""

from __future__ import annotations

import pytest

from app.ingest.utils.chunk_with_metadata import chunk_documents
from app.ingest.utils.clean import clean_documents
from app.ingest.utils.load_document import load_document
from app.core.schemas import Document, DocumentMetadata


class TestLoadDocument:
    """Tests for document loading."""

    def test_load_raw_text(self):
        docs = load_document("Hello, this is a test document.")
        assert len(docs) == 1
        assert "test document" in docs[0].content

    def test_load_with_filename(self):
        docs = load_document("Content here", filename="test.txt")
        assert docs[0].metadata.source == "test.txt"


class TestCleanDocuments:
    """Tests for document cleaning."""

    def test_clean_empty_docs(self):
        docs = [Document(content="   ", metadata=DocumentMetadata())]
        result = clean_documents(docs)
        assert len(result) == 0  # Empty after cleaning

    def test_clean_normalizes_whitespace(self):
        docs = [
            Document(
                content="Hello   world\n\n\n\nParagraph two",
                metadata=DocumentMetadata(source="test"),
            )
        ]
        result = clean_documents(docs)
        assert len(result) == 1
        assert "   " not in result[0].content


class TestChunkDocuments:
    """Tests for document chunking."""

    def test_chunk_creates_ids(self):
        docs = [
            Document(
                doc_id="doc1",
                content="A " * 300,  # 600 chars
                metadata=DocumentMetadata(source="test"),
            )
        ]
        chunks = chunk_documents(docs, chunk_size=100, chunk_overlap=10)
        assert len(chunks) > 1
        # All chunks should have unique IDs
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids))

    def test_chunk_preserves_metadata(self):
        meta = DocumentMetadata(source="policy.txt", tag="test")
        docs = [Document(doc_id="doc1", content="Short text", metadata=meta)]
        chunks = chunk_documents(docs, chunk_size=500, chunk_overlap=50)
        assert len(chunks) >= 1
        assert chunks[0].metadata.source == "policy.txt"
