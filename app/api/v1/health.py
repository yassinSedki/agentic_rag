"""Health and readiness endpoints.

- ``GET /health`` — liveness probe (always responds if the process is running).
- ``GET /ready``  — readiness probe (checks Ollama + Vector DB connectivity).
"""

from __future__ import annotations

import httpx
import structlog
from fastapi import APIRouter

from app.core.config import get_settings
from app.vectorstore import VectorStore

logger = structlog.get_logger()

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """Liveness probe — indicates the service process is running."""
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> dict:
    """Readiness probe — checks connectivity to Ollama and ChromaDB.

    Returns 200 with component statuses.  Each component reports
    ``"up"`` or ``"down"``.
    """
    settings = get_settings()
    statuses: dict[str, str] = {}

    # Check Ollama
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/version")
            statuses["ollama"] = "up" if resp.status_code == 200 else "down"
    except Exception:
        statuses["ollama"] = "down"

    # Check ChromaDB
    try:
        adapter = VectorStore()
        is_healthy = await adapter.health_check()
        statuses["vectordb"] = "up" if is_healthy else "down"
    except Exception:
        statuses["vectordb"] = "down"

    all_up = all(s == "up" for s in statuses.values())
    logger.info("readiness_check", statuses=statuses, all_up=all_up)

    return {
        "status": "ok" if all_up else "degraded",
        **statuses,
    }
