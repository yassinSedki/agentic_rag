"""Lightweight circuit breaker built on *tenacity*.

States:
    CLOSED   — normal operation, failures are counted.
    OPEN     — after ``threshold`` consecutive failures; all calls are
               rejected immediately for ``reset_s`` seconds.
    HALF-OPEN — after the reset window, a single probe call is allowed;
                success → CLOSED, failure → OPEN again.

Usage::

    from app.core.circuit_breaker import circuit_breaker

    @circuit_breaker(service="ollama")
    async def call_llm(prompt: str) -> str:
        ...
"""

from __future__ import annotations

import asyncio
import time
from enum import IntEnum
from functools import wraps
from typing import Any, Callable, TypeVar

import structlog

from app.core.config import get_settings
from app.core.exceptions import CircuitOpenError
from app.core.metrics import CIRCUIT_STATE

logger = structlog.get_logger()

F = TypeVar("F", bound=Callable[..., Any])


class State(IntEnum):
    CLOSED = 0
    OPEN = 1
    HALF_OPEN = 2


class CircuitBreaker:
    """In-process circuit breaker with async support."""

    def __init__(self, service: str, threshold: int, reset_s: int) -> None:
        self.service = service
        self.threshold = threshold
        self.reset_s = reset_s
        self._state = State.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> State:
        if self._state == State.OPEN:
            if time.monotonic() - self._last_failure_time >= self.reset_s:
                self._state = State.HALF_OPEN
                CIRCUIT_STATE.labels(service=self.service).set(State.HALF_OPEN)
        return self._state

    async def _on_success(self) -> None:
        async with self._lock:
            self._failure_count = 0
            self._state = State.CLOSED
            CIRCUIT_STATE.labels(service=self.service).set(State.CLOSED)

    async def _on_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self.threshold:
                self._state = State.OPEN
                CIRCUIT_STATE.labels(service=self.service).set(State.OPEN)
                logger.warning(
                    "circuit_breaker_opened",
                    service=self.service,
                    failure_count=self._failure_count,
                )

    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute *func* through the circuit breaker."""
        current = self.state
        if current == State.OPEN:
            raise CircuitOpenError(
                f"Circuit breaker for '{self.service}' is OPEN — request rejected"
            )

        try:
            result = await func(*args, **kwargs)
        except Exception:
            await self._on_failure()
            raise
        else:
            await self._on_success()
            return result


# ── Registry of named breakers ───────────────────────────────────────────────
_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(service: str) -> CircuitBreaker:
    """Get or create a ``CircuitBreaker`` for *service*."""
    if service not in _breakers:
        settings = get_settings()
        _breakers[service] = CircuitBreaker(
            service=service,
            threshold=settings.circuit_breaker_threshold,
            reset_s=settings.circuit_breaker_reset_s,
        )
    return _breakers[service]


def circuit_breaker(service: str) -> Callable[[F], F]:
    """Decorator that wraps an async function with a circuit breaker.

    Example::

        @circuit_breaker(service="ollama")
        async def call_llm(prompt: str) -> str: ...
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            breaker = get_breaker(service)
            return await breaker.call(func, *args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
