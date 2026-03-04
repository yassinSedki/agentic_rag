"""Embedding factory — creates embedding models from configuration.

Usage::

    from app.embedding.embedding_factory import get_embedder
    embedder = get_embedder()
    vectors = embedder.embed_documents(["hello world"])
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_embedder():
    """Create and return an embedding model based on settings.

    Currently supports Ollama embeddings; extend as needed.
    """
    settings = get_settings()

    from app.embedding.providers.ollama import build_ollama_embedder

    return build_ollama_embedder(settings)
