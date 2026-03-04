"""Synthesize node — streaming LLM synthesis with document context.

Reads ``retrieved_docs``, ``rewritten_query``, and ``history`` from state.
Writes ``raw_answer`` and ``source_ids``.

This is the **core generation step** — grounding is checked AFTER this.
"""

from __future__ import annotations

import time

import structlog

from app.agent.state import AgentState
from app.core.config import get_settings
from app.core.metrics import LLM_LATENCY
from app.llm.llm_factory import get_chat_llm

logger = structlog.get_logger()

_SYNTHESIS_PROMPT = """You are a helpful assistant answering questions based ONLY on the provided documents.

Rules:
1. ONLY use information from the provided documents to answer.
2. If the documents don't contain enough information, say so.
3. Cite document sources when possible by referencing their doc_id.
4. Be concise but thorough.
5. Use markdown formatting for readability.

Documents:
{context}

Conversation history:
{history}

Question: {question}

Answer:"""


async def synthesize(state: AgentState) -> dict:
    """Generate a draft answer grounded in retrieved documents."""
    query = state.get("rewritten_query", state["question"])
    docs = state.get("retrieved_docs", [])
    history = state.get("history", [])
    settings = get_settings()

    # Build context from retrieved docs (respect max chars)
    context_parts: list[str] = []
    source_ids: list[str] = []
    total_chars = 0

    for doc in docs:
        if isinstance(doc, dict):
            content = doc.get("content", "")
            doc_id = doc.get("doc_id", "unknown")
        else:
            content = str(doc)
            doc_id = "unknown"

        if total_chars + len(content) > settings.max_context_chars:
            break

        context_parts.append(f"[{doc_id}]: {content}")
        source_ids.append(doc_id)
        total_chars += len(content)

    context = "\n\n".join(context_parts) if context_parts else "No documents available."
    history_text = str(history[-5:]) if history else "[]"

    prompt = _SYNTHESIS_PROMPT.format(
        context=context,
        history=history_text,
        question=query,
    )

    llm = get_chat_llm()
    start = time.monotonic()

    try:
        response = await llm.ainvoke(prompt)
        raw_answer = response.content.strip()

        elapsed = time.monotonic() - start
        LLM_LATENCY.labels(model=settings.ollama_model).observe(elapsed)

        logger.info(
            "synthesis_complete",
            answer_len=len(raw_answer),
            source_count=len(source_ids),
            latency_ms=int(elapsed * 1000),
        )

        return {
            "raw_answer": raw_answer,
            "source_ids": source_ids,
        }

    except Exception as exc:
        logger.error("synthesis_failed", error=str(exc))
        return {
            "raw_answer": "",
            "source_ids": [],
            "error": f"Synthesis failed: {exc}",
        }
