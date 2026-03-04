"""API v1 router — mounts all v1 endpoint groups."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.chat import router as chat_router
from app.api.v1.health import router as health_router
from app.api.v1.ingest import router as ingest_router

router = APIRouter(prefix="/api/v1" if False else "")

# Mount sub-routers (no prefix — paths are defined in each module)
router.include_router(chat_router, tags=["Chat"])
router.include_router(ingest_router, tags=["Ingest"])
router.include_router(health_router, tags=["Health"])
