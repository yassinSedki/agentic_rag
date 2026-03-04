"""ChromaDB adapter implementing ``VectorStoreAdapter``.

Uses the ChromaDB ``HttpClient`` to communicate with a running Chroma
server.  All calls are wrapped with the circuit breaker for resilience.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import chromadb
import structlog

from app.core.circuit_breaker import circuit_breaker
from app.core.config import get_settings
from app.core.schemas import Chunk, Document, DocumentMetadata
from app.vectorstore.base import VectorStoreAdapter

logger = structlog.get_logger()


class ChromaAdapter(VectorStoreAdapter):
    """Concrete vector store backed by **ChromaDB** over HTTP."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
        )
        self._collection_name = settings.chroma_collection
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "chroma_adapter_initialized",
            host=settings.chroma_host,
            port=settings.chroma_port,
            collection=self._collection_name,
        )

    @circuit_breaker(service="chroma")
    async def add_documents(
        self,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> list[str]:
        """Upsert chunks into ChromaDB."""
        ids = [c.chunk_id for c in chunks]
        documents = [c.content for c in chunks]
        metadatas = [
            {
                "doc_id": c.doc_id,
                "source": c.metadata.source,
                "tag": c.metadata.tag,
                "page": c.metadata.page or 0,
                "timestamp": c.metadata.timestamp.isoformat(),
            }
            for c in chunks
        ]

        # ChromaDB client is synchronous — run in executor
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: self._collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            ),
        )

        logger.info("chroma_upserted", count=len(ids))
        return ids

    @circuit_breaker(service="chroma")
    async def similarity_search(
        self,
        query_embedding: list[float],
        k: int = 4,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[Document]:
        """Query ChromaDB for similar documents."""
        loop = asyncio.get_running_loop()

        where = filters if filters else None
        results = await loop.run_in_executor(
            None,
            lambda: self._collection.query(
                query_embeddings=[query_embedding],
                n_results=k,
                where=where,
                include=["documents", "metadatas", "distances"],
            ),
        )

        documents: list[Document] = []
        if results and results["documents"]:
            for i, doc_text in enumerate(results["documents"][0]):
                meta_raw = results["metadatas"][0][i] if results["metadatas"] else {}
                doc = Document(
                    doc_id=meta_raw.get("doc_id", ""),
                    content=doc_text or "",
                    metadata=DocumentMetadata(
                        source=meta_raw.get("source", ""),
                        tag=meta_raw.get("tag", ""),
                        page=meta_raw.get("page"),
                    ),
                )
                documents.append(doc)

        return documents

    @circuit_breaker(service="chroma")
    async def get_by_id(self, doc_id: str) -> Optional[Document]:
        """Fetch a single document by chunk ID."""
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            None,
            lambda: self._collection.get(
                ids=[doc_id],
                include=["documents", "metadatas"],
            ),
        )

        if not results or not results["documents"]:
            return None

        meta_raw = results["metadatas"][0] if results["metadatas"] else {}
        return Document(
            doc_id=doc_id,
            content=results["documents"][0] or "",
            metadata=DocumentMetadata(
                source=meta_raw.get("source", ""),
                tag=meta_raw.get("tag", ""),
                page=meta_raw.get("page"),
            ),
        )

    @circuit_breaker(service="chroma")
    async def delete(self, doc_ids: list[str]) -> int:
        """Delete documents by IDs from ChromaDB."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: self._collection.delete(ids=doc_ids),
        )
        logger.info("chroma_deleted", count=len(doc_ids))
        return len(doc_ids)

    @circuit_breaker(service="chroma")
    async def health_check(self) -> bool:
        """Ping ChromaDB heartbeat."""
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, self._client.heartbeat)
            return True
        except Exception:
            logger.error("chroma_health_check_failed")
            return False
