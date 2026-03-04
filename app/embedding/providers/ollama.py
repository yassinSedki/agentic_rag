"""Ollama embedding provider.

Returns a LangChain-compatible ``OllamaEmbeddings`` instance that can
embed texts into vectors for storage and similarity search.
"""

from __future__ import annotations

from langchain_ollama import OllamaEmbeddings

from app.core.config import Settings


def build_ollama_embedder(settings: Settings) -> OllamaEmbeddings:
    """Build an ``OllamaEmbeddings`` instance from application settings.

    Parameters
    ----------
    settings:
        Application settings with Ollama embedding parameters.

    Returns
    -------
    OllamaEmbeddings
        Configured embedding model.
    """
    return OllamaEmbeddings(
        base_url=settings.ollama_base_url,
        model=settings.ollama_embed_model,
    )
