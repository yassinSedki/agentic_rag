"""Shared Pydantic schemas used across multiple layers.

These models establish the canonical shape of domain objects (documents,
chunks, sources) so that every layer speaks the same language.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Document / Chunk ─────────────────────────────────────────────────────────
class DocumentMetadata(BaseModel):
    """Metadata attached to every ingested document chunk."""

    source: str = ""
    tag: str = ""
    page: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    author: Optional[str] = None
    extra: dict[str, Any] = Field(default_factory=dict)


class Document(BaseModel):
    """A full or partial document flowing through the pipeline."""

    doc_id: str = ""
    content: str
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)


class Chunk(BaseModel):
    """A sized portion of a document, ready for embedding."""

    chunk_id: str
    doc_id: str
    content: str
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)


# ── Source reference ─────────────────────────────────────────────────────────
class Source(BaseModel):
    """Citation reference returned alongside an answer."""

    doc_id: str
    title: str = ""
    page: Optional[int] = None
    snippet: Optional[str] = None


# ── Answer envelope ──────────────────────────────────────────────────────────
class AnswerResponse(BaseModel):
    """Structured answer payload (non-streaming representation)."""

    answer: str
    sources: list[Source] = Field(default_factory=list)
    retrieval_score: float = 0.0
    latency_ms: int = 0
    token_count: Optional[int] = None
