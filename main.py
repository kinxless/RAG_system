from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Header
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import httpx
import json
import asyncio
import traceback
import os
import tempfile
from urllib.parse import urlparse, unquote
from typing import Optional

# RAG
from rag import add_text, vector_keyword_search, detect_risk_query


# Utilities
from multi_loader import load_file
from cache import get_cached_response, cache_response
from db_sync import sync_database
from config import load_app_config
from client_identity import normalize_client_id
from cloud_links import (
    create_cloud_link,
    list_cloud_links,
    get_cloud_link,
    delete_cloud_link
)


APP_CONFIG = load_app_config()
HTTP_ASYNC_CLIENT: Optional[httpx.AsyncClient] = None


# =========================
# REQUEST MODEL
# =========================

class QuestionRequest(BaseModel):
    question: str
    tag: Optional[str] = None
    client_id: Optional[str] = None


class CloudImportRequest(BaseModel):
    url: str
    tags: list[str] = Field(default_factory=list)
    client_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class CloudLinkCreateRequest(BaseModel):
    name: str
    url: str
    provider: Optional[str] = None
    client_id: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class CloudLinkImportRequest(BaseModel):
    client_id: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


def _parse_tags(tags_text: Optional[str]) -> list[str]:
    if not tags_text:
        return []

    parsed = [t.strip().lower() for t in tags_text.split(",")]

    # Keep order while removing duplicates and empty values.
    seen = set()
    normalized = []
    for tag in parsed:
        if tag and tag not in seen:
            normalized.append(tag)
            seen.add(tag)

    return normalized


def _normalize_tags_list(tags: Optional[list[str]]) -> list[str]:
    if not tags:
        return []
    return _parse_tags(",".join([str(t) for t in tags]))


def _parse_metadata_json(metadata_json: Optional[str]) -> dict:
    if not metadata_json:
        return {}

    raw = metadata_json.strip()
    if not raw:
        return {}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metadata_json: {str(e)}"
        ) from e

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=400,
            detail="metadata_json must be a JSON object."
        )

    return data


def _resolve_client_id(
    request_client_id: Optional[str],
    header_client_id: Optional[str]
) -> Optional[str]:
    raw_client_id = request_client_id if request_client_id else header_client_id

    if raw_client_id is None:
        return None

    try:
        return normalize_client_id(raw_client_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        ) from e


def _normalize_tag(tag: Optional[str]) -> Optional[str]:
    if not tag:
        return None
    cleaned = tag.strip().lower()
    return cleaned or None


def _build_cache_key(
    question: str,
    tag: Optional[str],
    client_id: Optional[str]
) -> str:
    cache_key = question
    if tag:
        cache_key = f"{cache_key}||tag:{tag}"
    if client_id:
        cache_key = f"{cache_key}||client:{client_id}"
    return cache_key


def _build_prompt(context: str, question: str) -> str:
    return f"""
You must answer ONLY using the provided database context.

If the answer is not inside the context,
reply exactly:

DATA NOT FOUND IN DATABASE

---------------------

DATABASE CONTEXT:

{context}

---------------------

USER QUESTION:

{question}
"""


def _get_http_client() -> httpx.AsyncClient:
    if HTTP_ASYNC_CLIENT is None:
        raise HTTPException(
            status_code=503,
            detail="HTTP client not initialized."
        )
    return HTTP_ASYNC_CLIENT


async def _ingest_cloud_source(
    source_url: str,
    tags: list[str],
    metadata: dict,
    normalized_client_id: Optional[str]
) -> dict:
    tmp_path = None

    try:
        http_client = _get_http_client()
        async with http_client.stream(
            "GET",
            source_url,
            timeout=APP_CONFIG.cloud_import_timeout_seconds
        ) as response:
            response.raise_for_status()

            parsed = urlparse(source_url)
            filename = os.path.basename(parsed.path)
            filename = unquote(filename)

            if not filename:
                filename = "cloud_import"

            _, ext = os.path.splitext(filename)
            ext = ext.lower()

            if not ext:
                content_type = response.headers.get("content-type", "").lower()
                if "pdf" in content_type:
                    ext = ".pdf"
                elif "json" in content_type:
                    ext = ".json"
                elif "markdown" in content_type:
                    ext = ".md"
                elif "html" in content_type:
                    ext = ".html"
                else:
                    ext = ".txt"

            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=ext
            ) as tmp_file:
                tmp_path = tmp_file.name
                async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                    if chunk:
                        tmp_file.write(chunk)

        text = load_file(tmp_path)

        if not text or not text.strip():
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type or empty cloud file."
            )

        add_text(
            text,
            source_url,
            tags=tags,
            client_id=normalized_client_id,
            extra_metadata=metadata
        )

        return {
            "message": "Cloud document imported successfully",
            "source": source_url,
            "tags": tags,
            "metadata": metadata,
            "client_id": normalized_client_id or "shared"
        }

    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to download file from URL: {str(e)}"
        ) from e

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


# =========================
# FASTAPI APP
# =========================

app = FastAPI(
    title="RAG AI Backend",
    description="Recursive RAG + Graph + MySQL Sync API",
    version="1.2"
)


# =========================
# CORS
# =========================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# HEALTH CHECK
# =========================

@app.get("/")
def root():

    return {
        "status": "Backend running",
        "message": "RAG system ready"
    }


# =========================
# UPLOAD PDF
# =========================

@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    tags: str = Form(""),
    metadata_json: str = Form(""),
    client_id: str = Form(""),
    x_client_id: Optional[str] = Header(default=None, alias="X-Client-ID")
):

    tmp_path = None

    try:

        print(f"\nUploading file: {file.filename}")

        suffix = os.path.splitext(file.filename or "")[1]
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        ) as tmp_file:
            tmp_path = tmp_file.name
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                tmp_file.write(chunk)

        text = load_file(tmp_path)

        if not text or not text.strip():
            raise HTTPException(
                status_code=400,
                detail="Unsupported or empty file content."
            )

        print("Extracted text length:", len(text))

        parsed_tags = _parse_tags(tags)
        parsed_metadata = _parse_metadata_json(metadata_json)
        normalized_client_id = _resolve_client_id(client_id, x_client_id)

        add_text(
            text,
            file.filename,
            tags=parsed_tags,
            client_id=normalized_client_id,
            extra_metadata=parsed_metadata
        )

        return {
            "message": "Document uploaded successfully",
            "tags": parsed_tags,
            "metadata": parsed_metadata,
            "client_id": normalized_client_id or "shared"
        }

    except HTTPException:
        raise

    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=502,
            detail=f"HTTP error while streaming from model server: {str(e)}"
        ) from e

    except Exception as e:

        print("\nUPLOAD ERROR:")
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        await file.close()
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


# =========================
# IMPORT CLOUD FILE (URL)
# =========================

@app.post("/import_cloud")
async def import_cloud(
    data: CloudImportRequest,
    x_client_id: Optional[str] = Header(default=None, alias="X-Client-ID")
):

    try:

        source_url = data.url.strip()

        if not source_url:
            raise HTTPException(
                status_code=400,
                detail="URL is required."
            )

        print(f"\nImporting cloud file: {source_url}")

        normalized_client_id = _resolve_client_id(data.client_id, x_client_id)
        normalized_tags = _normalize_tags_list(data.tags)

        return await _ingest_cloud_source(
            source_url=source_url,
            tags=normalized_tags,
            metadata=data.metadata,
            normalized_client_id=normalized_client_id
        )

    except HTTPException:
        raise

    except Exception as e:

        print("\nCLOUD IMPORT ERROR:")
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================
# CLOUD LINKS
# =========================

@app.post("/cloud_links")
async def create_link(
    data: CloudLinkCreateRequest,
    x_client_id: Optional[str] = Header(default=None, alias="X-Client-ID")
):
    normalized_client_id = _resolve_client_id(data.client_id, x_client_id)
    normalized_tags = _normalize_tags_list(data.tags)

    if not data.name.strip():
        raise HTTPException(status_code=400, detail="name is required.")
    if not data.url.strip():
        raise HTTPException(status_code=400, detail="url is required.")

    link = create_cloud_link(
        name=data.name,
        url=data.url,
        provider=data.provider,
        client_id=normalized_client_id,
        tags=normalized_tags,
        metadata=data.metadata
    )

    return {
        "message": "Cloud link created",
        "link": link
    }


@app.get("/cloud_links")
async def get_links(
    client_id: Optional[str] = None,
    provider: Optional[str] = None,
    x_client_id: Optional[str] = Header(default=None, alias="X-Client-ID")
):
    normalized_client_id = _resolve_client_id(client_id, x_client_id)
    links = list_cloud_links(
        client_id=normalized_client_id,
        provider=provider
    )
    return {"links": links}


@app.delete("/cloud_links/{link_id}")
async def remove_link(link_id: str):
    deleted = delete_cloud_link(link_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Cloud link not found.")
    return {"message": "Cloud link deleted", "id": link_id}


@app.post("/import_cloud_link/{link_id}")
async def import_cloud_link(
    link_id: str,
    data: Optional[CloudLinkImportRequest] = None,
    x_client_id: Optional[str] = Header(default=None, alias="X-Client-ID")
):
    if data is None:
        data = CloudLinkImportRequest()

    link = get_cloud_link(link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Cloud link not found.")

    normalized_client_id = _resolve_client_id(
        data.client_id if data.client_id else link.get("client_id"),
        x_client_id
    )

    link_tags = _normalize_tags_list(link.get("tags") or [])
    request_tags = _normalize_tags_list(data.tags)
    merged_tags = _normalize_tags_list(link_tags + request_tags)

    merged_metadata = {}
    merged_metadata.update(link.get("metadata") or {})
    merged_metadata.update(data.metadata or {})

    print(f"\nImporting cloud link {link_id}: {link.get('url')}")

    result = await _ingest_cloud_source(
        source_url=str(link.get("url", "")).strip(),
        tags=merged_tags,
        metadata=merged_metadata,
        normalized_client_id=normalized_client_id
    )

    result["link_id"] = link_id
    result["link_name"] = link.get("name")
    return result


# =========================
# STANDARD RAG QUERY
# =========================

@app.post("/ask_rag")
async def ask_rag(
    question: str,
    tag: Optional[str] = None,
    client_id: Optional[str] = None,
    x_client_id: Optional[str] = Header(default=None, alias="X-Client-ID")
):

    try:

        print("\n--- NEW REQUEST ---")

        question = question.strip().lower()
        tag = _normalize_tag(tag)

        print("Question:", question)

        # =========================
        # CACHE
        # =========================

        normalized_client_id = _resolve_client_id(client_id, x_client_id)
        cache_key = _build_cache_key(question, tag, normalized_client_id)

        cached = get_cached_response(cache_key)

        if cached:

            print("CACHE HIT")

            return {
                "answer": cached
            }

        print("CACHE MISS")

        # =========================
        # RETRIEVE CONTEXT
        # =========================

        context_docs = vector_keyword_search(
            question,
            tag_filter=tag,
            client_id=normalized_client_id
        )

        print("Docs retrieved:", len(context_docs))

        if detect_risk_query(question):

            if isinstance(context_docs, list):
                return {
                    "answer": "\n".join(context_docs)
                }

            return {
                "answer": str(context_docs)
            }

        # Handle aggregation returning list
        if isinstance(context_docs, list):

            if len(context_docs) == 0:

                return {
                    "answer": "No relevant data found in database."
                }

            context = "\n\n".join(context_docs)

        else:

            context = str(context_docs)

        # =========================
        # PROMPT
        # =========================

        prompt = _build_prompt(context, question)

        print("Calling Ollama...")
        http_client = _get_http_client()

        response = await http_client.post(
            APP_CONFIG.ollama_url,
            json={
                "model": APP_CONFIG.model_name,
                "prompt": prompt,
                "stream": False
            },
            timeout=APP_CONFIG.ollama_timeout_seconds
        )

        print("Ollama status:", response.status_code)

        if response.status_code != 200:

            raise HTTPException(
                status_code=500,
                detail=f"Ollama error: {response.text}"
            )

        result = response.json()

        if "response" not in result:

            raise HTTPException(
                status_code=500,
                detail=f"Invalid Ollama response: {result}"
            )

        answer = result["response"]

        cache_response(
            cache_key,
            answer
        )

        print("Answer cached")

        return {
            "answer": answer,
            "client_id": normalized_client_id or "shared"
        }

    except HTTPException:
        raise

    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=502,
            detail=f"HTTP error while calling model server: {str(e)}"
        ) from e

    except Exception as e:

        print("\n=== RAG ERROR ===")
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================
# STREAMING RAG QUERY
# =========================

@app.post("/ask_rag_stream")
async def ask_rag_stream(
    data: QuestionRequest,
    x_client_id: Optional[str] = Header(default=None, alias="X-Client-ID")
):

    try:

        question = data.question.strip().lower()
        tag = _normalize_tag(data.tag)
        client_id = _resolve_client_id(data.client_id, x_client_id)

        print("\n--- STREAM REQUEST ---")
        print("Question:", question)

        # =========================
        # CACHE
        # =========================

        cache_key = _build_cache_key(question, tag, client_id)

        cached = get_cached_response(cache_key)

        if cached:

            print("STREAM CACHE HIT")

            return StreamingResponse(
                iter([cached]),
                media_type="text/plain"
            )

        print("STREAM CACHE MISS")

        # =========================
        # RETRIEVE CONTEXT
        # =========================

        context_docs = vector_keyword_search(
            question,
            tag_filter=tag,
            client_id=client_id
        )

        print("Docs retrieved:", len(context_docs))

        if detect_risk_query(question):

            if isinstance(context_docs, list):
                return StreamingResponse(
                    iter(["\n".join(context_docs)]),
                    media_type="text/plain"
                )

            return StreamingResponse(
                iter([str(context_docs)]),
                media_type="text/plain"
            )

        if isinstance(context_docs, list):

            if len(context_docs) == 0:

                return StreamingResponse(
                    iter(["No relevant data found in database."]),
                    media_type="text/plain"
                )

            context = "\n\n".join(context_docs)

        else:

            context = str(context_docs)

        # =========================
        # PROMPT
        # =========================

        prompt = _build_prompt(context, question)

        async def generate():

            try:

                print("Streaming from Ollama...")
                http_client = _get_http_client()

                async with http_client.stream(
                    "POST",
                    APP_CONFIG.ollama_url,
                    json={
                        "model": APP_CONFIG.model_name,
                        "prompt": prompt,
                        "stream": True
                    },
                    timeout=APP_CONFIG.ollama_stream_timeout_seconds
                ) as response:

                    if response.status_code != 200:

                        error_text = await response.aread()
                        print("Ollama error:", error_text)

                        yield "[ERROR: Ollama failed]"
                        return

                    full_response = ""

                    async for line in response.aiter_lines():

                        if not line:
                            continue

                        try:
                            data_line = json.loads(line)
                        except Exception:
                            continue

                        if data_line.get("done"):
                            break

                        if "response" in data_line:

                            token = data_line["response"]

                            if token:

                                full_response += token

                                yield token

                cache_response(
                    cache_key,
                    full_response
                )

                print("Stream cached")

            except Exception:

                print("\nSTREAM ERROR:")
                traceback.print_exc()

                yield "[ERROR: Stream failed]"

        return StreamingResponse(
            generate(),
            media_type="text/plain"
        )

    except HTTPException:
        raise

    except Exception as e:

        print("\n=== STREAM ERROR ===")
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================
# MANUAL DATABASE SYNC
# =========================

@app.post("/sync_database")
def sync_db():

    try:

        print("Manual database sync triggered")

        sync_database()

        return {
            "status": "Database synced"
        }

    except Exception as e:

        print("\nSYNC ERROR:")
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================
# BACKGROUND SYNC LOOP
# =========================

#@app.on_event("startup")
#async def start_background_sync():
    global HTTP_ASYNC_CLIENT

    if HTTP_ASYNC_CLIENT is None:
        HTTP_ASYNC_CLIENT = httpx.AsyncClient(follow_redirects=True)

    async def sync_loop():

        while True:

            try:

                print("Running background sync...")

                sync_database()

            except Exception as e:

                print("Sync error:", e)

            await asyncio.sleep(APP_CONFIG.background_sync_interval_seconds)

    asyncio.create_task(sync_loop())
@app.on_event("startup")
async def startup_http_client():
    global HTTP_ASYNC_CLIENT

    if HTTP_ASYNC_CLIENT is None:
        HTTP_ASYNC_CLIENT = httpx.AsyncClient(
            follow_redirects=True
        )

@app.on_event("shutdown")
async def shutdown_http_client():
    global HTTP_ASYNC_CLIENT
    if HTTP_ASYNC_CLIENT is not None:
        await HTTP_ASYNC_CLIENT.aclose()
        HTTP_ASYNC_CLIENT = None
