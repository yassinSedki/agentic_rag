"""Ollama LLM provider — thin wrapper around ``ChatOllama``.

Constructs the LangChain ``ChatOllama`` object with settings from
``core/config.py`` including base URL, model name, timeout, and
streaming mode.
"""

from __future__ import annotations

from langchain_ollama import ChatOllama

from app.core.config import Settings


def build_ollama_llm(settings: Settings) -> ChatOllama:
    """Build a ``ChatOllama`` instance from application settings.

    Parameters
    ----------
    settings:
        Application settings with Ollama parameters.

    Returns
    -------
    ChatOllama
        Configured LangChain chat model with streaming enabled.
    """
    return ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        timeout=settings.ollama_timeout_s,
        streaming=True,
        temperature=0.1,  # low temperature for factual RAG answers
    )
