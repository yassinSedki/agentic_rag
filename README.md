# Agentic RAG API

A production-grade **Retrieval-Augmented Generation (RAG)** API that streams answers token-by-token using a stateful LangGraph agent, hybrid document retrieval, and a **fully local stack** — both the LLM and the embedding model run through [Ollama](https://ollama.com) on your own machine. No cloud API keys, no external inference calls, no data leaving your environment.

---

## What It Does

1. You upload documents (PDF, DOCX, TXT, MD).
2. The system chunks, embeds, and stores them in a local ChromaDB vector store.
3. You ask questions via a streaming HTTP endpoint.
4. A LangGraph agent classifies your intent, rewrites your query, retrieves the most relevant document chunks using hybrid search (dense vectors + BM25 + RRF fusion), builds a grounded prompt, and streams the LLM answer back as Server-Sent Events.
5. Conversation history is persisted in SQLite so follow-up questions have context.

---

## Architecture

```
POST /chat
    │
    ▼
LangGraph Agent
    │
    ├─ decide         ← LLM classifies intent: rag / direct / clarify
    │
    ├─[rag]──────────────────────────────────────────────┐
    │  query_rewrite  ← LLM expands query for retrieval  │
    │  retrieve       ← dense (ChromaDB) + BM25 + RRF    │
    │  evaluate       ← are docs relevant enough?        │
    │      ├─ yes → prepare_rag_generation               │
    │      └─ no  → no_answer                            │
    │                                                    │
    ├─[direct]→ prepare_direct_generation                │
    └─[clarify]→ prepare_clarify_generation              │
                                                         │
    ▼                                                    │
API layer streams LLM tokens via SSE  ◄──────────────────┘
```

**Key design decisions:**
- Nodes only *prepare* prompts; actual LLM streaming happens in the API layer. This keeps the graph fast and testable.
- `ChromaDB` runs embedded (no separate server process).
- LLM and embedder are singletons (`@lru_cache`) — model weights load once, not per request.
- The compiled graph is also cached — `build_graph()` runs once at startup.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI + Uvicorn |
| Agent orchestration | LangGraph |
| LLM inference | Ollama (local, no cloud) |
| Embeddings | Ollama `nomic-embed-text` (local — same Ollama process as the LLM) |
| Vector store | ChromaDB (embedded) |
| Sparse search | rank-bm25 |
| Streaming | sse-starlette (SSE) |
| Config | pydantic-settings |
| Logging | structlog (JSON) |
| Metrics | Prometheus (`/metrics`) |
| Tracing | OpenTelemetry (optional) |
| Resilience | Custom async circuit breaker |
| Memory | SQLite (stdlib) |
| Containerization | Docker + Docker Compose |

**Python:** 3.11+

---

## Prerequisites

- **Python 3.11+** and **Poetry**
- **Docker & Docker Compose** (recommended for running Ollama)
- **Ollama** — download from [ollama.com](https://ollama.com)

---

## Quick Start

### Option A — Docker Compose (recommended)

```bash
# 1. Clone and configure
git clone <repo-url>
cd agentic_rag
cp .env.example .env        # edit if needed

# 2. Start the API + Ollama
docker compose up -d --build

# 3. Pull models (first run only, takes a few minutes)
docker exec rag-ollama ollama pull llama3
docker exec rag-ollama ollama pull nomic-embed-text

# 4. Verify
curl http://localhost:8000/health
```

### Option B — Run Locally

```bash
# 1. Install dependencies
poetry install

# 2. Start Ollama separately
ollama serve &
ollama pull llama3
ollama pull nomic-embed-text

# 3. Configure
cp .env.example .env
# Set OLLAMA_BASE_URL=http://localhost:11434 in .env

# 4. Run the API
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Option C — Streamlit UI (for manual testing)

```bash
poetry run streamlit run frontend_streamlit.py
```

---

## Configuration

All settings are loaded from environment variables (or a `.env` file). Copy `.env.example` to `.env` to get started.

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `dev` | Environment: `dev`, `staging`, `prod`. Disables `/docs` in non-dev. |
| `APP_HOST` | `0.0.0.0` | Bind address |
| `APP_PORT` | `8000` | Listen port |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Ollama API URL |
| `OLLAMA_MODEL` | `llama3` | Chat/generation model |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `OLLAMA_TIMEOUT_S` | `60` | LLM request timeout (seconds) |
| `VECTOR_DB` | `chroma` | Vector store backend (`chroma` only for now) |
| `CHROMA_PERSISTENCE_PATH` | `./data/chroma_db` | Local path for ChromaDB storage |
| `CHROMA_COLLECTION` | `docs` | ChromaDB collection name |
| `TOP_K` | `4` | Number of documents to retrieve per query |
| `MAX_CONTEXT_CHARS` | `12000` | Max characters of context sent to the LLM |
| `CHUNK_SIZE` | `512` | Characters per text chunk when ingesting |
| `CHUNK_OVERLAP` | `64` | Overlap between consecutive chunks |
| `RATE_LIMIT` | `60/minute` | API rate limit per IP |
| `ENABLE_MEMORY` | `true` | Persist conversation history in SQLite |
| `CIRCUIT_BREAKER_THRESHOLD` | `5` | Consecutive failures before circuit opens |
| `CIRCUIT_BREAKER_RESET_S` | `30` | Seconds before circuit attempts recovery |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel:4317` | OpenTelemetry collector endpoint (optional) |
| `ENABLE_PII_REDACTION` | `true` | Redact PII from logs |

---

## API Reference

### POST /ingest — Upload a document

Parses, cleans, chunks, embeds, and stores a document in the vector store.

**Supported formats:** PDF, TXT, MD, DOCX

```bash
curl -X POST http://localhost:8000/ingest \
  -F "file=@/path/to/your/document.pdf"
```

**Response:**
```json
{
  "doc_ids": ["a1b2c3d4", "e5f6a7b8"],
  "chunks_created": 2,
  "status": "ok"
}
```

---

### POST /chat — Ask a question (SSE stream)

Runs the agent and streams the answer back as Server-Sent Events. Use `-N` with curl to disable buffering.

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the refund policy?",
    "conversation_id": "session-abc123"
  }'
```

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `question` | string | yes | The user's question |
| `conversation_id` | string | yes | Session ID for multi-turn memory |
| `metadata` | object | no | Arbitrary key/value context |
| `history` | array | no | Explicit history override (omit to load from SQLite) |

**SSE event stream:**

```
data: {"type":"token","chunk":"The refund "}
data: {"type":"token","chunk":"policy allows returns within 30 days."}
data: {"type":"done","sources":[{"doc_id":"a1b2c3d4","title":"policy.txt","page":null,"snippet":"..."}],"latency_ms":1340,"token_count":47,"retrieval_score":0.81}
```

**Event types:**

| Type | Fields | Description |
|---|---|---|
| `token` | `chunk` | One streamed token or text fragment |
| `done` | `sources`, `latency_ms`, `token_count`, `retrieval_score` | Final metadata after answer completes |
| `error` | `code`, `message` | Error during processing |

---

### GET /health — Liveness check

```bash
curl http://localhost:8000/health
# → {"status": "ok"}
```

### GET /ready — Readiness check

Verifies Ollama and ChromaDB are reachable before accepting traffic.

```bash
curl http://localhost:8000/ready
# → {"status": "ok", "ollama": "up", "vectordb": "up"}
```

### GET /metrics — Prometheus metrics

```bash
curl http://localhost:8000/metrics
```

Key metrics exposed:

| Metric | Labels | Description |
|---|---|---|
| `rag_requests_total` | `endpoint`, `status` | Request counter |
| `rag_request_latency_seconds` | `endpoint` | End-to-end latency histogram |
| `rag_llm_latency_seconds` | `model` | LLM generation latency |
| `rag_retrieval_latency_seconds` | — | Vector search + fusion latency |
| `rag_retrieval_empty_total` | — | Queries returning no documents |
| `rag_active_connections` | — | Current SSE streams open |
| `rag_circuit_breaker_state` | `service` | 0=closed, 1=open, 2=half-open |

### OpenAPI Docs (dev only)

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Project Structure

```
agentic_rag/
├── app/
│   ├── main.py                      # FastAPI factory, middleware, exception handlers
│   ├── api/v1/
│   │   ├── chat.py                  # POST /chat — SSE streaming endpoint
│   │   ├── ingest.py                # POST /ingest — file upload
│   │   ├── health.py                # GET /health, /ready
│   │   ├── router.py                # Aggregates v1 routes
│   │   └── models/                  # Pydantic request/response schemas
│   ├── agent/
│   │   ├── graph.py                 # LangGraph wiring + cached get_graph()
│   │   ├── state.py                 # AgentState TypedDict
│   │   ├── nodes/
│   │   │   ├── decide.py            # Intent classifier (rag/direct/clarify)
│   │   │   ├── query_rewrite.py     # Query expansion via LLM
│   │   │   ├── retrieve.py          # Hybrid retrieval (dense + BM25 + RRF)
│   │   │   ├── evaluate_relevance.py # Relevance threshold check
│   │   │   ├── prepare_generation.py # Prompt builders for all routes
│   │   │   └── no_answer.py         # "I don't know" fallback
│   │   ├── memory/
│   │   │   └── store.py             # SQLite conversation history
│   │   └── tools/
│   │       └── lookup_by_id.py      # Lookup a document chunk by ID
│   ├── llm/
│   │   ├── llm_factory.py           # Cached ChatOllama singleton
│   │   └── providers/ollama.py
│   ├── embedding/
│   │   ├── embedding_factory.py     # Cached OllamaEmbeddings singleton
│   │   └── providers/ollama.py
│   ├── vectorstore/
│   │   ├── vector_store.py          # Facade — use this, not the adapter directly
│   │   ├── base.py                  # VectorStoreAdapter ABC
│   │   ├── chroma.py                # ChromaDB implementation
│   │   └── reranker.py              # RRF + weighted fusion
│   ├── ingest/
│   │   ├── document_processor.py    # 5-stage pipeline orchestrator
│   │   └── utils/                   # load → clean → chunk → embed → upsert
│   └── core/
│       ├── config.py                # pydantic-settings (all env vars)
│       ├── exceptions.py            # Exception hierarchy
│       ├── schemas.py               # Shared domain models
│       ├── circuit_breaker.py       # Async circuit breaker decorator
│       ├── metrics.py               # Prometheus counters/histograms
│       ├── logging.py               # structlog JSON setup
│       └── security.py              # RequestId middleware, PII sanitizers
├── tests/                           # pytest suite (unit + integration)
├── frontend_streamlit.py            # Optional Streamlit UI for manual testing
├── Dockerfile                       # Multi-stage build
├── docker-compose.yml               # API + Ollama services
├── pyproject.toml                   # Poetry deps + ruff/black/mypy config
└── .env.example                     # Environment variable template
```

---

## How Retrieval Works

Each query goes through three stages:

1. **Dense search** — The query is embedded **locally** using Ollama (`nomic-embed-text`) and compared against stored chunk vectors using cosine similarity (ChromaDB HNSW index). Returns `TOP_K * 2` candidates. No external API call is made — the embedding model runs inside the same Ollama process as the LLM.

2. **BM25 keyword search** — The same dense candidates are re-scored using BM25 (term-frequency keyword matching). This catches cases where exact words matter and pure semantic search misses.

3. **Reciprocal Rank Fusion (RRF)** — Both ranked lists are merged using the formula `score = Σ 1/(k + rank)` where `k=60`. This is parameter-free and robust — it combines rank positions rather than raw scores, so it handles score-scale differences automatically.

The final `TOP_K` results are passed to the LLM as grounded context.

---

## Resilience

The vector store is wrapped with an **async circuit breaker**:

- **CLOSED** (normal): calls pass through; failures are counted.
- **OPEN** (degraded): after `CIRCUIT_BREAKER_THRESHOLD` consecutive failures, all calls are rejected immediately for `CIRCUIT_BREAKER_RESET_S` seconds. This prevents a slow/down ChromaDB from stalling the entire event loop.
- **HALF-OPEN** (recovering): after the reset window, one probe call is allowed. Success → CLOSED; failure → OPEN.

---

## Testing

```bash
# Unit tests only (no external services needed)
poetry run pytest tests/ -m "not integration" -v

# With coverage report
poetry run pytest tests/ --cov=app --cov-report=html

# Integration tests (requires running Docker stack)
poetry run pytest tests/ -m integration -v

# Lint
poetry run ruff check app/ tests/

# Type check
poetry run mypy app/
```

---

## Known Limitations & Improvement Areas

| Area | Issue | Suggested Fix |
|---|---|---|
| SQLite in async | `MemoryStore` uses blocking `sqlite3` in the async event loop | Replace with `aiosqlite` |
| CORS | Wildcard origins with credentials disabled — tighten in production | Set `allow_origins` to your specific frontend domain |
| Dead code | `synthesize.py`, `grounding_check.py`, `validate_output.py`, `stream_answer.py`, `direct_answer.py`, `clarify.py` are not wired into the graph | Delete or re-integrate into the graph as optional nodes |
| Document deletion | No API endpoint to remove ingested documents | Add `DELETE /documents/{doc_id}` |
| Auth | No authentication — anyone can ingest or query | Add API key or JWT middleware |
| ChromaDB backup | No backup strategy for the embedded vector store | Schedule periodic copies of `data/chroma_db/` |
