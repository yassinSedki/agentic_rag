"""Direct answer node — LLM answers without document retrieval.

Used for simple questions (greetings, math, general knowledge) that
don't require the RAG pipeline.
"""

from __future__ import annotations

import structlog

from app.agent.state import AgentState
from app.llm.llm_factory import get_chat_llm

logger = structlog.get_logger()

_DIRECT_PROMPT = """You are a helpful assistant. Answer the user's question directly.
Keep your answer concise and helpful.

Conversation history: {history}

Question: {question}

Answer:"""


async def direct_answer(state: AgentState) -> dict:
    """Generate a direct answer without document retrieval."""
    question = state["question"]
    history = state.get("history", [])

    llm = get_chat_llm()
    prompt = _DIRECT_PROMPT.format(
        question=question,
        history=str(history[-5:]) if history else "[]",
    )

    try:
        response = await llm.ainvoke(prompt)
        answer = response.content.strip()

        logger.info("direct_answer_generated", answer_len=len(answer))
        return {
            "final_answer": answer,
            "error": None,
        }

    except Exception as exc:
        logger.error("direct_answer_failed", error=str(exc))
        return {
            "final_answer": "I'm sorry, I wasn't able to process your question.",
            "error": str(exc),
        }
