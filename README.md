# 🤖 Agentic RAG API

> Production-grade Retrieval-Augmented Generation API built with **FastAPI**, **LangGraph**, **Ollama**, and **ChromaDB**.

## Overview

This project implements an **agentic RAG (Retrieval-Augmented Generation)** service that:

- **Streams** LLM responses token-by-token via Server-Sent Events (SSE)
- **Retrieves** relevant documents using hybrid search (dense vectors + BM25) with RRF fusion
- **Orchestrates** routing and retrieval via a LangGraph state machine
- **Stores** embeddings in **ChromaDB** as an **embedded, local** vector store (no separate Chroma server)
- **Persists** conversation history in SQLite for multi-turn context

## ✨ Features

- **Real-time SSE streaming** — tokens stream as the LLM generates them (no buffering)
- **Hybrid retrieval** — dense vector search + BM25 keyword search with Reciprocal Rank Fusion
- **Intent-based routing** — Decide node classifies: RAG vs direct answer vs clarification
- **LangGraph agent** — explicit state machine with conditional edges
- **Circuit breaker** — resilient vector store calls with auto-recovery
- **Observability** — structured JSON logging, Prometheus metrics (`/metrics`)
- **Conversation memory** — SQLite-backed history for context across turns

## 🏗️ Architecture

```
START → Decide (LLM classifies intent)
  ├─ rag     → QueryRewrite → Retrieve → EvaluateRelevance
  │                ├─ sufficient=True  → PrepareRagGeneration → END
  │                └─ sufficient=False → NoAnswer → END
  ├─ direct  → PrepareDirectGeneration → END
  └─ clarify → PrepareClarifyGeneration → END

API layer: streams tokens from LLM.astream() for generation_prompt paths.
```

## 🚀 Setup

### Prerequisites

- **Python 3.11+**
- **Docker & Docker Compose** (for containerized run)
- **Ollama** (local LLM runtime)

### 1. Clone & Configure

```bash
git clone <repo-url>
cd agentic_rag

cp .env.example .env
# Edit .env — set OLLAMA_BASE_URL for your environment (see below)
```

### 2. Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_ENV` | Environment (dev/staging/prod) | `dev` |
| `APP_PORT` | API port | `8000` |
| `OLLAMA_BASE_URL` | Ollama API URL | `http://ollama:11434` (Docker) or `http://localhost:11434` (local) |
| `OLLAMA_MODEL` | Chat model name | `llama3` |
| `OLLAMA_EMBED_MODEL` | Embedding model | `nomic-embed-text` |
| `CHROMA_PERSISTENCE_PATH` | Local ChromaDB storage path | `./data/chroma_db` |
| `CHROMA_COLLECTION` | Collection name | `docs` |
| `TOP_K` | Number of docs to retrieve | `4` |
| `CHUNK_SIZE` | Chunk size for splitting | `512` |
| `ENABLE_MEMORY` | Use conversation memory | `true` |

### 3. Run with Docker Compose (recommended)

```bash
# Start API + Ollama
docker compose up -d --build

# Pull required models (first time only)
docker exec rag-ollama ollama pull llama3
docker exec rag-ollama ollama pull nomic-embed-text
```

### 4. Run Locally (Poetry)

```bash
poetry install
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Ensure Ollama is running locally (`ollama serve`) and set `OLLAMA_BASE_URL=http://localhost:11434` in `.env`.

---

## 📡 API Usage

### Ingest Documents (file upload)

Upload a document (PDF, TXT, MD, DOCX). The system loads, cleans, chunks, embeds, and upserts into the vector store.

```bash
curl -X POST http://localhost:8000/ingest \
  -F "file=@/path/to/your/document.pdf"
```

**Example with a text file:**

```bash
# Create a sample file
echo "The refund policy allows returns within 30 days of purchase. Items must be in original condition." > policy.txt

curl -X POST http://localhost:8000/ingest \
  -F "file=@policy.txt"
```

**Response:**

```json
{
  "doc_ids": ["doc-abc123", "doc-def456"],
  "chunks_created": 2,
  "status": "ok"
}
```

### Chat (SSE stream)

Stream an agent response. Use `-N` with curl to disable buffering and see tokens as they arrive.

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the refund policy?",
    "conversation_id": "my-session-123"
  }'
```

**SSE event types:**

| Event | Description |
|-------|-------------|
| `token` | Partial answer chunk (`{"type":"token","chunk":"..."}`) |
| `done` | Final metadata (`sources`, `latency_ms`, `token_count`, `retrieval_score`) |
| `error` | Error (`{"type":"error","code":"...","message":"..."}`) |

**Example stream output:**

```
data: {"type":"token","chunk":"The refund "}
data: {"type":"token","chunk":"policy allows "}
data: {"type":"token","chunk":"returns within 30 days..."}
data: {"type":"done","sources":[{"doc_id":"...","title":"policy.txt","snippet":"..."}],"latency_ms":1200,"token_count":15,"retrieval_score":0.85}
```

### Health & Readiness

```bash
# Liveness
curl http://localhost:8000/health

# Readiness (checks Ollama + ChromaDB)
curl http://localhost:8000/ready
```

### OpenAPI Docs

- Swagger UI: `http://localhost:8000/docs` (when `APP_ENV=dev`)
- ReDoc: `http://localhost:8000/redoc`

---

## 🧪 Testing

```bash
# Unit tests (no external services)
make test

# With coverage
make test-cov

# Integration tests (requires Docker)
make test-integration

# Lint & format
make lint
make format
```

---

## 📁 Project Structure

```
app/
├── main.py                 # FastAPI app factory
├── api/v1/                  # HTTP endpoints
│   ├── chat.py              # SSE streaming /chat
│   ├── ingest.py            # File upload /ingest
│   └── health.py            # /health, /ready
├── agent/
│   ├── graph.py             # LangGraph definition
│   ├── state.py             # AgentState TypedDict
│   ├── nodes/               # Graph nodes
│   │   ├── decide.py        # Intent classification
│   │   ├── query_rewrite.py # Query expansion
│   │   ├── retrieve.py      # Hybrid retrieval
│   │   ├── evaluate_relevance.py
│   │   ├── prepare_generation.py  # RAG/direct/clarify prompts
│   │   └── no_answer.py     # "I don't know" response
│   └── memory/              # Conversation history
├── llm/                     # LLM factory (Ollama)
├── embedding/                # Embedding factory
├── vectorstore/              # ChromaDB adapter (local)
├── ingest/                   # Document pipeline
└── core/                     # Config, metrics, circuit breaker
```

---

## ⚙️ Configuration

All settings are loaded from environment variables. See [`.env.example`](.env.example) for the full list.

---
