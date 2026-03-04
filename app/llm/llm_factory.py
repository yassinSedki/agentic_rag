"""LLM factory — creates chat model clients from configuration.

Usage::

    from app.llm.llm_factory import get_chat_llm
    llm = get_chat_llm()
    response = await llm.ainvoke("Hello!")
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_chat_llm():
    """Create and return a chat LLM client based on settings.

    Currently supports Ollama; extend with additional providers as needed.
    """
    settings = get_settings()

    # Default provider: Ollama
    from app.llm.providers.ollama import build_ollama_llm

    return build_ollama_llm(settings)
