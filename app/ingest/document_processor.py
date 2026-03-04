"""Document processor — orchestrates the full ingest pipeline.

Pipeline steps:
    1. **Load** — parse files / text into ``Document`` objects.
    2. **Clean** — normalise whitespace, strip boilerplate.
    3. **Chunk** — split into overlapping pieces with metadata + IDs.
    4. **Embed** — compute vector representations.
    5. **Upsert** — batch-write to the vector store.
"""

from __future__ import annotations

import time
from typing import Optional

import structlog

from app.core.schemas import Document
from app.embedding.embedding_factory import get_embedder
from app.ingest.utils.batch import batch_upsert
from app.ingest.utils.chunk_with_metadata import chunk_documents
from app.ingest.utils.clean import clean_documents
from app.ingest.utils.load_document import load_document
from app.vectorstore.base import VectorStoreAdapter

logger = structlog.get_logger()


class DocumentProcessor:
    """Orchestrates the end-to-end document ingestion pipeline."""

    def __init__(self, vector_store: VectorStoreAdapter) -> None:
        self._vector_store = vector_store
        self._embedder = get_embedder()

    async def process(
        self,
        source: str,
        filename: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Run the full pipeline on a single source.

        Parameters
        ----------
        source:
            File path or raw text.
        filename:
            Optional original filename.
        metadata:
            Extra metadata to attach to every chunk.

        Returns
        -------
        dict
            ``{"doc_ids": [...], "chunks_created": int, "status": "ok"}``.
        """
        start = time.monotonic()
        logger.info("ingest_started", source=filename or source[:50])

        # 1. Load
        documents: list[Document] = load_document(source, filename, metadata)
        logger.info("ingest_loaded", doc_count=len(documents))

        # 2. Clean
        documents = clean_documents(documents)
        logger.info("ingest_cleaned", doc_count=len(documents))

        # 3. Chunk
        chunks = chunk_documents(documents)
        logger.info("ingest_chunked", chunk_count=len(chunks))

        # 4. Embed
        texts = [c.content for c in chunks]
        embeddings = self._embedder.embed_documents(texts)
        logger.info("ingest_embedded", vector_count=len(embeddings))

        # 5. Upsert
        doc_ids = await batch_upsert(chunks, embeddings, self._vector_store)

        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "ingest_completed",
            chunks_created=len(doc_ids),
            elapsed_ms=elapsed_ms,
        )

        return {
            "doc_ids": doc_ids,
            "chunks_created": len(doc_ids),
            "status": "ok",
        }
