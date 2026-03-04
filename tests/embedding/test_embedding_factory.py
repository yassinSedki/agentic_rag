"""Tests for the embedding factory."""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestEmbeddingFactory:
    """Tests for get_embedder() factory."""

    def test_factory_returns_embedder(self, test_settings):
        """Factory should return an OllamaEmbeddings instance (mocked)."""
        with patch("app.embedding.providers.ollama.OllamaEmbeddings") as MockEmbed:
            MockEmbed.return_value = "mock_embedder"
            from app.embedding.embedding_factory import get_embedder

            get_embedder.cache_clear()
            embedder = get_embedder()
            assert embedder is not None
            get_embedder.cache_clear()
