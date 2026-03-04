"""LangGraph state machine — wires all nodes and conditional edges.

Graph flow (updated — grounding AFTER synthesis):
    START → Decide
        ├─ route=rag     → QueryRewrite → Retrieve → Evaluate
        │                     ├─ sufficient=True  → Synthesize → GroundingCheck
        │                     │                         ├─ ok=True  → Validate → Stream
        │                     │                         └─ ok=False → NoAnswer → Stream
        │                     └─ sufficient=False → NoAnswer → Stream
        ├─ route=direct  → DirectAnswer → Stream
        └─ route=clarify → Clarify → Stream
    Stream → END
"""

from __future__ import annotations

import structlog
from langgraph.graph import END, StateGraph

from app.agent.nodes.clarify import clarify
from app.agent.nodes.decide import decide
from app.agent.nodes.direct_answer import direct_answer
from app.agent.nodes.evaluate_relevance import evaluate_relevance
from app.agent.nodes.grounding_check import grounding_check
from app.agent.nodes.no_answer import no_answer
from app.agent.nodes.query_rewrite import query_rewrite
from app.agent.nodes.retrieve import retrieve
from app.agent.nodes.stream_answer import stream_answer
from app.agent.nodes.synthesize import synthesize
from app.agent.nodes.validate_output import validate_output
from app.agent.state import AgentState

logger = structlog.get_logger()


# ── Router functions ─────────────────────────────────────────────────────────


def after_decide(state: AgentState) -> str:
    """Route after the Decide node based on ``state.route``."""
    route = state.get("route", "rag")
    if route == "direct":
        return "direct_answer"
    elif route == "clarify":
        return "clarify"
    return "query_rewrite"  # default: rag


def after_evaluate(state: AgentState) -> str:
    """Route after EvaluateRelevance based on ``state.retrieval_sufficient``."""
    if state.get("retrieval_sufficient", False):
        return "synthesize"
    return "no_answer"


def after_grounding(state: AgentState) -> str:
    """Route after GroundingCheck based on ``state.grounding_ok``."""
    if state.get("grounding_ok", False):
        return "validate_output"
    return "no_answer"


def after_validate(state: AgentState) -> str:
    """Route after ValidateOutput based on ``state.error``."""
    if state.get("error") is None:
        return "stream_answer"
    return "no_answer"


# ── Graph builder ────────────────────────────────────────────────────────────


def build_graph() -> StateGraph:
    """Construct and compile the LangGraph agent.

    Returns
    -------
    StateGraph
        Compiled graph ready for invocation.
    """
    graph = StateGraph(AgentState)

    # ── Register nodes ───────────────────────────────────────────────────
    graph.add_node("decide", decide)
    graph.add_node("query_rewrite", query_rewrite)
    graph.add_node("retrieve", retrieve)
    graph.add_node("evaluate_relevance", evaluate_relevance)
    graph.add_node("synthesize", synthesize)
    graph.add_node("grounding_check", grounding_check)
    graph.add_node("validate_output", validate_output)
    graph.add_node("direct_answer", direct_answer)
    graph.add_node("clarify", clarify)
    graph.add_node("no_answer", no_answer)
    graph.add_node("stream_answer", stream_answer)

    # ── Entry point ──────────────────────────────────────────────────────
    graph.set_entry_point("decide")

    # ── Conditional edges ────────────────────────────────────────────────
    graph.add_conditional_edges(
        "decide",
        after_decide,
        {
            "query_rewrite": "query_rewrite",
            "direct_answer": "direct_answer",
            "clarify": "clarify",
        },
    )

    # ── Linear edges (RAG path) ──────────────────────────────────────────
    graph.add_edge("query_rewrite", "retrieve")
    graph.add_edge("retrieve", "evaluate_relevance")

    graph.add_conditional_edges(
        "evaluate_relevance",
        after_evaluate,
        {
            "synthesize": "synthesize",
            "no_answer": "no_answer",
        },
    )

    # Synthesis → Grounding (grounding AFTER synthesis)
    graph.add_edge("synthesize", "grounding_check")

    graph.add_conditional_edges(
        "grounding_check",
        after_grounding,
        {
            "validate_output": "validate_output",
            "no_answer": "no_answer",
        },
    )

    graph.add_conditional_edges(
        "validate_output",
        after_validate,
        {
            "stream_answer": "stream_answer",
            "no_answer": "no_answer",
        },
    )

    # ── Terminal edges ───────────────────────────────────────────────────
    graph.add_edge("direct_answer", "stream_answer")
    graph.add_edge("clarify", "stream_answer")
    graph.add_edge("no_answer", "stream_answer")
    graph.add_edge("stream_answer", END)

    logger.info("agent_graph_built")
    return graph.compile()
