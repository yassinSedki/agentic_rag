"""VectorStore test fixtures."""

import pytest


@pytest.fixture
def mock_chroma_collection():
    """Return a mock ChromaDB collection."""
    from unittest.mock import MagicMock

    collection = MagicMock()
    collection.upsert = MagicMock()
    collection.query = MagicMock(
        return_value={
            "documents": [["doc content"]],
            "metadatas": [[{"doc_id": "1", "source": "test.txt", "tag": "", "page": 0}]],
            "distances": [[0.1]],
        }
    )
    collection.get = MagicMock(
        return_value={
            "documents": ["doc content"],
            "metadatas": [{"doc_id": "1", "source": "test.txt", "tag": "", "page": 0}],
        }
    )
    return collection
