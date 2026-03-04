"""Tests for the LangGraph agent graph transitions."""

from __future__ import annotations

import pytest

from app.agent.graph import after_decide, after_evaluate, after_grounding, after_validate


class TestRouterFunctions:
    """Test conditional edge router functions."""

    def test_after_decide_rag(self):
        state = {"route": "rag"}
        assert after_decide(state) == "query_rewrite"

    def test_after_decide_direct(self):
        state = {"route": "direct"}
        assert after_decide(state) == "direct_answer"

    def test_after_decide_clarify(self):
        state = {"route": "clarify"}
        assert after_decide(state) == "clarify"

    def test_after_decide_default(self):
        state = {}
        assert after_decide(state) == "query_rewrite"

    def test_after_evaluate_sufficient(self):
        state = {"retrieval_sufficient": True}
        assert after_evaluate(state) == "synthesize"

    def test_after_evaluate_insufficient(self):
        state = {"retrieval_sufficient": False}
        assert after_evaluate(state) == "no_answer"

    def test_after_grounding_ok(self):
        state = {"grounding_ok": True}
        assert after_grounding(state) == "validate_output"

    def test_after_grounding_failed(self):
        state = {"grounding_ok": False}
        assert after_grounding(state) == "no_answer"

    def test_after_validate_success(self):
        state = {"error": None}
        assert after_validate(state) == "stream_answer"

    def test_after_validate_error(self):
        state = {"error": "parse failed"}
        assert after_validate(state) == "no_answer"
