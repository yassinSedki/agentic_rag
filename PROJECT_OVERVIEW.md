## Agentic RAG – High‑Level Overview

This project is a **production‑grade Retrieval‑Augmented Generation (RAG) API** built with **FastAPI**, **LangGraph**, **Ollama**, and **ChromaDB**.  
You send it documents, it indexes them, and then an LLM answers questions **grounded in those documents** instead of hallucinating.

- **API layer (`app/api/v1`)**: HTTP endpoints for `/chat`, `/ingest`, `/health`.
- **Agent layer (`app/agent`)**: a LangGraph **state machine** (multiple nodes) that decides how to handle each request.
- **LLM & embeddings (`app/llm`, `app/embedding`)**: wrappers around Ollama (or another LLM backend).
- **Vector store (`app/vectorstore`)**: Chroma adapter + reranker that performs semantic / hybrid search.
- **Ingest pipeline (`app/ingest`)**: loads, cleans, chunks, embeds, and stores your documents.
- **Core utilities (`app/core`)**: configuration, logging, metrics, security, circuit breaker, exceptions.

The result: a **robust RAG backend** you can run locally (or in Docker) and call from any frontend.

---

## How the RAG Pipeline Works (Conceptual)

At a high level, answering a question goes through these stages:

1. **User question arrives**
   - You call the `/chat` endpoint with a JSON body that includes the question (and optionally a conversation id, metadata, etc.).

2. **Routing / intent classification**
   - The `decide` node in `app/agent/nodes/decide.py` uses an LLM to classify the request:
     - **`rag`**: use retrieval + your documents.
     - **`direct`**: answer directly without retrieval.
     - **`clarify`**: ask the user for more information.

3. **Query rewrite (for RAG route)**
   - If the route is `rag`, the `query_rewrite` node rewrites the question to be clearer and more retrieval‑friendly.

4. **Retrieve documents**
   - The `retrieve` node calls the vector store (`app/vectorstore`) to:
     - Convert the query into an embedding.
     - Search in Chroma for the most similar chunks.
     - Optionally combine dense search with BM25 and rerank (hybrid retrieval).

5. **Evaluate retrieval quality**
   - The `evaluate_relevance` node checks if the retrieved documents look relevant enough:
     - If **good enough** → continue.
     - If **not sufficient** → go to a `no_answer` path (tell the user we don’t know / suggest ingestion).

6. **Synthesize an answer**
   - The `synthesize` node sends the **question + history + retrieved chunks** to the LLM.
   - The LLM generates an answer **token by token**, which is then streamed back to the client (SSE).

7. **Grounding check (hallucination guard)**
   - The `grounding_check` node compares the **draft answer** against the retrieved documents.
   - If the answer claims things **not supported** by the docs, it can:
     - Mark `grounding_ok = False` and route to `no_answer`.
     - Or adjust/flag the response.

8. **Validation & streaming**
   - `validate_output` parses and validates the answer into a structured schema.
   - `stream_answer` sends the final structured chunks to the HTTP response as a stream.

All of this is orchestrated by `app/agent/graph.py`, which wires the nodes together using LangGraph.

---

## How to Make the RAG Actually Work (Step‑by‑Step)

You need **two flows** to be working:

1. **Ingest flow** – put your data into the vector database.
2. **Chat flow** – ask questions that use that data.

### 1. Start the Backend

The easiest way is via Docker Compose (see below for the “why”):

```bash
cp .env.example .env
# Edit .env to set API keys, model names, ports, etc.

docker compose up -d --build
```

This should start:

- The **FastAPI** app (the RAG API).
- **ChromaDB** (vector store) and any other backing services (e.g. Ollama container) defined in `docker-compose.yml`.

If you prefer running locally without Docker, you can instead:

```bash
poetry install
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

> Make sure any required external services (Ollama, Chroma, etc.) are also running and configured to match your `.env`.

### 2. Ingest Your Documents

Call the `/ingest` endpoint with some text or documents. A simple example using `curl`:

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your-api-key-from-.env>" \
  -d '{
    "text": "The refund policy allows returns within 30 days.",
    "filename": "policy.txt",
    "metadata": {"tag": "policy"}
  }'
```

Behind the scenes, the ingest pipeline:

1. Loads the content (`load_document`).
2. Cleans and normalizes the text (`clean`).
3. Splits it into chunks with metadata (`chunk_with_metadata`).
4. Creates embeddings for each chunk (`embedding_factory`).
5. Stores them in Chroma (`vectorstore/chroma.py`).

Once this is done, the vector store is ready to serve RAG queries against your data.

### 3. Ask Questions (Chat)

Now use the `/chat` endpoint:

```bash
curl -N http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your-api-key-from-.env>" \
  -d '{"question": "What is the refund policy?"}'
```

The server will:

- Run the LangGraph agent (decide → retrieve → synthesize → ground → validate).
- Stream back tokens/chunks as they are generated (via SSE).

If your ingestion worked and your question matches the ingested content, the answer should quote/align with your policy data rather than making things up.

---

## Why Use Docker for This Project?

You **don’t have to** use Docker, but it solves several practical problems:

- **Reproducible environment**
  - Everyone gets the same Python version, OS libraries, and system packages.
  - No “works on my machine” issues from local differences.

- **Service orchestration**
  - RAG usually needs **multiple services**:
    - The FastAPI app.
    - A vector database (ChromaDB).
    - An LLM backend (Ollama or similar).
  - Docker Compose lets you start them all with **one command** and wires their networks/ports together.

- **Deployment ready**
  - The same images used in development can be pushed to a server or cloud provider.
  - Easier to scale or run behind a reverse proxy / load balancer.

- **Isolation**
  - Dependencies (Python libs, system libs) are contained in the image.
  - They don’t pollute your host machine Python or system packages.

For a multi‑component system like this (API + vector store + LLM), Docker is the most convenient way to run everything consistently.

---

## Purpose of the `Dockerfile`

The `Dockerfile` describes **how to build a container image** for the FastAPI RAG application.

Typical responsibilities:

- **Base image**: choose a Python base (e.g. `python:3.11-slim`).
- **Install dependencies**: copy `pyproject.toml` / `requirements.txt` and install packages.
- **Copy application code**: add `app/`, `tests/`, etc. into the image.
- **Configure environment**: set workdir, environment variables, non‑root user, etc.
- **Expose ports**: e.g. expose port `8000` for the FastAPI server.
- **Define the run command**: usually something like:
  - `uvicorn app.main:app --host 0.0.0.0 --port 8000`

In short, the `Dockerfile` turns your source code into a **runnable container image** that contains everything it needs (code + dependencies + runtime).

---

## Purpose of `docker-compose.yml`

`docker-compose.yml` defines **how multiple containers work together** as a single application stack.

Typical elements in this project:

- **Service for the RAG API**
  - Builds from the `Dockerfile`.
  - Mounts configuration / environment.
  - Exposes HTTP port to your host (e.g. `localhost:8000`).

- **Service for the vector store (ChromaDB)**
  - Runs the database engine.
  - Persists data in a Docker volume.
  - Connected to the API service over an internal Docker network.

- **Service for Ollama (LLM backend)**
  - Runs the model server.
  - API service calls it over the internal network.

- **Shared configuration**
  - Environment variables (via `.env`).
  - Volumes for data persistence.
  - Network definitions.

With `docker-compose.yml` you can:

- Start everything: `docker compose up -d --build`
- Stop everything: `docker compose down`
- Run integration tests or dev stacks that mirror production in a single command.

So:

- **`Dockerfile`** → how to build **one** container image (the app).
- **`docker-compose.yml`** → how to run **multiple containers together** (app + vector DB + LLM, etc.).

---

## If You Just Want to Use It

1. **Set up config**
   - Copy `.env.example` to `.env` and set your values.
2. **Start the stack**
   - `docker compose up -d --build`
3. **Ingest your data**
   - Call `/ingest` with your documents.
4. **Ask questions**
   - Call `/chat` with your question.

That’s all you need to get a working RAG assistant over your own documents.

