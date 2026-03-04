## Docker & Docker Compose in This Project

This document explains **how Docker and Docker Compose work in this repo**, and **why they are needed** for a real RAG system (API + LLM + vector DB).

---

## 1. What Docker Is (Conceptually)

- **Docker** runs your application inside a **container**, which is like a lightweight, isolated mini‑Linux system.
- A container has:
  - Its **own filesystem** (libraries, Python, your code).
  - Its **own network view** (ports, hostnames for other containers).
  - Its **own environment variables**.
- A **Docker image** is a **frozen template** that defines what goes into the container (OS + Python + dependencies + code).
- The **`Dockerfile`** describes how to build that image.

In this project, the goal is:

- Build a **reproducible image** for the FastAPI RAG API.
- Run it in a predictable environment, on any machine with Docker.

---

## 2. Your `Dockerfile` – How the API Image Is Built

Path: `Dockerfile`

This project uses a **multi‑stage build** with two stages:

### Stage 1 – `builder`

```text
FROM python:3.11-slim AS builder
WORKDIR /build
```

- Uses a slim Python 3.11 image.
- Works in `/build` directory.

**Installs build tools and Poetry:**

- Runs `apt-get` to install `build-essential` and `curl`.
- Installs Poetry (`POETRY_VERSION=1.8.3`) via the official installer.
- Adds `poetry` to the `PATH` so it can be used globally.

**Installs Python dependencies:**

- Copies `pyproject.toml` and `poetry.lock` into the image.
- Runs:
  - `poetry config virtualenvs.create false` (no virtualenv inside the container).
  - `poetry install --without dev` (only production deps, no dev tools).

Result: the **builder image** now has all Python packages installed globally.

### Stage 2 – `runtime`

```text
FROM python:3.11-slim AS runtime
WORKDIR /app
```

- Starts fresh from a clean Python 3.11 slim image (smaller, no compilers).
- Creates a **non‑root user** (`appuser`) and group (`appgroup`) for better security.

**Copies installed dependencies and code:**

- Copies the installed site‑packages from the builder image into this runtime image:
  - `COPY --from=builder /usr/local/lib/python3.11/site-packages ...`
- Copies binaries from builder (`/usr/local/bin`) — so tools like `uvicorn` are available.
- Copies your application code:
  - `COPY app/ ./app/`
- Sets ownership of `/app` to the non‑root user and switches to `USER appuser`.

**Networking, health, and entrypoint:**

- `EXPOSE 8000` tells Docker that the app will listen on port 8000.
- `HEALTHCHECK`:
  - Periodically runs a Python command that uses `httpx` to call `http://localhost:8000/health`.
  - If it fails, Docker marks the container as unhealthy.
- `CMD [...]`:
  - Starts the API with:
    - `uvicorn app.main:app --host 0.0.0.0 --port 8000`

In other words, the Dockerfile defines an image that:

- Has Python 3.11 + all dependencies.
- Runs your FastAPI app on port 8000.
- Supports health checks and uses a non‑root user.

---

## 3. What Docker Compose Is (Conceptually)

**Docker** runs a single container, but a real RAG system needs **multiple services**:

- The **API** (FastAPI / LangGraph).
- The **LLM server** (Ollama).
- The **vector store** (ChromaDB).

**Docker Compose** is a tool that lets you:

- Define multiple services in a single YAML file.
- Describe how they connect, which ports to expose, which volumes to use.
- Start/stop the entire stack with **one command**.

In this repo, that file is `docker-compose.yml` (for normal use) and `docker-compose.test.yml` (for integration tests).

---

## 4. `docker-compose.yml` – Your Production/Dev Stack

Path: `docker-compose.yml`

High‑level idea:

- **Service `api`**: your RAG API (built from the Dockerfile).
- **Service `ollama`**: LLM model server.
- **Service `chroma`**: ChromaDB vector store.
- Shared **volumes** for persistent data.
- Shared **network** so they can talk to each other.

### 4.1 `api` service (RAG API)

Key parts:

```yaml
api:
  build: .
  container_name: rag-api
  ports:
    - "8000:8000"
  env_file:
    - .env
  depends_on:
    ollama:
      condition: service_healthy
    chroma:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "python", "-c", "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"]
    interval: 30s
    timeout: 5s
    retries: 3
    start_period: 15s
  networks:
    - rag_net
  restart: unless-stopped
```

- **`build: .`**:
  - Uses the `Dockerfile` in the repo root to build the API image.
- **`ports: "8000:8000"`**:
  - Maps container port 8000 → host port 8000, so you can call:
    - `http://localhost:8000/...`
- **`env_file: .env`**:
  - Loads environment variables from your `.env` file into the container.
  - This is where API keys, model URLs, etc. are configured.
- **`depends_on` with `condition: service_healthy`**:
  - The API waits for `ollama` and `chroma` to be healthy before being considered “up”.
  - This uses health checks defined in those services.
- **`healthcheck`**:
  - Similar to the one inside the Dockerfile, but defined at the Compose level.
  - Periodically calls the `/health` endpoint of the API.
- **`networks: rag_net`**:
  - Allows API to reach `ollama` and `chroma` by their service names.
- **`restart: unless-stopped`**:
  - If the container crashes, Docker will restart it.

### 4.2 `ollama` service (LLM runtime)

Key parts:

```yaml
ollama:
  image: ollama/ollama:latest
  container_name: rag-ollama
  ports:
    - "11434:11434"
  volumes:
    - ollama_models:/root/.ollama
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:11434/api/version"]
    interval: 15s
    timeout: 5s
    retries: 5
    start_period: 30s
  networks:
    - rag_net
  restart: unless-stopped
```

- Runs the official `ollama/ollama` image.
- Exposes port **11434** to the host:
  - The API can talk to `http://ollama:11434` from inside the network.
  - You can access Ollama from your host on `http://localhost:11434`.
- Uses a **volume** `ollama_models` to persist downloaded models.
- Has its own healthcheck (calls the `/api/version` endpoint).

### 4.3 `chroma` service (vector store)

Key parts:

```yaml
chroma:
  image: chromadb/chroma:latest
  container_name: rag-chroma
  ports:
    - "8001:8000"
  volumes:
    - chroma_data:/chroma/chroma
  environment:
    - IS_PERSISTENT=TRUE
    - ANONYMIZED_TELEMETRY=FALSE
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/heartbeat"]
    interval: 15s
    timeout: 5s
    retries: 5
    start_period: 10s
  networks:
    - rag_net
  restart: unless-stopped
```

- Runs ChromaDB in a container.
- Inside the Docker network, Chroma listens on port 8000.
- Mapped to host port 8001 (so `localhost:8001` → `chroma:8000`).
- Uses a **persistent volume** `chroma_data` so embeddings survive restarts.
- `IS_PERSISTENT=TRUE` ensures Chroma persists state.
- Has a healthcheck (`/api/v1/heartbeat`) to signal readiness.

### 4.4 Volumes and networks

```yaml
volumes:
  ollama_models:
    driver: local
  chroma_data:
    driver: local

networks:
  rag_net:
    driver: bridge
```

- **Volumes**:
  - `ollama_models`: stores Ollama model data on the host disk.
  - `chroma_data`: stores ChromaDB index data.
- **Network `rag_net`**:
  - Connects `api`, `ollama`, and `chroma`.
  - Containers can reach each other via DNS names: `http://ollama:11434`, `http://chroma:8000`, etc.

---

## 5. `docker-compose.test.yml` – Integration Test Stack

Path: `docker-compose.test.yml`

This file defines a **separate stack** for integration tests, so tests don’t touch your main dev/prod data.

Key services:

- `api-test`:
  - Builds from the same Dockerfile.
  - Exposes port `8100:8000`.
  - Sets environment variables like:
    - `APP_ENV=dev`
    - `OLLAMA_BASE_URL=http://ollama-test:11434`
    - `CHROMA_HOST=chroma-test`, `CHROMA_PORT=8000`
    - `CHROMA_COLLECTION=test_docs`
  - Depends on `chroma-test` health.
- `chroma-test`:
  - ChromaDB, but **non‑persistent** (`IS_PERSISTENT=FALSE`).
  - No volume defined, data is ephemeral.
- `ollama-test`:
  - Optional Ollama instance for tests.

This is used by:

```bash
make test-integration
```

Which:

1. Brings up this test stack.
2. Runs pytest integration tests.
3. Brings the stack down and discards data.

---

## 6. How It All Works Together (Lifecycle)

### 6.1 Starting the system

From the project root:

```bash
docker compose up -d --build
```

What happens:

1. **Build phase**:
   - Docker reads `docker-compose.yml`.
   - For the `api` service, it builds the image using the `Dockerfile`.
2. **Run phase**:
   - Starts containers for:
     - `ollama`
     - `chroma`
     - `api`
   - Applies health checks and `depends_on` conditions:
     - `ollama` and `chroma` start first and become healthy.
     - `api` is marked healthy only when `/health` responds OK.
3. **Networking**:
   - All containers join the `rag_net` network.
   - API resolves `ollama` and `chroma` by service names.
4. **Persistence**:
   - Volumes store model files and vector store data between restarts.

### 6.2 Stopping the system

```bash
docker compose down
```

- Stops all containers in the stack.
- Keeps the **named volumes** (unless you pass `-v` to delete them), so data persists.

### 6.3 Day‑to‑day commands

- **Start stack**:
  ```bash
  docker compose up -d --build
  # or
  make compose-up
  ```

- **Stop stack**:
  ```bash
  docker compose down
  # or
  make compose-down
  ```

- **See logs**:
  ```bash
  docker compose logs -f api
  docker compose logs -f ollama
  docker compose logs -f chroma
  ```

- **Exec into a container**:
  ```bash
  docker exec -it rag-api /bin/bash
  docker exec -it rag-ollama /bin/bash
  docker exec -it rag-chroma /bin/bash
  ```

---

## 7. Why Docker & Docker Compose Are Needed Here

For this RAG project, Docker/Compose bring several **practical benefits**:

- **Multi‑service orchestration**
  - You need **three** components working together:
    - FastAPI RAG API
    - LLM server (Ollama)
    - Vector DB (Chroma)
  - Docker Compose lets you define and run them as **one stack**.

- **Consistent environments**
  - Everyone runs the **same Python version**, same OS libraries, same dependencies.
  - Avoids “it works on my machine” issues.

- **Easy onboarding**
  - New developer or new machine:
    - Install Docker.
    - `docker compose up -d --build`.
    - Immediately have a full RAG backend running.

- **Deployment ready**
  - The same images from development can be used in staging/production.
  - Fits well with CI/CD pipelines (build image, push, deploy).

- **Isolation and security**
  - Python dependencies and system libs are isolated from your host.
  - The app runs as a non‑root user inside the container.

Without Docker/Compose, you would have to:

- Install and configure Python + dependencies manually.
- Install and run Ollama.
- Install and run ChromaDB (with correct versions, ports, and config).
- Wire all three components together with consistent env vars and hostnames.

Docker and Docker Compose **automate and standardize** all of this.

---

## 8. TL;DR – How You Use It

- **For normal dev / usage:**
  1. Configure `.env`.
  2. Run `docker compose up -d --build` (or `make compose-up`).
  3. Ingest docs via `/ingest`, ask questions via `/chat`.
  4. Stop with `docker compose down` (or `make compose-down`).

- **For integration tests:**
  1. Run `make test-integration` (uses `docker-compose.test.yml`).
  2. It brings up a separate test stack, runs tests, then tears it down.

Docker = **how to package and run** the API.  
Docker Compose = **how to run the API + LLM + vector DB together** as a complete RAG system.

