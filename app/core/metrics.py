"""Prometheus metrics instruments.

Import this module and use the pre-defined counters / histograms / gauges
throughout the application.  The ``/metrics`` endpoint is exposed via
``prometheus_client`` ASGI middleware in ``main.py``.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ── Request-level ────────────────────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "rag_requests_total",
    "Total API requests",
    labelnames=["endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "rag_request_latency_seconds",
    "End-to-end request latency",
    labelnames=["endpoint"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

# ── LLM ──────────────────────────────────────────────────────────────────────
LLM_LATENCY = Histogram(
    "rag_llm_latency_seconds",
    "Ollama LLM call latency",
    labelnames=["model"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

# ── Retrieval ────────────────────────────────────────────────────────────────
RETRIEVAL_LATENCY = Histogram(
    "rag_retrieval_latency_seconds",
    "Vector DB query time",
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

RETRIEVAL_EMPTY = Counter(
    "rag_retrieval_empty_total",
    "Times retrieval returned no relevant documents",
)

# ── Connections ──────────────────────────────────────────────────────────────
ACTIVE_CONNECTIONS = Gauge(
    "rag_active_connections",
    "Currently open SSE connections",
)

# ── Circuit Breaker ──────────────────────────────────────────────────────────
CIRCUIT_STATE = Gauge(
    "rag_circuit_breaker_state",
    "Circuit breaker state (0=closed 1=open 2=half-open)",
    labelnames=["service"],
)
