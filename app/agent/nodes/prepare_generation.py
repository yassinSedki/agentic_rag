"""Prepare-generation nodes.

These nodes do **not** call the LLM. They build the prompt and metadata so the
API layer can stream tokens from the model in real time.
"""

from __future__ import annotations

import structlog

from app.agent.state import AgentState
from app.core.config import get_settings

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

_DIRECT_PROMPT = """You are a helpful assistant. Answer the user's question directly.
Keep your answer concise and helpful.

Conversation history: {history}

Question: {question}

Answer:"""

_CLARIFY_PROMPT = """You are a helpful assistant. The user's question is ambiguous or too vague.
Ask a brief, friendly clarification question to help you understand what they need.

Do NOT attempt to answer the question — just ask for clarification.

User's question: {question}

Clarification question:"""


async def prepare_rag_generation(state: AgentState) -> dict:
    """Build the RAG synthesis prompt and collect citation ids."""
    query = state.get("rewritten_query", state["question"])
    docs = state.get("retrieved_docs", [])
    history = state.get("history", [])
    settings = get_settings()

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

    logger.info(
        "rag_generation_prepared",
        prompt_chars=len(prompt),
        source_count=len(source_ids),
    )

    return {
        "generation_prompt": prompt,
        "source_ids": source_ids,
        "error": None,
    }


async def prepare_direct_generation(state: AgentState) -> dict:
    """Build the direct-answer prompt for streaming generation."""
    question = state["question"]
    history = state.get("history", [])
    prompt = _DIRECT_PROMPT.format(
        question=question,
        history=str(history[-5:]) if history else "[]",
    )
    logger.info("direct_generation_prepared", prompt_chars=len(prompt))
    return {
        "generation_prompt": prompt,
        "source_ids": [],
        "error": None,
    }


async def prepare_clarify_generation(state: AgentState) -> dict:
    """Build the clarification prompt for streaming generation."""
    question = state["question"]
    prompt = _CLARIFY_PROMPT.format(question=question)
    logger.info("clarify_generation_prepared", prompt_chars=len(prompt))
    return {
        "generation_prompt": prompt,
        "source_ids": [],
        "error": None,
    }

