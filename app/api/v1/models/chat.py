"""Pydantic schemas for the ``/chat`` endpoint.

Defines request, streaming event types, and related models.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request body for POST /chat."""

    question: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str = Field(default="default")
    metadata: Optional[dict[str, Any]] = None
    history: Optional[list[dict[str, str]]] = None


class Source(BaseModel):
    """Citation source included in the done event."""

    doc_id: str
    title: str = ""
    page: Optional[int] = None
    snippet: Optional[str] = None


class ChatTokenEvent(BaseModel):
    """SSE event for a partial answer token."""

    type: Literal["token"] = "token"
    chunk: str


class ChatDoneEvent(BaseModel):
    """SSE event when streaming is complete."""

    type: Literal["done"] = "done"
    sources: list[Source] = Field(default_factory=list)
    latency_ms: int = 0
    token_count: Optional[int] = None
    retrieval_score: float = 0.0


class ChatErrorEvent(BaseModel):
    """SSE event for errors."""

    type: Literal["error"] = "error"
    code: str
    message: str
