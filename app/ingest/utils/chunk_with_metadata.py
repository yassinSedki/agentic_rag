"""Chunking with metadata — split documents into overlapping chunks.

Each chunk receives a deterministic ``chunk_id`` derived from the SHA-256
hash of its content, ensuring deduplication on re-ingestion.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings
from app.core.schemas import Chunk, Document


def chunk_documents(
    documents: list[Document],
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> list[Chunk]:
    """Split documents into overlapping chunks with metadata.

    Parameters
    ----------
    documents:
        Cleaned documents to split.
    chunk_size:
        Characters per chunk (defaults to ``Settings.chunk_size``).
    chunk_overlap:
        Overlap between consecutive chunks (defaults to ``Settings.chunk_overlap``).

    Returns
    -------
    list[Chunk]
        Flat list of chunks with deterministic IDs and inherited metadata.
    """
    settings = get_settings()
    _chunk_size = chunk_size or settings.chunk_size
    _chunk_overlap = chunk_overlap or settings.chunk_overlap

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=_chunk_size,
        chunk_overlap=_chunk_overlap,
        separators=["\n\n", "\n", ".", " "],
        length_function=len,
    )

    chunks: list[Chunk] = []
    for doc in documents:
        texts = splitter.split_text(doc.content)
        for text in texts:
            chunk_id = _compute_chunk_id(text, doc.doc_id)
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    doc_id=doc.doc_id or doc.metadata.source,
                    content=text,
                    metadata=doc.metadata,
                )
            )

    return chunks


def _compute_chunk_id(content: str, doc_id: str) -> str:
    """Compute a deterministic chunk ID using SHA-256.

    The hash is based on the document ID + chunk content, ensuring
    identical chunks from the same source produce the same ID.
    """
    payload = f"{doc_id}:{content}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
