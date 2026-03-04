"""Tests for individual agent nodes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.nodes.evaluate_relevance import evaluate_relevance
from app.agent.nodes.no_answer import no_answer
from app.agent.nodes.stream_answer import stream_answer
from app.agent.nodes.validate_output import validate_output


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


class TestValidateOutput:
    """Tests for the validate_output node."""

    @pytest.mark.asyncio
    async def test_valid_answer(self):
        state = {"raw_answer": "This is the answer.", "source_ids": ["doc-1"]}
        result = await validate_output(state)
        assert result["final_answer"] == "This is the answer."
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_empty_answer(self):
        state = {"raw_answer": "", "source_ids": []}
        result = await validate_output(state)
        assert result["error"] is not None


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

    @pytest.mark.asyncio
    async def test_grounding_failed(self):
        state = {
            "question": "test?",
            "retrieval_sufficient": True,
            "grounding_ok": False,
        }
        result = await no_answer(state)
        assert "verified" in result["final_answer"]


class TestStreamAnswer:
    """Tests for the stream_answer node."""

    @pytest.mark.asyncio
    async def test_prepares_payload(self):
        state = {
            "final_answer": "Hello world",
            "source_ids": ["doc-1"],
            "metadata": {},
            "retrieval_score": 0.85,
        }
        result = await stream_answer(state)
        assert result["final_answer"] == "Hello world"
        assert result["metadata"]["source_ids"] == ["doc-1"]
        assert result["metadata"]["retrieval_score"] == 0.85
