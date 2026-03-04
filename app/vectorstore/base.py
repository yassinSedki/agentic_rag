"""Abstract vector store interface.

Concrete implementations (ChromaDB, Qdrant, …) must subclass
``VectorStoreAdapter`` and implement every abstract method.
This adapter pattern allows swapping backends without changing any
upstream code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from app.core.schemas import Chunk, Document


class VectorStoreAdapter(ABC):
    """Abstract base class for vector store backends."""

    @abstractmethod
    async def add_documents(
        self,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> list[str]:
        """Upsert embedded chunks into the store.

        Parameters
        ----------
        chunks:
            Document chunks with metadata.
        embeddings:
            Pre-computed embedding vectors aligned with *chunks*.

        Returns
        -------
        list[str]
            IDs of the stored chunks.
        """

    @abstractmethod
    async def similarity_search(
        self,
        query_embedding: list[float],
        k: int = 4,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[Document]:
        """Return the top-*k* documents most similar to the query embedding.

        Parameters
        ----------
        query_embedding:
            Vector representation of the query.
        k:
            Number of results to return.
        filters:
            Optional metadata filters (e.g., ``{"tag": "policy"}``).

        Returns
        -------
        list[Document]
            Ranked documents with metadata.
        """

    @abstractmethod
    async def get_by_id(self, doc_id: str) -> Optional[Document]:
        """Retrieve a single document by its *doc_id*.

        Returns ``None`` if not found.
        """

    @abstractmethod
    async def delete(self, doc_ids: list[str]) -> int:
        """Delete documents by their IDs.

        Returns the number of successfully deleted documents.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """Return ``True`` if the backend is reachable."""
