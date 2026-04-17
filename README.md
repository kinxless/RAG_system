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
docker-compose up --build

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