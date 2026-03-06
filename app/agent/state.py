"""AgentState — shared data contract for the LangGraph state machine.

Every node in the graph reads from and writes to this TypedDict.
Fields are annotated with ``Annotated[..., operator.add]`` when they
should merge (e.g. lists that grow across nodes).  All other fields
are overwritten by the last writer.
"""

from __future__ import annotations

from typing import Any, Optional

from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    """State passed through every node in the LangGraph agent.

    Attributes
    ----------
    question : str
        Original user question.
    conversation_id : str
        Conversation session identifier.
    request_id : str
        Unique per-request identifier for tracing.
    history : list
        Previous conversation turns (short-term context).
    rewritten_query : str
        Query after rewriting for better retrieval.
    retrieved_docs : list
        Documents returned by the retrieval step.
    retrieval_score : float
        Average relevance score of retrieved documents.
    retrieval_sufficient : bool
        Whether the retrieved docs are relevant enough.
    raw_answer : str
        Draft answer produced by the synthesize step.
    generation_prompt : str
        Prompt to be sent to the LLM for streaming generation. When this is set,
        the API layer is responsible for streaming the model output.
    final_answer : str
        Final validated answer ready for streaming.
    source_ids : list[str]
        Document IDs cited in the answer.
    grounding_ok : bool
        Whether the grounding check passed.
    metadata : dict
        Flexible metadata bag (grounding reports, latency, etc.).
    error : str | None
        Error message if something went wrong; ``None`` otherwise.
    route : str | None
        Routing decision: ``"rag"`` | ``"direct"`` | ``"clarify"``.
    """

    question: str
    conversation_id: str
    request_id: str
    history: list[dict[str, Any]]

    rewritten_query: str
    retrieved_docs: list[Any]
    retrieval_score: float
    retrieval_sufficient: bool

    raw_answer: str
    generation_prompt: str
    final_answer: str
    source_ids: list[str]

    grounding_ok: bool
    metadata: dict[str, Any]
    error: Optional[str]
    route: Optional[str]
