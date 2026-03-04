# Docker and Docker Compose: Overview and Lifecycle Logic

## 1. What is Docker?
Docker is a platform that packages applications and their dependencies into standardized units called **containers**. A container encapsulates everything needed for an application to run smoothly—including the code, runtime, system tools, system libraries, and settings. This ensures the application runs consistently, regardless of what environment or Operating System it is deployed on.

## 2. What is Docker Compose?
While Docker normally manages individual containers one by one, **Docker Compose** is a tool specifically designed for defining and running multi-container applications. By using a single declarative configuration file (`docker-compose.yml`), you define your application's microservices, networks, and persistent storage volumes. You can then trigger the entire stack to build and run using a single command: `docker-compose up`.

## 3. How your `docker-compose.yml` Works
In your Retrieval-Augmented Generation (RAG) project, you define three main microservices that must work together:
- **`api`**: Your custom Python RAG REST API.
- **`ollama`**: The local Large Language Model (LLM) serving engine.
- **`chroma`**: The ChromaDB vector database serving your document embeddings.

### Key Concepts in your Configuration:
- **Build vs. Image**: 
  - The `api` service uses `build: .`, which tells Docker to look at your local `Dockerfile` and compile a brand-new custom image containing your Python code.
  - The `ollama` and `chroma` services use pre-built images fetched directly from Docker Hub (`image: ollama/ollama:latest` and `chromadb/chroma:latest`).
- **Ports Mapping**: Directives like `8000:8000` map a port on your physical host machine to a port inside the isolated container. This is why you can navigate to `http://localhost:8000` on your Windows browser and successfully reach the Python API inside Docker.
- **Volumes**: Containers are ephemeral (temporary). If you delete a container, its data vanishes. **Volumes** (`ollama_models`, `chroma_data`) create persistent storage tunnels to your host machine. This means your downloaded heavy AI models and embedded Chroma vectors are strictly saved and won't be lost across container restarts.
- **Networks**: The `rag_net` bridge network acts as an isolated virtual router. The containers use this to communicate with each other securely using their service names instead of IP addresses. For example, your `api` container connects to ChromaDB by resolving the hostname `http://chroma:8000`.

## 4. The Container Lifecycle (Life Logic)
A container's lifecycle represents its journey from starting up to shutting down or recovering from failures. Your setup employs advanced lifecycle management features:

### Startup Order and Dependencies (`depends_on`)
Docker Compose does not just violently boot all services at exactly the same time. In your `api` block, you enforce strict dependency logic:
```yaml
depends_on:
  ollama:
    condition: service_healthy
  chroma:
    condition: service_healthy
```
**Logic:** The custom `api` container will be held back and forced to **wait** until both `ollama` and `chroma` fully start, initialize themselves, and pass their respective health checks. This guarantees your Python API doesn't crash on boot trying to connect to a database that isn't ready yet.

### Healthchecks
A container being "running" doesn't necessarily mean the application inside it isn't frozen. **Healthchecks** continuously poll the application to verify true health:
- **Chroma** runs `curl` against its `/heartbeat` API.
- **Ollama** runs `curl` against its `/api/version`.
- **API** runs a Python `httpx` script against its `/health` route.

**Logic:** Docker repeats these tests based on your defined `interval` (e.g., every 30s). If the service fails `retries` times in a row, it gets flagged as `unhealthy`. Health checks feed directly into the `depends_on` startup order mentioned above.

### Restart Policies (`restart: unless-stopped`)
This defines the recovery logic. If a service fatally crashes due to an out-of-memory error, a bug, or an unexpected OS reboot, Docker's daemon will automatically step in and **restart the container**. The "unless-stopped" condition means it will always fight to keep the service online, *except* if you intentionally paused it via the `docker compose stop` command.

## 5. Why is this needed? (The Benefits)
1. **Consistency ("It works on my machine")**: Setting up an AI stack manually is incredibly difficult. One developer might have Python 3.9, another Python 3.11. One might fail to install ChromaDB C++ bindings properly. Docker guarantees that the environment executing the API is 100% identical for every developer, staging server, and production server.
2. **One-Command Boot**: Instead of writing a convoluted 20-step README instructing a new developer to start Chroma in terminal A, Ollama in terminal B, and the API in terminal C—they just execute `docker compose up -d`. The infrastructure boots itself.
3. **App Isolation**: Your project dependencies won't conflict with other tasks on your Windows machine. Your system stays clean.
4. **Resilience**: The automated restart policies and strict health check dependency chains transform fragile distinct components into a single, self-healing, predictable system.
