"""Tests for the LLM factory."""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestLLMFactory:
    """Tests for get_chat_llm() factory."""

    def test_factory_returns_llm(self, test_settings):
        """Factory should return a ChatOllama instance (mocked)."""
        with patch("app.llm.providers.ollama.ChatOllama") as MockLLM:
            MockLLM.return_value = "mock_llm"
            from app.llm.llm_factory import get_chat_llm

            get_chat_llm.cache_clear()
            llm = get_chat_llm()
            assert llm is not None
            get_chat_llm.cache_clear()
