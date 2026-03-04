# 📁 Project Folder & File Structure

```text
agentic_rag/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py
│   │       ├── chat.py
│   │       ├── ingest.py
│   │       ├── health.py
│   │       └── models/
│   │           ├── __init__.py
│   │           ├── chat.py
│   │           └── ingest.py
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── state.py
│   │   ├── graph.py
│   │   │
│   │   ├── nodes/
│   │   │   ├── __init__.py
│   │   │   ├── decide.py
│   │   │   ├── query_rewrite.py
│   │   │   ├── retrieve.py
│   │   │   ├── evaluate_relevance.py
│   │   │   ├── grounding_check.py
│   │   │   ├── synthesize.py
│   │   │   ├── validate_output.py
│   │   │   ├── direct_answer.py
│   │   │   ├── clarify.py
│   │   │   ├── no_answer.py
│   │   │   └── stream_answer.py
│   │   │
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── lookup_by_id.py
│   │   │   └── memory_store.py
│   │   │
│   │   └── memory/
│   │       ├── __init__.py
│   │       └── conversation_memory.py
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── llm_factory.py
│   │   └── providers/
│   │       ├── __init__.py
│   │       └── ollama.py
│   │
│   ├── embedding/
│   │   ├── __init__.py
│   │   ├── embedding_factory.py
│   │   └── providers/
│   │       ├── __init__.py
│   │       └── ollama.py
│   │
│   ├── vectorstore/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── chroma.py
│   │   └── reranker.py
│   │
│   ├── ingest/
│   │   ├── __init__.py
│   │   ├── document_processor.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── load_document.py
│   │       ├── clean.py
│   │       ├── chunk_with_metadata.py
│   │       └── batch.py
│   │
│   └── core/
│       ├── __init__.py
│       ├── config.py
│       ├── logging.py
│       ├── metrics.py
│       ├── circuit_breaker.py
│       ├── security.py
│       ├── exceptions.py
│       └── schemas.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_graph.py
│   │   ├── test_nodes.py
│   │   └── test_tools.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_chat.py
│   │   └── test_ingest.py
│   ├── ingest/
│   │   ├── __init__.py
│   │   └── test_document_processor.py
│   ├── vectorstore/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   └── test_chroma_adapter.py
│   ├── llm/
│   │   ├── __init__.py
│   │   └── test_llm_factory.py
│   ├── embedding/
│   │   ├── __init__.py
│   │   └── test_embedding_factory.py
│   ├── test_circuit_breaker.py
│   └── test_security.py
│
├── Dockerfile
├── docker-compose.yml
├── docker-compose.test.yml
├── .env.example
├── pyproject.toml
├── Makefile
├── .pre-commit-config.yaml
├── .github/
│   └── workflows/
│       └── ci.yml
└── README.md
```

---

## 🤖 Agent Graph — LangGraph State Machine

```mermaid
flowchart TD
    START(["▶ START
    {question, conv_id, history}"])

    DECIDE["🔀 decide.py
    ─────────────────
    LLM classifies intent
    route = rag / direct / clarify"]

    REWRITE["✏️ query_rewrite.py
    ─────────────────
    LLM rewrites question
    for better retrieval"]

    RETRIEVE["🔍 retrieve.py
    ─────────────────
    Dense search + BM25
    → RRF fusion via reranker.py"]

    EVAL["📊 evaluate_relevance.py
    ─────────────────
    Score docs vs query
    → retrieval_sufficient flag
    → log metric"]

    GROUND["🔐 grounding_check.py
    ─────────────────
    LLM verifies claims
    are supported by docs"]

    SYNTH["🧠 synthesize.py
    ─────────────────
    Streaming LLM call
    with doc context + history
    → raw_answer, source_ids"]

    VALID["✅ validate_output.py
    ─────────────────
    Pydantic parse raw_answer
    → final_answer OR error"]

    DIRECT["💬 direct_answer.py
    ─────────────────
    LLM answers directly
    no retrieval needed"]

    CLARIFY["❓ clarify.py
    ─────────────────
    LLM asks user for
    clarification"]

    NOANSWER["🚫 no_answer.py
    ─────────────────
    Structured I-dont-know
    + ingest hint"]

    STREAM(["📡 stream_answer.py
    ─────────────────
    SSE terminal node
    token chunks → done event"])

    END(["⏹ END"])

    %% Entry
    START --> DECIDE

    %% Decide branches
    DECIDE -->|route = rag| REWRITE
    DECIDE -->|route = direct| DIRECT
    DECIDE -->|route = clarify| CLARIFY

    %% RAG path
    REWRITE --> RETRIEVE
    RETRIEVE --> EVAL

    %% Evaluate branch
    EVAL -->|retrieval_sufficient = True| GROUND
    EVAL -->|retrieval_sufficient = False| NOANSWER

    %% Grounding branch
    GROUND -->|grounding_ok = True| SYNTH
    GROUND -->|grounding_ok = False| NOANSWER

    %% Synthesis → validation
    SYNTH --> VALID
    VALID -->|parse_ok = True| STREAM
    VALID -->|parse_ok = False| NOANSWER

    %% All terminal paths → StreamAnswer → END
    DIRECT  --> STREAM
    CLARIFY --> STREAM
    NOANSWER --> STREAM
    STREAM --> END

    %% Styles
    style START    fill:#4f46e5,color:#fff,stroke:#3730a3
    style END      fill:#059669,color:#fff,stroke:#047857
    style STREAM   fill:#0891b2,color:#fff,stroke:#0e7490
    style DECIDE   fill:#7c3aed,color:#fff
    style EVAL     fill:#d97706,color:#fff
    style GROUND   fill:#d97706,color:#fff
    style VALID    fill:#d97706,color:#fff
    style NOANSWER fill:#dc2626,color:#fff
    style SYNTH    fill:#0f766e,color:#fff
    style DIRECT   fill:#0f766e,color:#fff
    style CLARIFY  fill:#0f766e,color:#fff
    style REWRITE  fill:#1e40af,color:#fff
    style RETRIEVE fill:#1e40af,color:#fff
```

---

## 🔀 Conditional Edge Router Functions

```mermaid
flowchart LR
    subgraph R1 ["after_decide()"]
        D1{state.route}
        D1 -->|rag| A1["→ query_rewrite"]
        D1 -->|direct| A2["→ direct_answer"]
        D1 -->|clarify| A3["→ clarify"]
        D1 -->|default| A1
    end

    subgraph R2 ["after_evaluate()"]
        D2{state.retrieval_sufficient}
        D2 -->|True| B1["→ grounding_check"]
        D2 -->|False| B2["→ no_answer"]
    end

    subgraph R3 ["after_grounding()"]
        D3{state.grounding_ok}
        D3 -->|True| C1["→ synthesize"]
        D3 -->|False| C2["→ no_answer"]
    end

    subgraph R4 ["after_validate()"]
        D4{state.error is None}
        D4 -->|True| E1["→ stream_answer"]
        D4 -->|False| E2["→ no_answer"]
    end
```

---

## 📦 AgentState — Shared Data Contract

```mermaid
classDiagram
    class AgentState {
        +str question
        +str conversation_id
        +str request_id
        +list history
        +str rewritten_query
        +list retrieved_docs
        +float retrieval_score
        +bool retrieval_sufficient
        +bool grounding_ok
        +str raw_answer
        +str final_answer
        +list source_ids
        +dict metadata
        +str error
        +str route
    }
```
