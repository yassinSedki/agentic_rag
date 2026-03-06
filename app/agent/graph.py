"""LangGraph state machine — wires nodes and conditional edges.

This graph orchestrates routing and retrieval, then **prepares** a generation
prompt. The actual LLM token streaming happens in the API layer.

Graph flow (streaming-ready):
    START → Decide
        ├─ route=rag     → QueryRewrite → Retrieve → Evaluate
        │                     ├─ sufficient=True  → PrepareRagGeneration → END
        │                     └─ sufficient=False → NoAnswer → END
        ├─ route=direct  → PrepareDirectGeneration → END
        └─ route=clarify → PrepareClarifyGeneration → END
"""

from __future__ import annotations

import structlog
from langgraph.graph import END, StateGraph

from app.agent.nodes.decide import decide
from app.agent.nodes.evaluate_relevance import evaluate_relevance
from app.agent.nodes.no_answer import no_answer
from app.agent.nodes.prepare_generation import (
    prepare_clarify_generation,
    prepare_direct_generation,
    prepare_rag_generation,
)
from app.agent.nodes.query_rewrite import query_rewrite
from app.agent.nodes.retrieve import retrieve, set_vector_store as set_retrieve_vector_store
from app.agent.state import AgentState
from app.agent.tools.lookup_by_id import set_vector_store as set_lookup_vector_store
from app.vectorstore import VectorStore

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

    # Wire shared vector store into retrieval-related components once per graph
    vs = VectorStore()
    set_retrieve_vector_store(vs)
    set_lookup_vector_store(vs)

    # ── Register nodes ───────────────────────────────────────────────────
    graph.add_node("decide", decide)
    graph.add_node("query_rewrite", query_rewrite)
    graph.add_node("retrieve", retrieve)
    graph.add_node("evaluate_relevance", evaluate_relevance)
    # Streaming generation is done in the API layer; these nodes prepare prompts.
    graph.add_node("synthesize", prepare_rag_generation)
    graph.add_node("direct_answer", prepare_direct_generation)
    graph.add_node("clarify", prepare_clarify_generation)
    graph.add_node("no_answer", no_answer)

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
            "synthesize": "synthesize",  # prepare_rag_generation
            "no_answer": "no_answer",
        },
    )

    # ── Terminal edges ───────────────────────────────────────────────────
    graph.add_edge("synthesize", END)
    graph.add_edge("direct_answer", END)
    graph.add_edge("clarify", END)
    graph.add_edge("no_answer", END)

    logger.info("agent_graph_built")
    return graph.compile()
