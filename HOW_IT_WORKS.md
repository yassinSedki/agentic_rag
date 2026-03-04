# 🚀 Step-by-Step: How the Agentic RAG System Works

> This guide walks you through every phase of the system — from setup to a live chat response.

---

## Step 1: Environment Setup

```bash
# 1. Clone and enter the project
cd agentic_rag

# 2. Copy environment config
cp .env.example .env
# Edit .env → set your API_KEY to something secure

# 3. Install dependencies with Poetry
poetry install

# 4. Start external services
docker compose up -d

# 5. Pull Ollama models (first time only)
docker exec rag-ollama ollama pull llama3
docker exec rag-ollama ollama pull nomic-embed-text

# 6. Start the API
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**What starts:**

| Service | Port | Purpose |
|---------|------|---------|
| FastAPI (api) | 8000 | Your RAG API |
| Ollama | 11434 | Local LLM inference |
| ChromaDB | 8001 | Vector store for embeddings |

---

## Step 2: Ingest Documents → Build Knowledge Base

Before the system can answer questions, you **feed it documents**.

```bash
# Ingest raw text
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{
    "text": "Employees may return items within 30 days for a full refund...",
    "filename": "refund_policy.txt",
    "metadata": {"tag": "policy"}
  }'
```

**What happens internally:**

```
POST /ingest
  │
  ▼
┌──────────────────────────────────────────────────┐
│  1. LOAD     → load_document.py                  │
│     Parse input (PDF/DOCX/TXT/MD or raw text)    │
│     → list[Document]                             │
│                                                  │
│  2. CLEAN    → clean.py                          │
│     Normalize whitespace, strip boilerplate      │
│     Drop empty pages                             │
│     → list[Document]                             │
│                                                  │
│  3. CHUNK    → chunk_with_metadata.py            │
│     RecursiveCharacterTextSplitter               │
│     chunk_size=512, overlap=64                   │
│     Assign SHA-256 chunk_id for dedup            │
│     → list[Chunk]                                │
│                                                  │
│  4. EMBED    → embedding_factory.py → Ollama     │
│     nomic-embed-text model                       │
│     texts → vectors (float arrays)               │
│     → list[list[float]]                          │
│                                                  │
│  5. UPSERT   → batch.py → ChromaAdapter          │
│     Deduplicate by chunk_id                      │
│     Batch insert into ChromaDB                   │
│     → list[chunk_ids]                            │
└──────────────────────────────────────────────────┘
  │
  ▼
Response: {"doc_ids": [...], "chunks_created": 12, "status": "ok"}
```

---

## Step 3: Ask a Question → Chat Endpoint (SSE Stream)

```bash
curl -N http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{"question": "What is the refund policy?"}'
```

This triggers the **LangGraph agent** — an 11-node state machine. Here's exactly what happens:

---

### 3.1 — Decide (Route Classification)

```
Input:  question = "What is the refund policy?"
LLM:    Classify → "rag" / "direct" / "clarify"
Output: route = "rag"
```

The LLM reads the question and decides:
- **rag** → needs document retrieval (most common)
- **direct** → simple question, answer without docs (e.g. "What is 2+2?")
- **clarify** → question is too vague, ask the user for details

---

### 3.2 — Query Rewrite

```
Input:  "What is the refund policy?"
LLM:    Rewrite for better search precision
Output: "company refund return policy conditions timeline"
```

Adds keywords, resolves pronouns from history, makes the query search-friendly.

---

### 3.3 — Hybrid Retrieve

```
Input:   rewritten_query
Step 1:  Embed query → vector via Ollama (nomic-embed-text)
Step 2:  Dense search → ChromaDB top-8 by cosine similarity
Step 3:  BM25 keyword search → rank-bm25 on the same candidates
Step 4:  RRF fusion → merge both rankings → top-4 documents
Output:  retrieved_docs = [doc1, doc2, doc3, doc4]
```

**Why hybrid?** Dense search finds semantically similar text. BM25 catches exact keyword matches. RRF combines both for better recall.

---

### 3.4 — Evaluate Relevance

```
Input:  retrieved_docs
Check:  Are there enough docs? Are scores above threshold?
Output: retrieval_sufficient = True/False
        retrieval_score = 0.85
```

- **True** → continue to synthesis
- **False** → jump to NoAnswer ("I don't know, try ingesting documents on this topic")

---

### 3.5 — Synthesize (LLM Generation)

```
Input:  rewritten_query + retrieved_docs + conversation history
Prompt: "Answer ONLY from these documents. Cite source IDs."
LLM:    Generates a grounded answer
Output: raw_answer = "The refund policy allows returns within 30 days..."
        source_ids = ["doc-001", "doc-002"]
```

The context is capped at `MAX_CONTEXT_CHARS=12000` to prevent overflow.

---

### 3.6 — Grounding Check (Post-Synthesis Verification)

```
Input:  raw_answer + retrieved_docs
Prompt: "Is every claim in this answer supported by the documents?"
LLM:    Verdict → "GROUNDED" or "NOT_GROUNDED"
Output: grounding_ok = True/False
```

- **True** → the answer is factually supported → continue
- **False** → hallucination detected → jump to NoAnswer

> **Key design decision:** Grounding happens AFTER synthesis, not before. This lets us verify the actual generated answer rather than pre-checking docs.

---

### 3.7 — Validate Output

```
Input:  raw_answer
Check:  Parse through Pydantic schema (ValidatedAnswer)
Output: final_answer = "The refund policy..." (if valid)
        error = None (or error message if parse fails)
```

---

### 3.8 — Stream Answer (SSE to Client)

The final answer is chunked into ~50-char pieces and streamed as **Server-Sent Events**:

```
data: {"type":"token","chunk":"The refund policy"}

data: {"type":"token","chunk":" allows returns within 30 days"}

data: {"type":"token","chunk":" of purchase."}

data: {"type":"done","sources":[{"doc_id":"doc-001"}],"latency_ms":843,"retrieval_score":0.85}
```

The client receives tokens in real-time, just like ChatGPT.

---

## Complete Flow Diagram

```
User Question
     │
     ▼
  ┌─DECIDE─┐
  │  LLM   │
  └──┬─┬─┬─┘
     │ │ │
     │ │ └── clarify ──→ CLARIFY ──→ STREAM → Client
     │ │
     │ └── direct ──→ DIRECT_ANSWER ──→ STREAM → Client
     │
     └── rag
          │
          ▼
    QUERY_REWRITE
          │
          ▼
   HYBRID_RETRIEVE  (Dense + BM25 → RRF)
          │
          ▼
  EVALUATE_RELEVANCE
      │          │
   sufficient  insufficient
      │          │
      ▼          └──→ NO_ANSWER ──→ STREAM → Client
  SYNTHESIZE
      │
      ▼
  GROUNDING_CHECK
      │          │
   grounded   not grounded
      │          │
      ▼          └──→ NO_ANSWER ──→ STREAM → Client
  VALIDATE_OUTPUT
      │          │
    valid     invalid
      │          │
      ▼          └──→ NO_ANSWER ──→ STREAM → Client
    STREAM
      │
      ▼
   Client (SSE events)
```

---

## Step 4: Health & Monitoring

```bash
# Liveness (is the process alive?)
curl http://localhost:8000/health
# → {"status": "ok"}

# Readiness (are Ollama + ChromaDB reachable?)
curl http://localhost:8000/ready
# → {"status": "ok", "ollama": "up", "vectordb": "up"}

# Prometheus metrics
curl http://localhost:8000/metrics
# → rag_requests_total, rag_llm_latency_seconds, etc.
```

---

## Step 5: Security Layers

Every request passes through these layers:

```
Request → API Key Check → Rate Limiter → Pydantic Validation
    → Request ID Injection → Agent Execution
    → Prompt Sanitizer (strips injection patterns)
    → PII Redactor (emails, phones → [REDACTED])
    → LLM Call → Output Validation → Response
```

---

## Step 6: Running Tests

```bash
# Unit tests (no Docker needed)
make test

# With coverage report
make test-cov

# Integration tests (starts test containers)
make test-integration
```

---

## Key Architecture Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| **LLM Runtime** | Ollama | 100% local, zero cloud cost, OpenAI-compatible |
| **Vector DB** | ChromaDB | Minimal setup, swappable via adapter pattern |
| **Streaming** | SSE (not WebSocket) | Simpler, auto-reconnect, HTTP/1.1 native |
| **Agent Framework** | LangGraph | Explicit state machine, node-by-node testable |
| **Grounding** | Post-synthesis | Verify the actual answer, not just the docs |
| **Memory** | Deferred | Stubbed out, feature-flagged for later |
