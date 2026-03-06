"""High-level VectorStore façade.

This class is the single vector store entrypoint used by the rest of
the application. Internally it delegates to a concrete backend
implementation (currently ChromaDB). To switch to a different vector
DB, update this class only.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.core.schemas import Chunk, Document
from app.vectorstore.base import VectorStoreAdapter
from app.vectorstore.chroma import ChromaAdapter


class VectorStore(VectorStoreAdapter):
    """Vector store façade that delegates to a concrete backend.

    The backend is selected from configuration (``Settings.vector_db``)
    and encapsulated inside this class so callers never depend on a
    specific implementation like Chroma.
    """

    def __init__(self) -> None:
        settings = get_settings()

        # For now we only support Chroma; extend this conditional when
        # adding new backends (e.g. QdrantAdapter).
        if settings.vector_db == "chroma":
            self._backend: VectorStoreAdapter = ChromaAdapter()
        else:
            raise ValueError(f"Unsupported vector_db backend: {settings.vector_db!r}")

    async def add_documents(
        self,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> list[str]:
        return await self._backend.add_documents(chunks, embeddings)

    async def similarity_search(
        self,
        query_embedding: list[float],
        k: int = 4,
        filters: dict | None = None,
    ) -> list[Document]:
        return await self._backend.similarity_search(
            query_embedding=query_embedding,
            k=k,
            filters=filters,
        )

    async def get_by_id(self, doc_id: str) -> Document | None:
        return await self._backend.get_by_id(doc_id)

    async def delete(self, doc_ids: list[str]) -> int:
        return await self._backend.delete(doc_ids)

    async def health_check(self) -> bool:
        return await self._backend.health_check()

