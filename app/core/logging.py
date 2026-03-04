"""Structured JSON logging powered by *structlog*.

Call ``setup_logging()`` once at application startup (in ``main.py``).
Afterwards any module can obtain a logger via::

    import structlog
    logger = structlog.get_logger()
    logger.info("event_name", key="value")
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import get_settings


def setup_logging() -> None:
    """Configure structlog + stdlib logging for JSON output."""
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # ── Shared processors ────────────────────────────────────────────────
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # ── Structlog configuration ──────────────────────────────────────────
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # ── Stdlib handler ───────────────────────────────────────────────────
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer()
            if settings.app_env == "dev"
            else structlog.processors.JSONRenderer(),
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "httpx", "chromadb"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(**initial_binds: object) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger, optionally with initial key-value pairs."""
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(**initial_binds)
    return logger
