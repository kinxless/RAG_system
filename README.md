# Production-Ready Multi-Client RAG System

A scalable Retrieval-Augmented Generation (RAG) backend designed for private business knowledge systems.

Built with FastAPI, ChromaDB, MySQL, and Neo4j.

---

# Overview

This project implements a production-ready RAG infrastructure capable of handling:

- Multi-client knowledge bases
- Structured database ingestion
- Graph-based retrieval
- Cloud document ingestion
- Persistent vector storage
- Streaming responses

Designed for real-world deployment in enterprise and private AI systems.

---

# Core Features

## Multi-Client Architecture

Each client operates in isolated collections and data environments.

Supports:

- Separate document stores
- Separate vector collections
- Configurable ingestion pipelines

---

## Vector Retrieval (ChromaDB)

- Persistent vector storage
- Dynamic collection handling
- Metadata-aware retrieval
- Optimized embedding pipeline

---

## MySQL Data Sync

Supports live ingestion from relational databases.

Includes:

- Incremental sync
- Checkpoint tracking
- Background ingestion
- Fault-tolerant recovery

---

## Graph Retrieval (Neo4j)

Implements hybrid retrieval using knowledge graphs.

Capabilities:

- Entity linking
- Relationship-aware queries
- Graph-enhanced context retrieval

---

## Cloud Document Import

Supports ingestion from cloud-based sources.

Features:

- Remote file ingestion
- Background processing
- Fault tolerance

---

## Caching Layer

Response caching system:

- Reduces repeated compute
- Improves latency
- Persistent cache storage

---

## Streaming Responses

Supports streaming token output for real-time responses.

---

## Docker Deployment

Fully containerized system.

Run with:

```bash
docker compose up --build
```

---

## RunPod Deployment

This repo ships with everything needed to run on a RunPod pod (GPU or CPU) with the API, Ollama, and MySQL bundled, and persistent state on a network volume.

### 1. Create a network volume (one-time)

In the RunPod console, create a **Network Volume** (e.g. 50–100 GB). This will hold:

- ChromaDB embeddings
- MySQL data
- Ollama model weights
- HuggingFace embedding model cache

### 2. Launch a pod

- **Template:** any Ubuntu/CUDA image with Docker (e.g. RunPod's "Docker" or "PyTorch" templates).
- **GPU:** any modern NVIDIA card if you want fast Ollama inference (CPU works too, just slower).
- **Volume mount path:** `/workspace` (mounting the network volume from step 1).
- **Expose HTTP ports:** `8000` (FastAPI) and optionally `11434` (Ollama).

### 3. SSH into the pod and deploy

```bash
git clone <your repo> /app && cd /app
cp .env.runpod.example .env       # then edit secrets
docker compose up -d --build
```

The first start downloads the Ollama model and the sentence-transformers embedding model into `/workspace`; subsequent restarts are fast.

### 4. Verify

```bash
curl http://localhost:8000/                  # health check
curl http://localhost:11434/api/tags         # Ollama models
docker compose logs -f api                   # tail API logs
```

The API is reachable at `https://<pod-id>-8000.proxy.runpod.net/` once RunPod's HTTP proxy picks up the exposed port.

### Notes

- All persistent state lives under `/workspace`; pod recreations (kept on the same network volume) keep ChromaDB, MySQL data, and downloaded models.
- For GPU pods, uncomment the `deploy.resources` block in `docker-compose.yml`.
- To use an external MySQL instead, drop the `mysql` service and set `DATABASE_URL` directly in `.env`.

---

# Project Structure

```plaintext
app/
    __init__.py
    main.py
    rag.py
    ingest.py
    db_sync.py
    graph_search.py
    cache.py
    checkpoint.py
    cloud_links.py
    config.py
    client_identity.py
    multi_loader.py
    mySQL_DB.py
    neo4j_builder.py
    neo4j_config.py
    pdf_loader.py

scripts/
    bulk_ingest.py
    bulk_ingest_RRL.py
    insert_rlm_dataset.py

tests/
    test_neo4j_connection.py

archive/

Dockerfile
requirements.txt
requirements-optional.txt

.env.example
config.example.json
.gitignore
.dockerignore
README.md