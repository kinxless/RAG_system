# RunPod GPU pod image: CUDA base + Python + Ollama + FastAPI app.
# CPU-only pods will still work — Ollama and torch fall back to CPU.

FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive \
    DATA_DIR=/workspace \
    CHROMA_PATH=/workspace/chroma_db \
    CACHE_FILE=/workspace/cache.json \
    CHECKPOINT_FILE=/workspace/sync_checkpoint.json \
    CLOUD_LINKS_FILE=/workspace/cloud_links.json \
    OLLAMA_HOST=0.0.0.0:11434 \
    OLLAMA_URL=http://127.0.0.1:11434/api/generate \
    OLLAMA_MODELS=/workspace/ollama_models \
    HF_HOME=/workspace/hf_cache \
    SENTENCE_TRANSFORMERS_HOME=/workspace/hf_cache \
    MODEL_NAME=phi3:mini

# System deps + Ollama installer prerequisites.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.10 python3-pip python3.10-venv \
        curl ca-certificates git \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.10 /usr/bin/python \
    && ln -sf /usr/bin/python3.10 /usr/bin/python3

# Ollama (binary install).
RUN curl -fsSL https://ollama.com/install.sh | sh

WORKDIR /app

# Python deps first for layer caching.
COPY requirements.txt requirements-optional.txt ./
RUN pip install --upgrade pip \
 && pip install -r requirements.txt \
 && if [ -s requirements-optional.txt ]; then pip install -r requirements-optional.txt; fi

# App source.
COPY . .

# Make entrypoint executable.
RUN chmod +x /app/start.sh

# Persistent volume mount target on RunPod is /workspace by convention.
RUN mkdir -p /workspace

EXPOSE 8000 11434

CMD ["/app/start.sh"]
