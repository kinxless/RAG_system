#!/usr/bin/env bash
# Entrypoint: boots Ollama in the background, pulls the configured model,
# then launches the FastAPI server. Used by the RunPod pod image.

set -e

: "${MODEL_NAME:=phi3:mini}"
: "${OLLAMA_HOST:=0.0.0.0:11434}"
: "${OLLAMA_READY_TIMEOUT:=60}"
: "${UVICORN_HOST:=0.0.0.0}"
: "${UVICORN_PORT:=8000}"
: "${UVICORN_WORKERS:=1}"

mkdir -p "${DATA_DIR:-/workspace}"
mkdir -p "${OLLAMA_MODELS:-/workspace/ollama_models}"
mkdir -p "${HF_HOME:-/workspace/hf_cache}"

echo "[start.sh] Launching Ollama on ${OLLAMA_HOST}..."
ollama serve > /workspace/ollama.log 2>&1 &
OLLAMA_PID=$!

# Wait for Ollama to accept connections.
echo "[start.sh] Waiting for Ollama (timeout ${OLLAMA_READY_TIMEOUT}s)..."
for i in $(seq 1 "${OLLAMA_READY_TIMEOUT}"); do
    if curl -fs "http://127.0.0.1:11434/api/tags" > /dev/null 2>&1; then
        echo "[start.sh] Ollama ready after ${i}s"
        break
    fi
    if ! kill -0 "${OLLAMA_PID}" 2>/dev/null; then
        echo "[start.sh] Ollama exited early. See /workspace/ollama.log:"
        tail -n 80 /workspace/ollama.log || true
        exit 1
    fi
    sleep 1
done

# Pull the model if not present (no-op when already cached on the volume).
echo "[start.sh] Ensuring model '${MODEL_NAME}' is available..."
ollama pull "${MODEL_NAME}" || {
    echo "[start.sh] WARNING: ollama pull failed; continuing — server may serve cached models only."
}

# Trap to cleanly shut Ollama down when uvicorn exits.
trap 'echo "[start.sh] Shutting down..."; kill ${OLLAMA_PID} 2>/dev/null || true' EXIT INT TERM

echo "[start.sh] Starting uvicorn on ${UVICORN_HOST}:${UVICORN_PORT}..."
exec uvicorn app.main:app \
    --host "${UVICORN_HOST}" \
    --port "${UVICORN_PORT}" \
    --workers "${UVICORN_WORKERS}"
