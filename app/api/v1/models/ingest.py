"""Pydantic schemas for the ``/ingest`` endpoint."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    """Request body for POST /ingest."""

    text: Optional[str] = None
    filename: Optional[str] = None
    content_base64: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class IngestResponse(BaseModel):
    """Response body for POST /ingest."""

    doc_ids: list[str] = Field(default_factory=list)
    chunks_created: int = 0
    status: str = "ok"
