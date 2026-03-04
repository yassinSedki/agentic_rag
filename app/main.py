"""FastAPI application factory with lifespan, middleware, and router registration.

Entry point::

    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.exceptions import (
    AuthenticationError,
    CircuitOpenError,
    IngestError,
    LLMTimeoutError,
    RAGException,
    RateLimitExceededError,
    RetrievalError,
)
from app.core.logging import setup_logging
from app.core.security import RequestIdMiddleware

logger = structlog.get_logger()


# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup / shutdown hooks."""
    settings = get_settings()
    setup_logging()
    logger.info(
        "app_starting",
        env=settings.app_env,
        host=settings.app_host,
        port=settings.app_port,
    )
    yield
    logger.info("app_shutting_down")


# ── App factory ──────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()

    application = FastAPI(
        title="Agentic RAG API",
        description="Production-grade Retrieval-Augmented Generation API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.app_env == "dev" else None,
        redoc_url="/redoc" if settings.app_env == "dev" else None,
    )

    # ── Middleware ────────────────────────────────────────────────────────
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(RequestIdMiddleware)

    # ── Exception handlers ───────────────────────────────────────────────
    @application.exception_handler(AuthenticationError)
    async def auth_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": exc.message})

    @application.exception_handler(RateLimitExceededError)
    async def rate_limit_handler(
        request: Request, exc: RateLimitExceededError
    ) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": exc.message})

    @application.exception_handler(LLMTimeoutError)
    async def llm_timeout_handler(
        request: Request, exc: LLMTimeoutError
    ) -> JSONResponse:
        return JSONResponse(status_code=504, content={"detail": exc.message})

    @application.exception_handler(CircuitOpenError)
    async def circuit_open_handler(
        request: Request, exc: CircuitOpenError
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": exc.message})

    @application.exception_handler(RetrievalError)
    async def retrieval_handler(
        request: Request, exc: RetrievalError
    ) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": exc.message})

    @application.exception_handler(IngestError)
    async def ingest_handler(request: Request, exc: IngestError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": exc.message})

    @application.exception_handler(RAGException)
    async def rag_handler(request: Request, exc: RAGException) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": exc.message})

    # ── Routes ───────────────────────────────────────────────────────────
    application.include_router(v1_router)

    # ── Prometheus metrics endpoint ──────────────────────────────────────
    metrics_app = make_asgi_app()
    application.mount("/metrics", metrics_app)

    return application


# Module-level app instance for uvicorn
app = create_app()
