"""Security utilities: API-key check, rate limiting, prompt sanitizer, PII redactor.

These are composed as FastAPI middleware or dependencies in ``main.py``.
"""

from __future__ import annotations

import re
from typing import Optional

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError

logger = structlog.get_logger()




# ── Prompt Injection Sanitizer ───────────────────────────────────────────────
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"<\|?system\|?>", re.IGNORECASE),
    re.compile(r"ASSISTANT\s*:", re.IGNORECASE),
    re.compile(r"###\s*(instruction|system)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+", re.IGNORECASE),
    re.compile(r"forget\s+(everything|all)", re.IGNORECASE),
]


def sanitize_prompt(text: str) -> str:
    """Strip known prompt-injection patterns from *text*.

    Returns the sanitised text.  Any match is logged as a warning.
    """
    cleaned = text
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(cleaned):
            logger.warning("prompt_injection_detected", pattern=pattern.pattern)
            cleaned = pattern.sub("", cleaned)
    return cleaned.strip()


# ── PII Redactor ─────────────────────────────────────────────────────────────
_PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
    "phone": re.compile(
        r"(\+?\d{1,3}[-.\s]?)?(\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{3,4}"
    ),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
}


def redact_pii(text: str) -> str:
    """Replace PII patterns in *text* with ``[REDACTED]``.

    Only active when ``ENABLE_PII_REDACTION`` is ``True`` in settings.
    """
    settings = get_settings()
    if not settings.enable_pii_redaction:
        return text

    result = text
    for pii_type, pattern in _PII_PATTERNS.items():
        if pattern.search(result):
            logger.info("pii_redacted", pii_type=pii_type)
            result = pattern.sub("[REDACTED]", result)
    return result


# ── Request-ID Middleware ────────────────────────────────────────────────────
class RequestIdMiddleware(BaseHTTPMiddleware):
    """Inject ``X-Request-ID`` into every request / response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        import uuid

        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        # Bind to structlog context for the duration of this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ── Auth Error Middleware (fallback for non-dependency routes) ────────────────
class AuthErrorMiddleware(BaseHTTPMiddleware):
    """Catch ``AuthenticationError`` and return 401."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            return await call_next(request)
        except AuthenticationError as exc:
            return JSONResponse(
                status_code=401,
                content={"detail": exc.message},
            )
