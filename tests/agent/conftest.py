"""Agent test fixtures."""

from __future__ import annotations

import pytest

from app.agent.state import AgentState


@pytest.fixture
def base_agent_state() -> AgentState:
    """Return a minimal AgentState for testing."""
    return AgentState(
        question="What is the refund policy?",
        conversation_id="test-conv-001",
        request_id="test-req-001",
        history=[],
        metadata={},
    )


@pytest.fixture
def rag_agent_state(base_agent_state) -> AgentState:
    """Return an AgentState with retrieval results for testing."""
    return AgentState(
        **base_agent_state,
        rewritten_query="refund policy details and conditions",
        retrieved_docs=[
            {
                "doc_id": "doc-001",
                "content": "Returns are accepted within 30 days of purchase.",
                "metadata": {"source": "policy.txt"},
                "score": 0.85,
            },
            {
                "doc_id": "doc-002",
                "content": "Items must be in original packaging.",
                "metadata": {"source": "policy.txt"},
                "score": 0.72,
            },
        ],
        retrieval_score=0.785,
        retrieval_sufficient=True,
    )
