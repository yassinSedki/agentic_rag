# 🏗️ Agentic RAG System — Production Architecture Blueprint

> **Role**: AI Architect  
> **Project**: Async RAG Agent API — FastAPI · LangGraph · Ollama · Vector DB  
> **Date**: 2026-02-26  
> **Status**: Production-Ready Design

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Context (C4 Level 1)](#2-system-context-c4-level-1)
3. [Container Architecture (C4 Level 2)](#3-container-architecture-c4-level-2)
4. [Component Breakdown (C4 Level 3)](#4-component-breakdown-c4-level-3)
5. [LangGraph Agent State Machine](#5-langgraph-agent-state-machine)
6. [Request Lifecycle & Data Flow](#6-request-lifecycle--data-flow)
7. [Ingestion Pipeline](#7-ingestion-pipeline)
8. [API Contract](#8-api-contract)
9. [Infrastructure & Docker Topology](#9-infrastructure--docker-topology)
10. [Observability Design](#10-observability-design)
11. [Security Model](#11-security-model)
12. [Testing Strategy](#12-testing-strategy)
13. [Repository Layout (Final)](#13-repository-layout-final)
14. [Technology Decision Record](#14-technology-decision-record)
15. [Evaluation & Rubric Mapping](#15-evaluation--rubric-mapping)
16. [Suggested Development Timeline](#16-suggested-development-timeline)

---

## 1. Executive Summary

This system is a **production-grade, streaming Retrieval-Augmented Generation (RAG) API** designed for enterprise document Q&A scenarios. It combines:

- **FastAPI** for async, non-blocking HTTP with Server-Sent Events (SSE) streaming
- **LangGraph** for explicit, testable multi-step agent orchestration
- **Ollama** for local LLM inference (zero cloud dependency)
- **ChromaDB / Qdrant** for semantic vector retrieval
- **Docker Compose** for one-command reproducible deployment

The system prioritizes **grounded answers**, **observability**, **resilience**, and **developer ergonomics** — meeting all acceptance criteria plus advanced add-ons across reliability, retrieval quality, security, and operations.

---

## 2. System Context (C4 Level 1)

```mermaid
C4Context
    title System Context — Agentic RAG API

    Person(user, "End User / Client App", "Sends questions via REST; receives streaming SSE responses")
    Person(admin, "Operator / DevOps", "Manages deployment, ingests documents, monitors health")

    System(rag_api, "Agentic RAG Service", "FastAPI async service that orchestrates LLM responses grounded in a knowledge base")

    System_Ext(ollama, "Ollama LLM Runtime", "Local LLM inference server (llama3, mistral, etc.)")
    System_Ext(vectordb, "Vector Database", "Stores document embeddings for semantic retrieval (ChromaDB / Qdrant)")
    System_Ext(otel, "OpenTelemetry Collector", "Collects distributed traces and metrics")
    System_Ext(prometheus, "Prometheus + Grafana", "Metrics scraping and dashboards")

    Rel(user, rag_api, "POST /chat — SSE stream", "HTTPS")
    Rel(admin, rag_api, "POST /ingest, GET /health", "HTTPS")
    Rel(rag_api, ollama, "Generate & embed", "HTTP/REST")
    Rel(rag_api, vectordb, "Store & query vectors", "gRPC / HTTP")
    Rel(rag_api, otel, "Traces & spans", "OTLP/gRPC")
    Rel(rag_api, prometheus, "Expose /metrics", "HTTP Scrape")
```

---

## 3. Container Architecture (C4 Level 2)

```mermaid
C4Container
    title Container Diagram — Agentic RAG Platform

    Person(client, "Client", "Browser, curl, SDK")

    Container_Boundary(platform, "Docker Compose Stack") {
        Container(api, "RAG API", "Python 3.11 / FastAPI", "Handles HTTP, orchestrates agent, streams SSE")
        Container(ollama_c, "Ollama", "Go / llama.cpp", "Serves LLM and embedding models locally")
        Container(chroma, "ChromaDB", "Python / DuckDB+Parquet", "Vector store with REST+gRPC API")
        Container(otel_c, "OTEL Collector", "Go", "Receives traces, exports to stdout / Jaeger")
    }

    ContainerDb(vol_chroma, "chroma_data volume", "Persistent vector + document store")
    ContainerDb(vol_ollama, "ollama_models volume", "Downloaded model weights")

    Rel(client, api, "POST /chat, POST /ingest, GET /health", "HTTP SSE")
    Rel(api, ollama_c, "Chat + embed calls", "HTTP :11434")
    Rel(api, chroma, "Add docs, query", "HTTP :8001")
    Rel(api, otel_c, "OTLP spans", "gRPC :4317")
    Rel(ollama_c, vol_ollama, "Reads/writes model files")
    Rel(chroma, vol_chroma, "Persists embeddings")
```

---

## 4. Component Breakdown (C4 Level 3)

### 4.1 High-Level Module Map

```mermaid
graph TD
    subgraph API ["🌐 app/api/v1/"]
        CHAT_R["chat.py\nPOST /chat SSE"]
        INGEST_R["ingest.py\nPOST /ingest"]
        subgraph MODELS ["models/"]
            CHAT_M["chat.py\nChatRequest · ChatDoneEvent"]
            INGEST_M["ingest.py\nIngestRequest · IngestResponse"]
        end
    end

    subgraph AGENT ["🤖 app/agent/"]
        STATE["state.py\nAgentState TypedDict"]
        GRAPH["graph.py\nStateGraph compiler"]
        subgraph NODES ["nodes/ — pure reasoning"]
            N_DECIDE[decide.py]
            N_REWRITE[query_rewrite.py]
            N_RETRIEVE[retrieve.py]
            N_EVAL[evaluate_relevance.py]
            N_GROUND[grounding_check.py]
            N_SYNTH[synthesize.py]
            N_VALID[validate_output.py]
            N_DIRECT[direct_answer.py]
            N_CLARIFY[clarify.py]
            N_NOANSWER[no_answer.py]
            N_STREAM[stream_answer.py]
        end
        subgraph TOOLS ["tools/ — side effects"]
            T_LOOKUP[lookup_by_id.py]
            T_MEM[memory_store.py]
        end
        subgraph MEMORY ["memory/"]
            MEM[memory.py]
        end
    end

    subgraph LLM ["🧠 app/llm/"]
        LLM_FACTORY["llm_factory.py"]
        subgraph PROVIDERS ["providers/"]
            OLLAMA_P["ollama.py\nChatOllama definition"]
        end
    end

    subgraph EMBED_NS ["🔢 app/embedding/"]
        EMBED_FACTORY["embedding_factory.py"]
    end

    subgraph VS_NS ["🗄️ app/vectorstore/"]
        VS_WRAPPER["vectorstore.py\nAbstract interface"]
        VS_CHROMA["chroma.py\nChromaDB implementation"]
    end

    subgraph INGEST_NS ["📥 app/ingest/"]
        PROC["document_processor.py\norchestrator"]
        subgraph UTILS ["utils/"]
            U_LOAD["load_document.py"]
            U_CLEAN["clean.py"]
            U_CHUNK["chunk_with_metadata.py"]
            U_BATCH["batch.py"]
        end
    end

    subgraph CORE ["⚙️ app/core/"]
        CFG[config.py]
        LOG[logging.py]
        MET[metrics.py]
        CB[circuit_breaker.py]
        SEC[security.py]
    end

    CHAT_R --> GRAPH
    INGEST_R --> PROC
    GRAPH --> STATE
    GRAPH --> NODES
    N_RETRIEVE --> VS_WRAPPER
    T_LOOKUP --> VS_WRAPPER
    T_MEM --> MEM
    MEM --> VS_WRAPPER
    VS_WRAPPER --> VS_CHROMA
    VS_CHROMA --> EMBED_FACTORY
    PROC --> U_LOAD & U_CLEAN & U_CHUNK & U_BATCH
    PROC --> VS_WRAPPER
    LLM_FACTORY --> OLLAMA_P
    GRAPH --> LLM_FACTORY
    EMBED_FACTORY --> OLLAMA_P
    AGENT --> CORE
    API --> CORE
    INGEST_NS --> CORE
```


### 4.2 Internal Component Responsibilities

#### 🌐 API Layer — `app/api/v1/`

| File | Responsibility |
|------|----------------|
| `chat.py` | Validate `ChatRequest`, open SSE generator, stream graph output, handle disconnect |
| `ingest.py` | Accept JSON or multipart, delegate to `document_processor`, return `IngestResponse` |
| `models/chat.py` | `ChatRequest` · `ChatTokenEvent` · `ChatDoneEvent` · `ChatErrorEvent` · `Source` |
| `models/ingest.py` | `IngestRequest` · `IngestResponse` |

#### 🤖 Agent Layer — `app/agent/`

| File | Responsibility |
|------|----------------|
| `state.py` | `AgentState` TypedDict — single shared object passed through all nodes |
| `graph.py` | Compile `StateGraph`: register all nodes, wire conditional edges via router functions |
| `nodes/decide.py` | LLM classifier → `route`: `"rag"` / `"direct"` / `"clarify"`. Default fallback: `"rag"` |
| `nodes/query_rewrite.py` | Rewrite user question for better vector retrieval precision |
| `nodes/retrieve.py` | Dense vector search + in-process BM25 (`rank-bm25`) → RRF fusion |
| `nodes/evaluate_relevance.py` | Score docs vs query (cosine sim); set `retrieval_score`, `retrieval_sufficient`; emit metric |
| `nodes/grounding_check.py` | LLM verifier: do retrieved docs support the query? Sets `grounding_ok` |
| `nodes/synthesize.py` | Streaming LLM call with doc context + history; sets `raw_answer`, `source_ids` |
| `nodes/validate_output.py` | Pydantic output parser on `raw_answer`; sets `final_answer` or `error` |
| `nodes/direct_answer.py` | LLM answers directly without retrieval |
| `nodes/clarify.py` | LLM returns a clarification question to the user |
| `nodes/no_answer.py` | Structured "I don't know" response + ingest hint; sets `final_answer` |
| `nodes/stream_answer.py` | Terminal SSE emitter: token chunks then `done` event |
| `tools/lookup_by_id.py` | `@tool` — fetch full document by ID from vectorstore, re-rank vs query |
| `tools/memory_store.py` | `@tool` — delegate to `memory.py` to read/write conversation summaries |
| `memory/memory.py` | `store_summary(conv_id, text)` + `retrieve_context(conv_id) → str`; TTL + max-N safeguards |

#### 🧠 LLM Layer — `app/llm/`

| File | Responsibility |
|------|----------------|
| `llm_factory.py` | `LLMFactory.create(provider) → BaseChatModel`; reads `OLLAMA_MODEL` from config |
| `providers/ollama.py` | `build_ollama_llm(settings) → ChatOllama`; sets base URL, model, timeout, streaming |

#### 🔢 Embedding Layer — `app/embedding/`

| File | Responsibility |
|------|----------------|
| `embedding_factory.py` | `EmbeddingFactory.create(provider) → Embeddings`; `"ollama"` or `"sentence-transformers"` |

#### 🗄️ VectorStore Layer — `app/vectorstore/`

| File | Responsibility |
|------|----------------|
| `vectorstore.py` | `VectorStoreAdapter` abstract base: `add()`, `search()`, `get_by_id()`, `delete()` |
| `chroma.py` | `ChromaAdapter(VectorStoreAdapter)` — ChromaDB `HttpClient`; circuit breaker wrapped |

#### 📥 Ingest Layer — `app/ingest/`

| File | Responsibility |
|------|----------------|
| `document_processor.py` | Orchestrate: `load → clean → chunk → batch_upsert`; return `list[doc_id]` |
| `utils/load_document.py` | `load(source, filename) → list[Document]`; PDF, DOCX, TXT, MD, raw text |
| `utils/clean.py` | `clean(docs) → list[Document]`; strip boilerplate, normalise whitespace, drop empty pages |
| `utils/chunk_with_metadata.py` | `chunk(docs) → list[Document]`; `RecursiveCharacterTextSplitter`; `doc_id = sha256(content)` |
| `utils/batch.py` | `batch_upsert(chunks, adapter) → list[str]`; deduplicates by `doc_id` before upsert |

#### ⚙️ Core Layer — `app/core/`

| File | Responsibility |
|------|----------------|
| `config.py` | `pydantic-settings` `Settings`; all env vars; singleton via `@lru_cache` |
| `logging.py` | `structlog` JSON processor; binds `request_id`, `conv_id`, `node`, `latency_ms` |
| `metrics.py` | All `prometheus_client` counters, histograms, and gauges |
| `circuit_breaker.py` | `tenacity` retry + jitter; CLOSED → OPEN → HALF-OPEN state machine |
| `security.py` | `slowapi` rate limiter; prompt injection sanitizer; PII redactor |



---

## 5. LangGraph Agent State Machine

### 5.1 State Definition

```mermaid
classDiagram
    class AgentState {
        +str question
        +str conversation_id
        +str request_id
        +list~Message~ history
        +str rewritten_query
        +list~Document~ retrieved_docs
        +float retrieval_score
        +bool retrieval_sufficient
        +str raw_answer
        +str final_answer
        +list~str~ source_ids
        +dict metadata
        +str error
        +str __next__
    }
```

### 5.2 Full Agent Graph

```mermaid
stateDiagram-v2
    [*] --> Decide

    Decide --> QueryRewrite : needs_retrieval = True
    Decide --> DirectAnswer : simple_question = True
    Decide --> ClarifyNode : ambiguous = True

    QueryRewrite --> HybridRetrieve

    HybridRetrieve --> EvaluateRelevance

    EvaluateRelevance --> GroundingCheck : relevant_docs_found = True
    EvaluateRelevance --> IDontKnow : no_relevant_docs

    GroundingCheck --> SynthesizeAnswer : grounding_ok
    GroundingCheck --> IDontKnow : grounding_failed

    SynthesizeAnswer --> ValidateOutput

    ValidateOutput --> StreamAnswer : valid_output
    ValidateOutput --> IDontKnow : schema_parse_failed

    DirectAnswer --> StreamAnswer
    ClarifyNode --> StreamAnswer
    IDontKnow --> StreamAnswer

    StreamAnswer --> [*]
```

### 5.3 Node Descriptions

| Node | Input State Fields | Output State Fields | Description |
|---|---|---|---|
| `Decide` | `question`, `history` | `__next__`, `rewritten_query` | Classifier: direct / RAG / clarify |
| `QueryRewrite` | `question`, `history` | `rewritten_query` | LLM rewrites question for retrieval |
| `HybridRetrieve` | `rewritten_query`, metadata filters | `retrieved_docs` | Dense + BM25 → RRF fusion |
| `EvaluateRelevance` | `retrieved_docs`, `rewritten_query` | `retrieval_sufficient`, `retrieval_score` | Scores relevance; routes accordingly |
| `GroundingCheck` | `retrieved_docs` | `grounding_ok` | Verifies answer claims vs. docs |
| `SynthesizeAnswer` | `retrieved_docs`, `rewritten_query`, `history` | `raw_answer`, `source_ids` | LLM streams final answer |
| `ValidateOutput` | `raw_answer` | `final_answer` or `error` | Pydantic schema parse; rejects hallucinations |
| `DirectAnswer` | `question`, `history` | `final_answer` | LLM answers directly without retrieval |
| `ClarifyNode` | `question` | `final_answer` | Returns clarification question to user |
| `IDontKnow` | `question` | `final_answer` | Structured 'I don't know' with ingestion hint |
| `StreamAnswer` | `final_answer`, `source_ids`, `metadata` | — | SSE stream emitter (terminal node) |

---

## 6. Request Lifecycle & Data Flow

### 6.1 Chat Request (Happy Path)

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant MW as Middleware
    participant API as ChatRouter
    participant G as LangGraph Agent
    participant RW as QueryRewrite Node
    participant RET as HybridRetrieve Node
    participant VS as VectorStore
    participant OL as Ollama
    participant SYN as Synthesize Node
    participant ST as StreamAnswer Node

    C->>MW: POST /chat {question, conv_id}
    MW->>MW: Inject X-Request-ID, rate-limit check
    MW->>API: Forward validated request
    API->>G: Invoke graph (async stream)
    G->>RW: question + history
    RW->>OL: Rewrite prompt
    OL-->>RW: rewritten_query
    RW->>RET: rewritten_query
    RET->>VS: Dense search (top_k)
    VS-->>RET: doc_vectors
    RET->>VS: BM25 keyword search
    VS-->>RET: bm25_results
    RET->>RET: RRF fusion → ranked_docs
    RET->>SYN: ranked_docs + rewritten_query
    SYN->>OL: Synthesize with context (streaming)
    loop Token stream
        OL-->>SYN: token chunk
        SYN-->>ST: partial answer
        ST-->>C: data: {"chunk":"...","type":"token"} SSE
    end
    ST-->>C: data: {"type":"done","sources":[...],"latency_ms":420} SSE
    C->>C: Close SSE connection
```

### 6.2 Client Disconnect Handling

```mermaid
flowchart LR
    A[Client connects] --> B{Client disconnects?}
    B -- No --> C[Normal streaming]
    B -- Yes --> D[asyncio CancelledError raised]
    D --> E[Graph run cancelled]
    E --> F[Background coroutines cleaned up]
    F --> G[Structured log: client_disconnect]
    G --> H[Metrics: disconnect_counter++]
```

---

## 7. Ingestion Pipeline

```mermaid
flowchart TD
    A([📄 Input: File / Raw Text / URL]) --> B[DocLoader<br/>pdf · txt · md · docx]
    B --> C[TextSplitter<br/>RecursiveCharacterTextSplitter<br/>chunk_size=512 overlap=64]
    C --> D[MetadataEnricher<br/>source · timestamp · tag · page_num]
    D --> E[EmbeddingService<br/>Ollama nomic-embed-text]
    E --> F{Batch Upsert}
    F --> G[(ChromaDB / Qdrant<br/>Collection: docs)]
    G --> H[Return: list of doc_ids + status]
    
    style A fill:#4f46e5,color:#fff
    style G fill:#0891b2,color:#fff
    style H fill:#059669,color:#fff
```

### 7.1 Chunking Strategy

| Parameter | Value | Config Key |
|---|---|---|
| Chunk size | 512 chars | `CHUNK_SIZE` |
| Overlap | 64 chars | `CHUNK_OVERLAP` |
| Splitter | `RecursiveCharacterTextSplitter` | — |
| Separators | `["\n\n", "\n", ".", " "]` | — |
| Metadata fields | `source`, `tag`, `page`, `timestamp`, `doc_id` | — |

---

## 8. API Contract

### 8.1 Endpoints Summary

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/ingest` | API Key | Upload documents into the vector store |
| `POST` | `/chat` | API Key | Stream agent response (SSE) |
| `GET` | `/health` | Public | Liveness probe |
| `GET` | `/ready` | Public | Readiness: Ollama + VectorDB ping |
| `GET` | `/metrics` | Internal | Prometheus metrics scrape endpoint |
| `GET` | `/docs` | Dev only | OpenAPI / Swagger UI |

---

### 8.2 POST /ingest

**Request**
```json
{
  "text": "Optional raw text content",
  "filename": "policy.pdf",
  "content_base64": "...",
  "metadata": {
    "tag": "policy",
    "author": "hr-team"
  }
}
```

**Response** `200 OK`
```json
{
  "doc_ids": ["a1b2c3", "d4e5f6"],
  "chunks_created": 12,
  "status": "ok"
}
```

---

### 8.3 POST /chat (SSE Stream)

**Request**
```json
{
  "question": "What are the refund policies?",
  "conversation_id": "conv-uuid-1234",
  "metadata": { "tag": "policy" }
}
```

**SSE Event Stream**
```
data: {"type": "token", "chunk": "The refund policy states"}

data: {"type": "token", "chunk": " that items must be returned within 30 days."}

data: {"type": "done", "sources": [{"doc_id": "a1b2c3", "title": "policy.pdf", "page": 4}], "latency_ms": 843, "token_count": 56, "retrieval_score": 0.91}
```

**Error Event**
```
data: {"type": "error", "code": "RETRIEVAL_EMPTY", "message": "No relevant documents found. Please ingest documents on this topic."}

data: {"type": "error", "code": "OLLAMA_TIMEOUT", "message": "LLM service timed out. Try again."}
```

---

### 8.4 Pydantic Schema Diagram

```mermaid
classDiagram
    class ChatRequest {
        +str question
        +str conversation_id
        +Optional~dict~ metadata
        +Optional~list~ history
    }

    class ChatTokenEvent {
        +Literal~token~ type
        +str chunk
    }

    class ChatDoneEvent {
        +Literal~done~ type
        +list~Source~ sources
        +int latency_ms
        +Optional~int~ token_count
        +float retrieval_score
    }

    class ChatErrorEvent {
        +Literal~error~ type
        +str code
        +str message
    }

    class IngestRequest {
        +Optional~str~ text
        +Optional~str~ filename
        +Optional~str~ content_base64
        +Optional~dict~ metadata
    }

    class IngestResponse {
        +list~str~ doc_ids
        +int chunks_created
        +str status
    }

    class Source {
        +str doc_id
        +str title
        +Optional~int~ page
        +Optional~str~ snippet
    }

    ChatDoneEvent --> Source
```

---

## 9. Infrastructure & Docker Topology

### 9.1 Docker Compose Network

```mermaid
graph TB
    subgraph Host Machine
        subgraph docker_net [Docker Network: rag_net]
            API["🐍 api<br/>FastAPI :8000<br/>Healthcheck: GET /health"]
            CHROMA["🔵 chroma<br/>ChromaDB :8001<br/>Healthcheck: GET /api/v1/heartbeat"]
            OLLAMA["🦙 ollama<br/>Ollama :11434<br/>Healthcheck: GET /api/version"]
            OTEL["📡 otel-collector<br/>:4317 gRPC, :8888 metrics"]
        end

        VOL_CHROMA[("📦 chroma_data<br/>persistent volume")]
        VOL_OLLAMA[("📦 ollama_models<br/>persistent volume")]
        VOL_LOGS[("📦 app_logs")]
    end

    CLIENT["👤 Client"] -- ":8000" --> API
    ADMIN["🔧 Admin / Prometheus"] -- ":9090" --> API
    API --> CHROMA
    API --> OLLAMA
    API --> OTEL
    CHROMA --> VOL_CHROMA
    OLLAMA --> VOL_OLLAMA
    API --> VOL_LOGS
```

### 9.2 Dockerfile — Multi-Stage Build

```mermaid
flowchart LR
    A[python:3.11-slim<br/> BUILD STAGE] -->|Copy pyproject.toml<br/>pip install deps| B[Builder Layer]
    B -->|Copy only app/ code| C[python:3.11-slim<br/> RUNTIME STAGE]
    C -->|Non-root user<br/>HEALTHCHECK<br/>CMD uvicorn| D[🐳 Final Image<br/>~180MB]
```

### 9.3 Health Check Chain

```mermaid
sequenceDiagram
    participant ORC as Orchestrator (compose)
    participant API
    participant OL as Ollama
    participant VDB as ChromaDB

    ORC->>API: GET /health (liveness)
    API-->>ORC: 200 {"status":"ok"}

    ORC->>API: GET /ready (readiness)
    API->>OL: GET /api/version
    OL-->>API: 200
    API->>VDB: GET /api/v1/heartbeat
    VDB-->>API: 200
    API-->>ORC: 200 {"ollama":"up","vectordb":"up"}
```

---

## 10. Observability Design

### 10.1 Three Pillars

```mermaid
mindmap
  root((Observability))
    Logs
      structlog JSON
      Fields: request_id · conv_id · node · latency_ms · level
      Output: stdout → Docker log driver
      Rotation: via compose log-opt
    Metrics
      prometheus_client
      Endpoints: /metrics
      Counters: requests_total · errors_total · retrieval_empty_total
      Histograms: request_latency_seconds · retrieval_latency_seconds · llm_latency_seconds
      Gauges: active_connections
    Traces
      OpenTelemetry Python SDK
      Span per node in LangGraph
      Propagate: X-Request-ID → trace_id
      Exporter: OTLP gRPC → otel-collector → stdout/Jaeger
```

### 10.2 Example Structured Log Entry

```json
{
  "timestamp": "2026-02-26T15:30:00.123Z",
  "level": "info",
  "request_id": "req-abc-123",
  "conv_id": "conv-uuid-1234",
  "node": "hybrid_retrieve",
  "latency_ms": 145,
  "docs_retrieved": 4,
  "retrieval_score": 0.87,
  "event": "retrieval_complete"
}
```

### 10.3 Metrics Reference

| Metric Name | Type | Labels | Description |
|---|---|---|---|
| `rag_requests_total` | Counter | `endpoint`, `status` | Total API requests |
| `rag_request_latency_seconds` | Histogram | `endpoint` | End-to-end latency |
| `rag_llm_latency_seconds` | Histogram | `model` | Ollama call latency |
| `rag_retrieval_latency_seconds` | Histogram | — | Vector DB query time |
| `rag_retrieval_empty_total` | Counter | — | Times retrieval returned nothing |
| `rag_active_connections` | Gauge | — | Open SSE connections |
| `rag_circuit_breaker_state` | Gauge | `service` | 0=closed 1=open 2=half-open |

---

## 11. Security Model

### 11.1 Security Layers

```mermaid
flowchart TD
    A([Incoming Request]) --> B[TLS Termination<br/>Nginx / API Gateway]
    B --> C[API Key Validation<br/>X-API-Key header]
    C --> D[Rate Limiter<br/>slowapi: 60 req/min/IP]
    D --> E[Input Validation<br/>Pydantic schemas]
    E --> F[Request ID Injection]
    F --> G[Agent Execution]
    G --> H[Context Sanitizer<br/>Strip injection patterns from retrieved docs]
    H --> I[PII Redactor<br/>emails · phone numbers → REDACTED]
    I --> J[LLM Call]
    J --> K[Output Schema Validator<br/>Pydantic output parser]
    K --> L([Response Stream])

    style B fill:#7c3aed,color:#fff
    style D fill:#dc2626,color:#fff
    style H fill:#d97706,color:#fff
    style I fill:#d97706,color:#fff
```

### 11.2 Threat Model

| Threat | Mitigation | Layer |
|---|---|---|
| Prompt injection via docs | Sanitize context; treat retrieved text as untrusted | `security.py` |
| API abuse / DDoS | Rate limiting per IP + API key | Middleware |
| Secret leakage | `.env` in `.gitignore`; pre-commit hook blocks `*.env` | DevOps |
| Insecure deserialization | Pydantic strict validation; no `eval` / `exec` | Schemas |
| PII exposure in logs | PII redactor node before LLM call | `nodes.py` |
| Dependency vulnerabilities | `pip-audit` in CI; Dependabot alerts | CI/CD |
| Unbound resource use | Timeouts: `OLLAMA_TIMEOUT_S`, `RETRIEVAL_TIMEOUT_S` | `circuit_breaker.py` |

---

## 12. Testing Strategy

### 12.1 Test Pyramid

```mermaid
graph TD
    A["🔺 E2E Tests<br/>Docker Compose Up → ingest → /chat<br/>Marker: integration"] 
    B["🔷 Integration Tests<br/>testcontainers · ChromaDB in-container<br/>Marker: integration"]
    C["🟦 Unit Tests<br/>pytest · mocked Ollama · mocked VectorDB<br/>Fast · No I/O"]

    A --> B --> C

    style A fill:#dc2626,color:#fff
    style B fill:#d97706,color:#fff
    style C fill:#059669,color:#fff
```

### 12.2 Test Matrix

| Test Case | Module | Strategy |
|---|---|---|
| Empty retrieval → `IDontKnow` path | `test_graph.py` | Mock VS returns `[]`; assert node = IDontKnow |
| Retrieval N docs → citations in metadata | `test_graph.py` | Mock VS returns docs; assert `source_ids` populated |
| Ollama timeout → 504 / streamed error | `test_routes_chat.py` | Mock Ollama raises `asyncio.TimeoutError` |
| Streaming: first chunk < 500ms | `test_routes_chat.py` | `time.monotonic()` before/after first SSE event |
| Ingest: chunks created correctly | `test_retrieval.py` | Assert chunk count = `ceil(len/chunk_size)` |
| Rate limit exceeded → 429 | `test_routes_chat.py` | Send 61 requests in 1 min |
| Schema validation reject bad input | `test_schemas.py` | Pydantic raises `ValidationError` |
| Circuit breaker opens after N failures | `test_circuit_breaker.py` | Simulate N Ollama failures; assert `CircuitOpen` |
| Client disconnect cancels agent | `test_routes_chat.py` | Close connection mid-stream; assert no leaked tasks |
| PII redaction removes emails | `test_security.py` | Pass text with email; assert output is `REDACTED` |

### 12.3 Running Tests

```bash
# Unit tests only (no Ollama, no DB needed)
pytest tests/ -m "not integration" -v

# Integration tests (requires Docker)
docker compose -f docker-compose.test.yml up -d
pytest tests/ -m integration -v

# Coverage report
pytest tests/ -m "not integration" --cov=app --cov-report=html
```

---

## 13. Repository Layout (Final)

```
agentic_rag/
│
├── app/
│   ├── main.py                              # FastAPI app factory + lifespan + middleware registration
│   │
│   ├── api/
│   │   └── v1/
│   │       ├── chat.py                      # POST /chat  — SSE streaming endpoint
│   │       ├── ingest.py                    # POST /ingest — document ingestion endpoint
│   │       └── models/
│   │           ├── chat.py                  # ChatRequest · ChatTokenEvent · ChatDoneEvent · ChatErrorEvent · Source
│   │           └── ingest.py                # IngestRequest · IngestResponse
│   │
│   ├── agent/
│   │   ├── state.py                         # AgentState TypedDict (single source of truth)
│   │   ├── graph.py                         # StateGraph compiler — nodes + conditional edges
│   │   │
│   │   ├── nodes/                           # PURE reasoning nodes (no I/O side-effects)
│   │   │   ├── decide.py                    # Classify intent → route: rag / direct / clarify
│   │   │   ├── query_rewrite.py             # Rewrite question for retrieval
│   │   │   ├── retrieve.py                  # Dense + BM25 (in-process) → RRF fusion
│   │   │   ├── evaluate_relevance.py        # Score relevance → retrieval_sufficient flag + metric
│   │   │   ├── grounding_check.py           # Verify claims vs retrieved docs
│   │   │   ├── synthesize.py                # Streaming LLM synthesis with context
│   │   │   ├── validate_output.py           # Pydantic output parse → final_answer or error
│   │   │   ├── direct_answer.py             # LLM answer with no retrieval
│   │   │   ├── clarify.py                   # Generate clarification question
│   │   │   ├── no_answer.py                 # Structured 'I don't know' + ingest hint
│   │   │   └── stream_answer.py             # Terminal SSE emitter node
│   │   │
│   │   ├── tools/                           # SIDE-EFFECT tools (called via LangGraph ToolNode)
│   │   │   ├── lookup_by_id.py              # Fetch full doc by ID + cross-encoder re-rank
│   │   │   └── memory_store.py              # Read / write conversation summaries
│   │   │
│   │   └── memory/
│   │       └── memory.py                    # store_summary() + retrieve_context(); TTL + max-N safeguards
│   │
│   ├── llm/
│   │   ├── llm_factory.py                   # LLMFactory.create(provider) → BaseChatModel
│   │   └── providers/
│   │       └── ollama.py                    # build_ollama_llm(settings) → ChatOllama
│   │
│   ├── embedding/
│   │   └── embedding_factory.py             # EmbeddingFactory.create(provider) → Embeddings
│   │
│   ├── vectorstore/
│   │   ├── vectorstore.py                   # VectorStoreAdapter abstract interface
│   │   └── chroma.py                        # ChromaAdapter — concrete ChromaDB implementation
│   │
│   ├── ingest/
│   │   ├── document_processor.py            # Orchestrates: load → clean → chunk → batch_upsert
│   │   └── utils/
│   │       ├── load_document.py             # load(source, filename) → list[Document]
│   │       ├── clean.py                     # clean(docs) → list[Document]
│   │       ├── chunk_with_metadata.py       # chunk(docs, size, overlap) → list[Document] + sha256 IDs
│   │       └── batch.py                     # batch_upsert(chunks, adapter) → list[doc_id]
│   │
│   └── core/
│       ├── config.py                        # pydantic-settings Settings; all env vars; @lru_cache singleton
│       ├── logging.py                       # structlog JSON processor
│       ├── metrics.py                       # prometheus_client instruments
│       ├── circuit_breaker.py               # tenacity retry + CLOSED/OPEN/HALF-OPEN state machine
│       └── security.py                      # Rate limiter · prompt sanitizer · PII redactor
│
├── tests/
│   ├── conftest.py                          # Fixtures: mock LLM, mock VectorStoreAdapter
│   ├── agent/
│   │   ├── test_graph.py                    # Graph transition tests (all conditional edges)
│   │   ├── test_nodes.py                    # Unit test each node in isolation
│   │   └── test_tools.py                    # lookup_by_id, memory_store tests
│   ├── api/
│   │   ├── test_chat.py                     # SSE stream, disconnect, rate-limit tests
│   │   └── test_ingest.py                   # Ingest endpoint validation tests
│   ├── ingest/
│   │   └── test_document_processor.py       # load → clean → chunk → batch pipeline tests
│   ├── vectorstore/
│   │   └── test_chroma_adapter.py           # ChromaAdapter unit tests (mocked client)
│   ├── test_circuit_breaker.py              # Circuit breaker state machine tests
│   └── test_security.py                     # Rate limit, sanitizer, PII redaction tests
│
├── Dockerfile                               # Multi-stage: builder + slim runtime, non-root user
├── docker-compose.yml                       # api · ollama · chroma · otel-collector + volumes
├── docker-compose.test.yml                  # Test compose (in-memory ChromaDB, mock Ollama)
├── .env.example                             # All env vars documented, no secrets
├── pyproject.toml                           # Project metadata, deps, mypy, ruff, pytest config
├── Makefile                                 # lint · test · format · compose-up · coverage
├── .pre-commit-config.yaml                  # ruff, black, isort, detect-secrets hooks
├── .github/
│   └── workflows/
│       └── ci.yml                           # GitHub Actions: lint + unit tests + Docker build
└── README.md                                # Setup, curl examples, known limitations
```



---

## 14. Technology Decision Record

### TDR-001: Vector Database — ChromaDB

| Factor | ChromaDB | Qdrant | pgvector |
|---|---|---|---|
| Setup complexity | ✅ Minimal | 🟡 Medium | 🔴 High |
| Hybrid retrieval | 🟡 Via plugin | ✅ Built-in | 🟡 Custom |
| Persistence | ✅ DuckDB+Parquet | ✅ WAL | ✅ PostgreSQL |
| Production scale | 🟡 Medium | ✅ High | ✅ High |
| **Decision** | **Default** | **Swap-in** | — |

> **Decision**: ChromaDB as default (easy local dev), Qdrant as production swap via the `VectorStoreAdapter` abstraction.

---

### TDR-002: Streaming — SSE over WebSocket

| Factor | SSE | WebSocket |
|---|---|---|
| Simplicity | ✅ HTTP/1.1 native | 🔴 Protocol upgrade |
| Reconnection | ✅ Auto (browser) | 🔴 Manual |
| Unidirectional | ✅ Perfect fit (server → client) | 🟡 Overkill |
| Proxy support | ✅ Standard | 🟡 Needs config |
| **Decision** | **✅ SSE** | — |

---

### TDR-003: LLM Runtime — Ollama

| Factor | Value |
|---|---|
| Zero cloud cost | ✅ 100% local inference |
| Model variety | llama3, mistral, qwen2.5, phi-3 |
| Embedding support | nomic-embed-text, mxbai-embed |
| Docker image | `ollama/ollama` official |
| API compatibility | OpenAI-compatible REST |

---

### TDR-004: Agent Orchestration — LangGraph

| Factor | LangGraph | Plain LangChain | Custom FSM |
|---|---|---|---|
| Explicit state | ✅ TypedDict | 🔴 Implicit | 🟡 Manual |
| Conditional routing | ✅ First-class | 🟡 Chains | ✅ Manual |
| Testability | ✅ Node-by-node | 🟡 End-to-end | ✅ |
| Streaming support | ✅ Native | 🟡 Partial | 🔴 Manual |
| **Decision** | **✅ LangGraph** | — | — |

---

## 15. Evaluation & Rubric Mapping

| Category | Weight | How This Design Addresses It |
|---|---|---|
| **Architecture** | 25% | Clear C4 layers (API → Agent → RAG → Core); adapter pattern for VectorDB; single-responsibility nodes; no coupling between layers |
| **Correctness** | 25% | Grounding check node; IDontKnow path for empty retrieval; Pydantic output parser; circuit breaker; timeout handling |
| **Tests** | 20% | Comprehensive unit tests; mock Ollama + VectorDB fixtures; 10+ targeted test cases; edge cases covered |
| **Ops / Docker** | 15% | One-command `docker compose up`; health + readiness probes; volume persistence; multi-stage Dockerfile; `.env` driven |
| **Code Quality** | 15% | mypy strict; ruff + black; structlog; pre-commit hooks; CI workflow; typed LangGraph state |

---

## 16. Suggested Development Timeline

```mermaid
gantt
    title Development Timeline (4 Days)
    dateFormat  YYYY-MM-DD
    section Day 1 — Foundation
    Skeleton FastAPI app + config        :d1a, 2026-02-26, 4h
    docker-compose + Ollama + Chroma     :d1b, after d1a, 3h
    Health + readiness endpoints + tests :d1c, after d1b, 1h

    section Day 2 — RAG Core
    Embeddings + VectorStore adapter     :d2a, 2026-02-27, 3h
    Ingestion pipeline + chunking        :d2b, after d2a, 2h
    Retrieval module + unit tests        :d2c, after d2b, 3h

    section Day 3 — Agent + Streaming
    LangGraph graph + all nodes          :d3a, 2026-02-28, 4h
    SSE streaming endpoint               :d3b, after d3a, 2h
    Graph tests + streaming test         :d3c, after d3b, 2h

    section Day 4 — Polish + Add-ons
    Observability: logs + metrics + OTEL :d4a, 2026-03-01, 2h
    Security: rate limit + sanitizer     :d4b, after d4a, 2h
    Hybrid retrieval + re-ranking        :d4c, after d4b, 2h
    README + .env.example + CI           :d4d, after d4c, 2h
```

---

## 17. LangGraph Agent — Full Graph Logic

This section provides a complete visual specification of the LangGraph agent: every node, every edge (including conditional edges), data flowing through state, and the terminal SSE streaming path.

---

### 17.1 Complete Node & Edge Map

```mermaid
flowchart TD
    START(["▶ START\n{question, conv_id, history}"])

    DECIDE["🔀 Decide\nClassify intent:\ndirect / rag / clarify"]

    DIRECT["💬 DirectAnswer\nLLM answers with\nno retrieval"]

    CLARIFY["❓ ClarifyNode\nAsk user for\nclarification"]

    REWRITE["✏️ QueryRewrite\nRewrite question\nfor better retrieval"]

    RETRIEVE["🔍 HybridRetrieve\nDense search + BM25\n→ RRF fusion"]

    EVAL["📊 EvaluateRelevance\nScore doc relevance\nLog metric"]

    IDK1["🚫 IDontKnow\n'Retrieval empty or\nirrelevant'\n+ ingest hint"]

    GROUND["🔐 GroundingCheck\nVerify claims vs docs\nDetect hallucination risk"]

    IDK2["🚫 IDontKnow\n'Cannot ground answer\nin documents'"]

    SYNTH["🧠 SynthesizeAnswer\nLLM streams answer\nwith doc context"]

    VALID["✅ ValidateOutput\nPydantic parse\nreject bad schema"]

    IDK3["🚫 IDontKnow\n'Output schema failed'\n+ fallback message"]

    STREAM(["📡 StreamAnswer\nSSE terminal node\nEmit token chunks\n+ done event"])

    START --> DECIDE

    DECIDE -->|route = direct| DIRECT
    DECIDE -->|route = clarify| CLARIFY
    DECIDE -->|route = rag| REWRITE

    REWRITE --> RETRIEVE

    RETRIEVE --> EVAL

    EVAL -->|retrieval_sufficient = True| GROUND
    EVAL -->|retrieval_sufficient = False| IDK1

    GROUND -->|grounding_ok = True| SYNTH
    GROUND -->|grounding_ok = False| IDK2

    SYNTH --> VALID

    VALID -->|parse_ok = True| STREAM
    VALID -->|parse_ok = False| IDK3

    DIRECT  --> STREAM
    CLARIFY --> STREAM
    IDK1    --> STREAM
    IDK2    --> STREAM
    IDK3    --> STREAM

    STREAM --> END(["⏹ END"])

    style START  fill:#4f46e5,color:#fff,stroke:#3730a3
    style END    fill:#059669,color:#fff,stroke:#047857
    style STREAM fill:#0891b2,color:#fff,stroke:#0e7490
    style DECIDE fill:#7c3aed,color:#fff
    style EVAL   fill:#d97706,color:#fff
    style GROUND fill:#d97706,color:#fff
    style VALID  fill:#d97706,color:#fff
    style IDK1   fill:#dc2626,color:#fff
    style IDK2   fill:#dc2626,color:#fff
    style IDK3   fill:#dc2626,color:#fff
    style SYNTH  fill:#0f766e,color:#fff
```

---

### 17.2 AgentState Data Flow Through Each Node

This diagram shows **which fields each node reads and writes** in the shared `AgentState`.

```mermaid
flowchart LR
    subgraph STATE ["📦 AgentState (TypedDict)"]
        direction TB
        Q[question]
        CID[conversation_id]
        RID[request_id]
        HIST[history]
        RQ[rewritten_query]
        RDOCS[retrieved_docs]
        RSCORE[retrieval_score]
        RSUFF[retrieval_sufficient]
        GROUND_OK[grounding_ok]
        RAWANS[raw_answer]
        FANS[final_answer]
        SIDS[source_ids]
        META[metadata]
        ROUTE[route]
        ERR[error]
    end

    subgraph NODES ["🤖 Graph Nodes"]
        N1["Decide\n─────────────\nREADS: question, history\nWRITES: route"]
        N2["QueryRewrite\n─────────────\nREADS: question, history\nWRITES: rewritten_query"]
        N3["HybridRetrieve\n─────────────\nREADS: rewritten_query, metadata\nWRITES: retrieved_docs"]
        N4["EvaluateRelevance\n─────────────\nREADS: retrieved_docs, rewritten_query\nWRITES: retrieval_score, retrieval_sufficient"]
        N5["GroundingCheck\n─────────────\nREADS: retrieved_docs, rewritten_query\nWRITES: grounding_ok"]
        N6["SynthesizeAnswer\n─────────────\nREADS: retrieved_docs, rewritten_query, history\nWRITES: raw_answer, source_ids"]
        N7["ValidateOutput\n─────────────\nREADS: raw_answer\nWRITES: final_answer OR error"]
        N8["DirectAnswer\n─────────────\nREADS: question, history\nWRITES: final_answer"]
        N9["ClarifyNode\n─────────────\nREADS: question\nWRITES: final_answer"]
        N10["IDontKnow\n─────────────\nREADS: question\nWRITES: final_answer, error"]
        N11["StreamAnswer\n─────────────\nREADS: final_answer, source_ids, metadata\nWRITES: (streams to client)"]
    end
```

---

### 17.3 Conditional Edge Logic (Router Functions)

```mermaid
flowchart TD
    subgraph ROUTER_DECIDE ["after_decide()"]
        D1{state.route}
        D1 -->|== 'rag'| E1["→ query_rewrite"]
        D1 -->|== 'direct'| E2["→ direct_answer"]
        D1 -->|== 'clarify'| E3["→ clarify"]
    end

    subgraph ROUTER_EVAL ["after_evaluate()"]
        D2{state.retrieval_sufficient}
        D2 -->|True| E4["→ grounding_check"]
        D2 -->|False| E5["→ i_dont_know"]
    end

    subgraph ROUTER_GROUND ["after_grounding()"]
        D3{state.grounding_ok}
        D3 -->|True| E6["→ synthesize"]
        D3 -->|False| E7["→ i_dont_know"]
    end

    subgraph ROUTER_VALID ["after_validate()"]
        D4{state.error == None}
        D4 -->|True| E8["→ stream_answer"]
        D4 -->|False| E9["→ i_dont_know"]
    end
```

---

### 17.4 Memory Integration Loop

Conversation summaries are stored in ChromaDB and retrieved each turn to provide long-term context without growing unbounded.

```mermaid
sequenceDiagram
    participant C  as Client
    participant G  as LangGraph Agent
    participant M  as memory.py
    participant VS as ChromaDB (memory collection)
    participant LLM as Ollama

    C->>G: POST /chat {question, conv_id}

    G->>M: retrieve_conversation_context(conv_id)
    M->>VS: similarity_search(conv_id, top_k=3)
    VS-->>M: [past summaries]
    M-->>G: context_string (injected into history)

    Note over G: Agent runs full graph with enriched history

    G->>LLM: Synthesize answer (with past context)
    LLM-->>G: final_answer

    G->>M: store_conversation_summary(conv_id, summary)
    M->>LLM: Summarize exchange in 2-3 sentences
    LLM-->>M: summary_text
    M->>VS: add_document(summary_text, metadata={conv_id, timestamp})

    G-->>C: SSE stream response
```

---

### 17.5 SSE Streaming Terminal Path

`StreamAnswer` is the terminal node that converts `AgentState` into an SSE event stream.

```mermaid
flowchart TD
    A["StreamAnswer node receives AgentState\nfinal_answer · source_ids · metadata · retrieval_score · latency_ms"]

    A --> B{Is answer a\nstreaming generator?}

    B -->|Yes — from SynthesizeAnswer| C["Iterate token chunks\nfrom LLM stream"]
    C --> D["Yield SSE token event\ndata: {type:'token', chunk:'...'}"]
    D -->|more chunks| C
    D -->|stream done| E

    B -->|No — static string| F["Chunk string into\nN-char pieces"]
    F --> G["Yield SSE token events"]
    G --> E

    E["Yield SSE done event\ndata: {type:'done',\nsources:[...],\nlatency_ms:...,\nretrieval_score:...}"]

    E --> H{Client disconnected?}
    H -->|Yes| I["asyncio.CancelledError\ncancel background tasks\nlog client_disconnect\nincrement disconnect_counter metric"]
    H -->|No| J["Close SSE generator\nclean up"]

    style A fill:#0891b2,color:#fff
    style E fill:#059669,color:#fff
    style I fill:#dc2626,color:#fff
```

---

### 17.6 Tool Nodes (LangChain Tools Called Inside Agent)

```mermaid
flowchart LR
    subgraph TOOL_NODE ["ToolNode (invoked by SynthesizeAnswer or Decide)"]
        T1["🔧 lookup_by_id(doc_id)\n──────────────────────\n1. Fetch full document from ChromaDB by ID\n2. Run cross-encoder re-rank against query\n3. Return top-scored Document"]

        T2["🔍 metadata_filter_search(query, filters)\n──────────────────────\n1. Apply metadata filters to collection query\n   (e.g. tag='policy', author='hr-team')\n2. Dense similarity search within filtered set\n3. Return top-K filtered Documents"]
    end

    A["SynthesizeAnswer\nor Decide node"] -->|tool_call| TOOL_NODE
    TOOL_NODE -->|Document result| A
```

---

### 17.7 Node Implementation Summary

| # | Node | File | LLM Call? | Output Fields |
|---|------|------|-----------|---------------|
| 1 | `Decide` | `nodes/decide.py` | ✅ Yes (classifier prompt) | `route` |
| 2 | `QueryRewrite` | `nodes/query_rewrite.py` | ✅ Yes | `rewritten_query` |
| 3 | `HybridRetrieve` | `nodes/retrieve.py` | ❌ No (vector ops) | `retrieved_docs` |
| 4 | `EvaluateRelevance` | `nodes/evaluate_relevance.py` | ❌ No (cosine sim) | `retrieval_score`, `retrieval_sufficient` |
| 5 | `GroundingCheck` | `nodes/grounding_check.py` | ✅ Yes (verifier prompt) | `grounding_ok` |
| 6 | `SynthesizeAnswer` | `nodes/synthesize.py` | ✅ Yes (streaming) | `raw_answer`, `source_ids` |
| 7 | `ValidateOutput` | `nodes/validate_output.py` | ❌ No (Pydantic parse) | `final_answer` or `error` |
| 8 | `DirectAnswer` | `nodes/direct_answer.py` | ✅ Yes | `final_answer` |
| 9 | `ClarifyNode` | `nodes/clarify.py` | ✅ Yes | `final_answer` |
| 10 | `IDontKnow` | `nodes/i_dont_know.py` | ❌ No (templated) | `final_answer`, `error` |
| 11 | `StreamAnswer` | `nodes/stream_answer.py` | ❌ No (SSE emit) | *(streams to client)* |

---

## Appendix A: Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `dev` | Environment: dev / staging / prod |
| `APP_HOST` | `0.0.0.0` | Bind address |
| `APP_PORT` | `8000` | HTTP port |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama service URL |
| `OLLAMA_MODEL` | `llama3` | Chat model to use |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `OLLAMA_TIMEOUT_S` | `60` | LLM call timeout (seconds) |
| `VECTOR_DB` | `chroma` | Backend: `chroma` or `qdrant` |
| `CHROMA_HOST` | `chroma` | ChromaDB hostname |
| `CHROMA_PORT` | `8001` | ChromaDB port |
| `CHROMA_COLLECTION` | `docs` | Collection name |
| `TOP_K` | `4` | Documents to retrieve |
| `MAX_CONTEXT_CHARS` | `12000` | Max chars fed to LLM |
| `RETRIEVAL_TIMEOUT_S` | `10` | Vector DB query timeout |
| `CHUNK_SIZE` | `512` | Document chunk size (chars) |
| `CHUNK_OVERLAP` | `64` | Chunk overlap (chars) |
| `API_KEY` | *(required)* | Service authentication key |
| `RATE_LIMIT` | `60/minute` | Per-IP rate limit |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel:4317` | OpenTelemetry collector |
| `ENABLE_PII_REDACTION` | `true` | Enable PII redaction |
| `CIRCUIT_BREAKER_THRESHOLD` | `5` | Failures before circuit opens |
| `CIRCUIT_BREAKER_RESET_S` | `30` | Seconds before half-open |

---

## Appendix B: Key Dependencies

```toml
# pyproject.toml (key deps)
[project]
dependencies = [
  "fastapi>=0.111",
  "uvicorn[standard]>=0.29",
  "langchain>=0.2",
  "langchain-community>=0.2",
  "langgraph>=0.1",
  "langchain-ollama>=0.1",
  "chromadb>=0.5",
  "pydantic>=2.7",
  "pydantic-settings>=2.3",
  "structlog>=24.1",
  "prometheus-client>=0.20",
  "opentelemetry-sdk>=1.24",
  "opentelemetry-exporter-otlp>=1.24",
  "tenacity>=8.3",
  "slowapi>=0.1.9",
  "python-multipart>=0.0.9",
  "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2",
  "pytest-asyncio>=0.23",
  "pytest-cov>=5.0",
  "httpx>=0.27",
  "ruff>=0.4",
  "black>=24.4",
  "mypy>=1.10",
  "pre-commit>=3.7",
]
```

---

*Document generated by AI Architect · Agentic RAG System · 2026-02-26*
