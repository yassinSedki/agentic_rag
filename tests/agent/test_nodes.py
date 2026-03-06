"""Tests for individual agent nodes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.nodes.decide import decide
from app.agent.nodes.evaluate_relevance import evaluate_relevance
from app.agent.nodes.no_answer import no_answer
from app.agent.nodes.query_rewrite import query_rewrite
from app.agent.nodes.prepare_generation import (
    prepare_rag_generation,
    prepare_direct_generation,
    prepare_clarify_generation,
)


class TestDecide:
    """Tests for the decide node."""

    @pytest.mark.asyncio
    async def test_decide_rag(self):
        class FakeResponse:
            content = "rag"

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=FakeResponse())

        with patch("app.agent.nodes.decide.get_chat_llm", return_value=mock_llm):
            state = {"question": "What is RAG?"}
            result = await decide(state)
            assert result["route"] == "rag"

    @pytest.mark.asyncio
    async def test_decide_fallback(self):
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("error"))

        with patch("app.agent.nodes.decide.get_chat_llm", return_value=mock_llm):
            state = {"question": "..."}
            result = await decide(state)
            assert result["route"] == "rag"  # default fallback


class TestQueryRewrite:
    """Tests for the query_rewrite node."""

    @pytest.mark.asyncio
    async def test_rewrite_success(self):
        class FakeResponse:
            content = "Detailed search query about RAG"

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=FakeResponse())

        with patch("app.agent.nodes.query_rewrite.get_chat_llm", return_value=mock_llm):
            state = {"question": "tell me about rag"}
            result = await query_rewrite(state)
            assert "Detailed" in result["rewritten_query"]

    @pytest.mark.asyncio
    async def test_rewrite_short_fallback(self):
        class FakeResponse:
            content = "hi"  # too short

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=FakeResponse())

        with patch("app.agent.nodes.query_rewrite.get_chat_llm", return_value=mock_llm):
            state = {"question": "original question"}
            result = await query_rewrite(state)
            assert result["rewritten_query"] == "original question"


class TestEvaluateRelevance:
    """Tests for the evaluate_relevance node."""

    @pytest.mark.asyncio
    async def test_empty_docs(self):
        state = {"retrieved_docs": [], "rewritten_query": "test"}
        result = await evaluate_relevance(state)
        assert result["retrieval_sufficient"] is False
        assert result["retrieval_score"] == 0.0

    @pytest.mark.asyncio
    async def test_sufficient_docs(self):
        state = {
            "retrieved_docs": [
                {"doc_id": "1", "content": "test", "score": 0.8},
                {"doc_id": "2", "content": "test", "score": 0.6},
            ],
            "rewritten_query": "test",
        }
        result = await evaluate_relevance(state)
        assert result["retrieval_sufficient"] is True
        assert result["retrieval_score"] > 0.0


class TestPrepareGeneration:
    """Tests for nodes that build prompts for the API layer."""

    @pytest.mark.asyncio
    async def test_prepare_rag(self):
        state = {
            "question": "test?",
            "retrieved_docs": [{"doc_id": "doc1", "content": "Sample content"}],
        }
        result = await prepare_rag_generation(state)
        assert "doc1" in result["generation_prompt"]
        assert "Sample content" in result["generation_prompt"]
        assert result["source_ids"] == ["doc1"]

    @pytest.mark.asyncio
    async def test_prepare_direct(self):
        state = {"question": "Hello"}
        result = await prepare_direct_generation(state)
        assert "Hello" in result["generation_prompt"]
        assert result["source_ids"] == []

    @pytest.mark.asyncio
    async def test_prepare_clarify(self):
        state = {"question": "what?"}
        result = await prepare_clarify_generation(state)
        assert "what?" in result["generation_prompt"]


class TestNoAnswer:
    """Tests for the no_answer node."""

    @pytest.mark.asyncio
    async def test_insufficient_retrieval(self):
        state = {
            "question": "test?",
            "retrieval_sufficient": False,
        }
        result = await no_answer(state)
        assert "don't have enough information" in result["final_answer"]
        assert "Hint:" in result["final_answer"]
