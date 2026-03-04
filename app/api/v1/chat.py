"""Chat endpoint — SSE streaming responses via the LangGraph agent.

POST /chat accepts a ``ChatRequest``, runs the agent graph, and streams
the answer back as Server-Sent Events.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from app.agent.graph import build_graph
from app.api.v1.models.chat import (
    ChatDoneEvent,
    ChatErrorEvent,
    ChatRequest,
    ChatTokenEvent,
    Source,
)
from app.core.config import get_settings
from app.core.metrics import ACTIVE_CONNECTIONS, REQUEST_COUNT, REQUEST_LATENCY
from app.core.security import verify_api_key

logger = structlog.get_logger()

router = APIRouter()


async def _stream_response(
    request: ChatRequest,
    request_id: str,
) -> AsyncGenerator[str, None]:
    """Run the agent graph and yield SSE events."""
    start = time.monotonic()
    settings = get_settings()

    ACTIVE_CONNECTIONS.inc()
    try:
        # Build and run graph
        graph = build_graph()

        initial_state = {
            "question": request.question,
            "conversation_id": request.conversation_id,
            "request_id": request_id,
            "history": request.history or [],
            "metadata": request.metadata or {},
        }

        result = await graph.ainvoke(initial_state)

        # Stream the final answer in chunks
        final_answer = result.get("final_answer", "")
        source_ids = result.get("source_ids", [])
        retrieval_score = result.get("retrieval_score", 0.0)
        error = result.get("error")

        if error and not final_answer:
            # Error path
            event = ChatErrorEvent(
                code="AGENT_ERROR",
                message=error,
            )
            yield f"data: {event.model_dump_json()}\n\n"
            REQUEST_COUNT.labels(endpoint="/chat", status="error").inc()
            return

        # Stream answer in token-sized chunks
        chunk_size = 50  # characters per SSE event
        token_count = 0
        for i in range(0, len(final_answer), chunk_size):
            chunk_text = final_answer[i : i + chunk_size]
            event = ChatTokenEvent(chunk=chunk_text)
            yield f"data: {event.model_dump_json()}\n\n"
            token_count += 1

        # Done event
        elapsed_ms = int((time.monotonic() - start) * 1000)
        sources = [Source(doc_id=sid) for sid in source_ids]
        done_event = ChatDoneEvent(
            sources=sources,
            latency_ms=elapsed_ms,
            token_count=token_count,
            retrieval_score=retrieval_score,
        )
        yield f"data: {done_event.model_dump_json()}\n\n"

        REQUEST_COUNT.labels(endpoint="/chat", status="success").inc()
        REQUEST_LATENCY.labels(endpoint="/chat").observe(
            time.monotonic() - start
        )

        logger.info(
            "chat_complete",
            request_id=request_id,
            latency_ms=elapsed_ms,
            token_count=token_count,
        )

    except Exception as exc:
        logger.error("chat_stream_error", error=str(exc), request_id=request_id)
        event = ChatErrorEvent(
            code="INTERNAL_ERROR",
            message=str(exc),
        )
        yield f"data: {event.model_dump_json()}\n\n"
        REQUEST_COUNT.labels(endpoint="/chat", status="error").inc()

    finally:
        ACTIVE_CONNECTIONS.dec()


@router.post("/chat")
async def chat(
    request: Request,
    body: ChatRequest,
    api_key: str = Depends(verify_api_key),
) -> EventSourceResponse:
    """Stream an agent response via Server-Sent Events.

    Accepts a ``ChatRequest`` with a question and optional context,
    runs the LangGraph agent, and returns the answer as an SSE stream.
    """
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        conversation_id=body.conversation_id,
    )

    logger.info("chat_request", question=body.question[:100])

    return EventSourceResponse(
        _stream_response(body, request_id),
        media_type="text/event-stream",
    )
