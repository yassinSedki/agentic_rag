# Design Note — Agentic RAG API

This document explains the main design decisions: **vector database choice**, **streaming method**, **graph states and flow**, and the **patterns** used throughout the project.

---

## 1. Vector Database: ChromaDB (Local / Embedded)

### Choice

**ChromaDB** was chosen as the vector store for this RAG service.

### Why ChromaDB?

- **Simplicity** — Minimal setup, no separate server process for development.
- **Python-native** — First-class Python client; integrates cleanly with LangChain.
- **Embedded mode** — `PersistentClient` stores vectors on disk in a single directory; no network dependency.
- **Metadata support** — Filtering by `source`, `page`, `tag` for retrieval.
- **Cosine similarity** — Default HNSW index with cosine similarity for semantic search.

### How It Is Used: Local, Not Server

This project uses **ChromaDB in embedded mode**, not as a separate HTTP server:

```
┌─────────────────────────────────────────────────────────┐
│  API Container / Process                                 │
│  ┌─────────────┐    ┌──────────────────────────────────┐ │
│  │ FastAPI     │───▶│ ChromaDB PersistentClient         │ │
│  │ + LangGraph │    │ path = ./data/chroma_db           │ │
│  └─────────────┘    │ (local, on-disk, in-process)      │ │
│                     └──────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Configuration:**

- `chroma_persistence_path`: `./data/chroma_db` (or `./data/chroma_db` in Docker)
- No `CHROMA_HOST` / `CHROMA_PORT` — the adapter uses `chromadb.PersistentClient(path=...)`, not `HttpClient`.

**Implications:**

- **Pros**: Single process, no network latency, easy local dev and Docker, data persists in a volume.
- **Cons**: No horizontal scaling of the vector store; one process owns the data. For multi-service scaling, you would switch to `chromadb.HttpClient` and run a Chroma server.

---

## 2. Streaming Method: Server-Sent Events (SSE)

### Choice

**Server-Sent Events (SSE)** via `text/event-stream` for streaming LLM responses.

### Why SSE?

- **One-way streaming** — Server pushes tokens to the client; no need for client→server streaming.
- **HTTP-based** — Works over standard HTTP; no WebSocket upgrade or protocol negotiation.
- **Simple client** — `curl -N`, `EventSource` in browsers, or any HTTP client that supports streaming.
- **Reconnection** — Built-in retry semantics (though we use a single long-lived stream per request).
- **Structured events** — Each event is a JSON object: `token`, `done`, or `error`.

### Implementation Pattern

1. **Graph prepares** — LangGraph runs routing + retrieval. Terminal nodes return `generation_prompt` (or `final_answer` for `no_answer`).
2. **API streams** — For `generation_prompt`, the API calls `llm.astream(prompt)` and forwards each chunk as an SSE `token` event.
3. **Done event** — After streaming completes, a final `done` event carries metadata: `sources`, `latency_ms`, `token_count`, `retrieval_score`.
4. **Disconnect handling** — The generator checks `await request.is_disconnected()` and cancels the producer task to avoid leaking work.

### Alternatives Considered

- **WebSocket** — More complex; not needed for one-way streaming.
- **Chunked transfer** — Less structured; SSE provides clear event boundaries.
- **Buffered response** — Rejected; spec requires incremental streaming.

---

## 3. Graph States and Design

### State Contract (`AgentState`)

The LangGraph state is a `TypedDict` shared by all nodes:

| Field | Purpose |
|-------|---------|
| `question` | Original user question |
| `conversation_id` | Session identifier |
| `request_id` | Request tracing |
| `history` | Previous turns (from memory or client) |
| `route` | Routing decision: `rag` \| `direct` \| `clarify` |
| `rewritten_query` | Query after rewrite (RAG path) |
| `retrieved_docs` | Documents from hybrid search |
| `retrieval_score` | Average relevance score |
| `retrieval_sufficient` | Whether docs are good enough |
| `generation_prompt` | Prompt for LLM streaming (RAG/direct/clarify) |
| `final_answer` | Precomputed answer (e.g. `no_answer`) |
| `source_ids` | Citation IDs |
| `error` | Error message if any |

### Graph Flow (Clarification-Oriented)

The graph is designed to **clarify intent** before answering:

```
                    ┌─────────────┐
                    │   START    │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Decide    │  LLM classifies: rag | direct | clarify
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
   ┌──────────┐     ┌──────────────┐     ┌──────────────┐
   │   rag    │     │   direct     │     │   clarify    │
   └────┬─────┘     └──────┬───────┘     └──────┬───────┘
        │                  │                     │
        ▼                  │                     │
   ┌─────────────┐         │                     │
   │QueryRewrite │         │                     │
   └──────┬──────┘         │                     │
          │                │                     │
          ▼                │                     │
   ┌─────────────┐         │                     │
   │  Retrieve   │         │                     │
   └──────┬──────┘         │                     │
          │                │                     │
          ▼                │                     │
   ┌─────────────────┐     │                     │
   │EvaluateRelevance│     │                     │
   └──────┬──────────┘     │                     │
          │                 │                     │
    ┌─────┴─────┐           │                     │
    │           │           │                     │
    ▼           ▼           │                     │
 sufficient  insufficient   │                     │
    │           │           │                     │
    ▼           ▼           │                     │
┌─────────┐ ┌─────────┐    │                     │
│Prepare  │ │NoAnswer │    │                     │
│RAG Gen  │ │         │    │                     │
└────┬────┘ └────┬────┘    │                     │
     │            │        │                     │
     │     ┌──────┴────────┴──────┐              │
     │     │                      │              │
     │     │  PrepareDirectGen    │ PrepareClarifyGen
     │     │                      │              │
     │     └──────────┬───────────┘              │
     │                │                          │
     └────────────────┼──────────────────────────┘
                      │
                      ▼
                    ┌─────┐
                    │ END │  → API streams LLM output or precomputed text
                    └─────┘
```

### Design Rationale for Clarification

1. **Decide node** — Avoids unnecessary retrieval for greetings or simple questions.
2. **Clarify route** — When the question is ambiguous, the agent asks for clarification instead of guessing.
3. **No-answer path** — When retrieval is empty or insufficient, the agent returns a structured "I don't know" with a hint to ingest relevant docs.
4. **Prepare nodes** — Graph nodes do not call the LLM for generation; they only build prompts. The API layer streams the LLM output, enabling real-time token delivery.

---

## 4. Patterns Used

### Adapter Pattern (Vector Store)

- **`VectorStoreAdapter`** — Abstract interface (`add_documents`, `similarity_search`, `get_by_id`, `delete`, `health_check`).
- **`ChromaAdapter`** — Concrete implementation using ChromaDB.
- **`VectorStore`** — Facade that selects the backend from config (`vector_db=chroma`).

### Factory Pattern (LLM, Embeddings)

- **`get_chat_llm()`** — Returns configured Ollama chat model.
- **`get_embedder()`** — Returns configured embedding model (Ollama).

### Circuit Breaker

- Wraps ChromaDB calls (`add_documents`, `similarity_search`, etc.).
- Opens after N failures; half-open for retry; prevents cascading failures.

### Producer–Consumer for Streaming

- **Producer task** — `_produce_llm_chunks` runs `llm.astream(prompt)` and pushes chunks into an `asyncio.Queue`.
- **Consumer** — The SSE generator reads from the queue, yields token events, and checks for client disconnect.

### 12-Factor Configuration

- All settings via environment variables.
- Pydantic `Settings` with `.env` support.
- No hardcoded secrets or endpoints.

---

## 5. Summary

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Vector DB** | ChromaDB (embedded) | Local, simple, no server; Python-native |
| **Storage mode** | Local `PersistentClient` | Single process, disk persistence, no network |
| **Streaming** | SSE (`text/event-stream`) | One-way, HTTP-based, simple clients |
| **Graph** | LangGraph with conditional edges | Explicit routing, intent clarification, testable |
| **Generation** | API streams `llm.astream()` | Real token-by-token streaming; graph prepares prompts |
