"""Grounding check node — verifies the synthesized answer is supported by docs.

**This runs AFTER synthesis** (not before).  The LLM examines the
``raw_answer`` and ``retrieved_docs`` to flag any claims that are not
grounded in the provided documents.

Sets ``grounding_ok`` and optionally ``metadata["grounding_report"]``.
"""

from __future__ import annotations

import structlog

from app.agent.state import AgentState
from app.llm.llm_factory import get_chat_llm

logger = structlog.get_logger()

_GROUNDING_PROMPT = """You are a grounding verifier for a RAG system.

Your task: determine whether the ANSWER is fully supported by the DOCUMENTS.

Rules:
1. Check each claim in the answer against the documents.
2. If ALL claims are supported → respond with "GROUNDED"
3. If ANY claim is NOT supported by the documents → respond with "NOT_GROUNDED"
4. Ignore stylistic differences — focus on factual accuracy.

DOCUMENTS:
{documents}

ANSWER:
{answer}

Verdict (respond with ONLY "GROUNDED" or "NOT_GROUNDED"):"""


async def grounding_check(state: AgentState) -> dict:
    """Verify that the synthesized answer is grounded in retrieved documents."""
    raw_answer = state.get("raw_answer", "")
    docs = state.get("retrieved_docs", [])

    # If no answer was produced, auto-fail
    if not raw_answer:
        logger.warning("grounding_no_answer")
        return {"grounding_ok": False}

    # Build document context
    doc_texts: list[str] = []
    for doc in docs:
        if isinstance(doc, dict):
            doc_texts.append(doc.get("content", ""))
        else:
            doc_texts.append(str(doc))

    documents_str = "\n\n---\n\n".join(doc_texts) if doc_texts else "No documents."

    prompt = _GROUNDING_PROMPT.format(
        documents=documents_str,
        answer=raw_answer,
    )

    llm = get_chat_llm()

    try:
        response = await llm.ainvoke(prompt)
        verdict = response.content.strip().upper()

        grounding_ok = "GROUNDED" in verdict and "NOT_GROUNDED" not in verdict

        logger.info(
            "grounding_check_complete",
            verdict=verdict,
            grounding_ok=grounding_ok,
        )

        return {
            "grounding_ok": grounding_ok,
            "metadata": {
                **state.get("metadata", {}),
                "grounding_report": verdict,
            },
        }

    except Exception as exc:
        logger.error("grounding_check_failed", error=str(exc))
        # Fail-safe: reject unverifiable answers
        return {"grounding_ok": False}
