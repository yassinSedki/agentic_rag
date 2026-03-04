"""Custom exception hierarchy for the Agentic RAG system.

Every domain-specific error inherits from ``RAGException`` so that a single
handler at the API layer can translate them to structured HTTP responses.
"""

from __future__ import annotations

from typing import Any


# ── Base ─────────────────────────────────────────────────────────────────────
class RAGException(Exception):
    """Root exception for the Agentic RAG domain."""

    def __init__(self, message: str = "An error occurred", detail: Any = None) -> None:
        self.message = message
        self.detail = detail
        super().__init__(self.message)


# ── Retrieval ────────────────────────────────────────────────────────────────
class RetrievalError(RAGException):
    """Raised when the vector store or retrieval pipeline fails."""


class RetrievalEmptyError(RAGException):
    """Raised when no relevant documents are found."""


# ── LLM ──────────────────────────────────────────────────────────────────────
class LLMTimeoutError(RAGException):
    """Raised when the LLM call exceeds the configured timeout."""


class LLMError(RAGException):
    """Generic LLM error (non-timeout)."""


# ── Grounding ────────────────────────────────────────────────────────────────
class GroundingFailedError(RAGException):
    """Raised when the grounding check rejects the answer as unsupported."""


# ── Validation ───────────────────────────────────────────────────────────────
class OutputValidationError(RAGException):
    """Raised when the generated answer fails Pydantic schema parsing."""


# ── Circuit Breaker ──────────────────────────────────────────────────────────
class CircuitOpenError(RAGException):
    """Raised when the circuit breaker is in OPEN state, rejecting requests."""


# ── Ingest ───────────────────────────────────────────────────────────────────
class IngestError(RAGException):
    """Raised during document ingestion failures."""


class UnsupportedFileTypeError(IngestError):
    """Raised when an unsupported file format is submitted for ingestion."""


# ── Security ─────────────────────────────────────────────────────────────────
class AuthenticationError(RAGException):
    """Raised when API key validation fails."""


class RateLimitExceededError(RAGException):
    """Raised when a client exceeds the configured rate limit."""
