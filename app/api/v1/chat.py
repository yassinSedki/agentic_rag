"""Chat endpoint — SSE streaming responses via the LangGraph agent.

POST /chat accepts a ``ChatRequest``, runs the agent graph, and streams
the answer back as Server-Sent Events.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from dataclasses import dataclass
from typing import AsyncGenerator

import structlog
from fastapi import APIRouter, Request
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
from app.core.exceptions import LLMTimeoutError
from app.core.metrics import ACTIVE_CONNECTIONS, LLM_LATENCY, REQUEST_COUNT, REQUEST_LATENCY
from app.llm.llm_factory import get_chat_llm
from app.agent.memory.store import get_memory_store

logger = structlog.get_logger()

router = APIRouter()


@dataclass(frozen=True)
class _StreamFailure:
    code: str
    message: str


async def _stream_text_as_events(text: str, chunk_size: int = 50) -> AsyncGenerator[str, None]:
    """Fallback streaming for precomputed answers (non-LLM)."""
    for i in range(0, len(text), chunk_size):
        chunk_text = text[i : i + chunk_size]
        if not chunk_text:
            continue
        event = ChatTokenEvent(chunk=chunk_text)
        yield f"data: {event.model_dump_json()}\n\n"


async def _produce_llm_chunks(
    prompt: str,
    queue: "asyncio.Queue[str | _StreamFailure | None]",
) -> None:
    """Run the LLM streaming call and push chunks into a queue."""
    llm = get_chat_llm()
    settings = get_settings()
    start = time.monotonic()
    try:
        async for chunk in llm.astream(prompt):
            text = getattr(chunk, "content", None)
            if text:
                await queue.put(text)
    except LLMTimeoutError as exc:
        await queue.put(_StreamFailure(code="LLM_TIMEOUT", message=str(exc)))
    except Exception as exc:
        await queue.put(_StreamFailure(code="LLM_ERROR", message=str(exc)))
    finally:
        elapsed = time.monotonic() - start
        LLM_LATENCY.labels(model=settings.ollama_model).observe(elapsed)
        await queue.put(None)


def _sources_from_state(source_ids: list[str], retrieved_docs: list[dict] | None) -> list[Source]:
    """Build Source objects with optional snippets from retrieved docs."""
    if not source_ids:
        return []
    docs = retrieved_docs or []
    by_id: dict[str, dict] = {}
    for d in docs:
        if isinstance(d, dict) and d.get("doc_id"):
            by_id[str(d["doc_id"])] = d

    sources: list[Source] = []
    for sid in source_ids:
        d = by_id.get(sid, {})
        meta = d.get("metadata") if isinstance(d, dict) else {}
        page = None
        title = ""
        if isinstance(meta, dict):
            page = meta.get("page")
            title = meta.get("source", "") or ""
        snippet = (d.get("content", "")[:240] if isinstance(d, dict) else "") or None
        sources.append(Source(doc_id=sid, title=title, page=page, snippet=snippet))
    return sources


async def _stream_response(
    http_request: Request,
    request: ChatRequest,
    request_id: str,
) -> AsyncGenerator[str, None]:
    """Run the agent graph and yield SSE events."""
    start = time.monotonic()

    ACTIVE_CONNECTIONS.inc()
    try:
        # Build and run graph (routing + retrieval + prompt preparation)
        graph = build_graph()

        # Load history from memory store if not provided by client
        history = request.history
        if not history:
            memory_store = get_memory_store()
            history = memory_store.get_history(request.conversation_id)

        initial_state = {
            "question": request.question,
            "conversation_id": request.conversation_id,
            "request_id": request_id,
            "history": history or [],
            "metadata": request.metadata or {},
        }

        result = await graph.ainvoke(initial_state)

        final_answer: str = result.get("final_answer", "") or ""
        generation_prompt: str = result.get("generation_prompt", "") or ""
        source_ids: list[str] = result.get("source_ids", []) or []
        retrieval_score: float = float(result.get("retrieval_score", 0.0) or 0.0)
        error = result.get("error")
        retrieved_docs = result.get("retrieved_docs") if isinstance(result, dict) else None

        if error and not final_answer and not generation_prompt:
            event = ChatErrorEvent(code="AGENT_ERROR", message=str(error))
            yield f"data: {event.model_dump_json()}\n\n"
            REQUEST_COUNT.labels(endpoint="/chat", status="error").inc()
            return

        # If the agent decided not to call the LLM (e.g., no_answer), stream the precomputed text.
        token_count = 0
        full_answer = ""
        if final_answer and not generation_prompt:
            full_answer = final_answer
            async for evt in _stream_text_as_events(final_answer):
                if await http_request.is_disconnected():
                    return
                token_count += 1
                yield evt
        else:
            # Real streaming: forward model chunks as they are produced.
            queue: asyncio.Queue[str | _StreamFailure | None] = asyncio.Queue()
            producer = asyncio.create_task(_produce_llm_chunks(generation_prompt, queue))
            try:
                while True:
                    if await http_request.is_disconnected():
                        producer.cancel()
                        return
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=0.25)
                    except TimeoutError:
                        continue
                    if item is None:
                        break
                    if isinstance(item, _StreamFailure):
                        event = ChatErrorEvent(code=item.code, message=item.message)
                        yield f"data: {event.model_dump_json()}\n\n"
                        REQUEST_COUNT.labels(endpoint="/chat", status="error").inc()
                        return

                    token_count += 1
                    full_answer += item
                    event = ChatTokenEvent(chunk=item)
                    yield f"data: {event.model_dump_json()}\n\n"
            finally:
                if not producer.done():
                    producer.cancel()
                with contextlib.suppress(Exception):
                    await producer

        # Save turn to persistent memory store
        memory_store = get_memory_store()
        memory_store.save_turn(request.conversation_id, request.question, full_answer)

        # Done event (metadata)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        sources = _sources_from_state(source_ids, retrieved_docs if isinstance(retrieved_docs, list) else None)
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
        _stream_response(request, body, request_id),
        media_type="text/event-stream",
    )
