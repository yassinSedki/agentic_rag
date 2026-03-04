# 🤖 Agentic RAG API

> Production-grade Retrieval-Augmented Generation API built with **FastAPI**, **LangGraph**, **Ollama**, and **ChromaDB**.

## ✨ Features

- **Streaming SSE responses** — real-time token-by-token answers
- **Hybrid retrieval** — dense vector search + BM25 with RRF fusion
- **Grounded answers** — post-synthesis grounding check prevents hallucination
- **LangGraph agent** — explicit, testable state machine with 11 nodes
- **Circuit breaker** — resilient external service calls with auto-recovery
- **Observability** — structured JSON logging, Prometheus metrics
- **Security** — API key auth, rate limiting, PII redaction, prompt injection sanitizer

## 🏗️ Architecture

```
START → Decide
  ├─ rag     → Rewrite → Retrieve → Evaluate → Synthesize → GroundingCheck → Validate → Stream
  ├─ direct  → DirectAnswer → Stream
  └─ clarify → Clarify → Stream
Stream → END
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Ollama (for local LLM inference)

### 1. Clone & Configure

```bash
cp .env.example .env
# Edit .env — at minimum change API_KEY
```

### 2. Start Services

```bash
# With Docker Compose (recommended)
docker compose up -d --build

# Or run locally with Poetry
poetry install
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Pull Ollama Models

```bash
docker exec rag-ollama ollama pull llama3
docker exec rag-ollama ollama pull nomic-embed-text
```

## 📡 API Usage

### Ingest Documents

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: changeme-to-a-secure-value" \
  -d '{
    "text": "The refund policy allows returns within 30 days...",
    "filename": "policy.txt",
    "metadata": {"tag": "policy"}
  }'
```

### Chat (SSE Stream)

```bash
curl -N http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: changeme-to-a-secure-value" \
  -d '{"question": "What is the refund policy?"}'
```

### Health Check

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

## 🧪 Testing

```bash
# Unit tests (no external services needed)
make test

# With coverage
make test-cov

# Integration tests (requires Docker)
make test-integration
```

## 📁 Project Structure

```
app/
├── main.py              # FastAPI app factory
├── api/v1/              # HTTP endpoints (chat, ingest, health)
├── agent/               # LangGraph state machine
│   ├── state.py         # AgentState TypedDict
│   ├── graph.py         # Graph wiring + routers
│   ├── nodes/           # 11 pure reasoning nodes
│   └── tools/           # Side-effect tools
├── llm/                 # LLM factory + Ollama provider
├── embedding/           # Embedding factory + provider
├── vectorstore/         # Abstract adapter + ChromaDB + reranker
├── ingest/              # Document processing pipeline
└── core/                # Config, logging, metrics, security
```

## ⚙️ Configuration

All settings are configured via environment variables. See [`.env.example`](.env.example) for the full list.

## 📝 Known Limitations

- **Memory integration** is stubbed out (planned for a future phase).
- BM25 keyword search runs in-process on dense search candidates (not a separate index).
- Single Ollama model at a time (no multi-model routing yet).

## 📄 License

MIT
