FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install Python dependencies first for better layer caching.
COPY requirements.txt requirements-optional.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install chromadb pypdf neo4j mysql-connector-python sentence-transformers && \
    if [ -s requirements-optional.txt ]; then pip install -r requirements-optional.txt; fi

# Copy application source.
COPY . .

# Ensure local data directory exists for Chroma persistence.
RUN mkdir -p /app/chroma_db

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
