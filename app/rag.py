import chromadb
from chromadb.utils import embedding_functions
from collections import Counter
import os
import uuid
import re
from typing import Optional, List, Dict, Any
from app.client_identity import normalize_client_id

# =========================
# CONFIG
# =========================

DATA_DIR = os.getenv("DATA_DIR", ".")
CHROMA_PATH = os.getenv("CHROMA_PATH", os.path.join(DATA_DIR, "chroma_db"))

COLLECTION_NAME = "rasid_cases"

# Embedding model. Default is English-only; for multilingual data set
# EMBED_MODEL_NAME=paraphrase-multilingual-MiniLM-L12-v2 (or larger).
EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME", "all-MiniLM-L6-v2")

DEFAULT_K = 20
CLIENT_COLLECTION_PREFIX = "client"


# =========================
# LAZY INIT CHROMA
# =========================

embedding_function = None
client = None
collection = None
_init_error: Optional[Exception] = None
_collection_cache = {}


def _ensure_initialized():
    global embedding_function, client, collection, _init_error

    if (
        embedding_function is not None
        and client is not None
        and collection is not None
    ):
        return

    if _init_error is not None:
        raise RuntimeError(
            "RAG initialization failed previously. "
            "Ensure embedding model is available and network access is allowed."
        ) from _init_error

    try:
        if not os.path.exists(CHROMA_PATH):
            os.makedirs(CHROMA_PATH)

        embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBED_MODEL_NAME
        )

        client = chromadb.PersistentClient(
            path=CHROMA_PATH
        )

        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_function
        )
        _collection_cache[COLLECTION_NAME] = collection

    except Exception as e:
        _init_error = e
        raise RuntimeError(
            "Failed to initialize RAG backend. "
            "Check model download/network and Chroma setup."
        ) from e


def _get_or_create_collection_by_name(name: str):
    cached = _collection_cache.get(name)
    if cached is not None:
        return cached

    col = client.get_or_create_collection(
        name=name,
        embedding_function=embedding_function
    )
    _collection_cache[name] = col
    return col


# ==========================================================
# NEW — RISK DETECTION + AGGREGATION
# ==========================================================

def detect_risk_query(query):

    query = query.lower()

    risk_keywords = [
        "risk",
        "risks",
        "most common",
        "common risks",
        "frequent risks",
        "top risks",
        "most repeated"
    ]

    return any(
        keyword in query
        for keyword in risk_keywords
    )


def extract_risks_from_docs(docs):

    risks = []

    for doc in docs:

        matches = re.findall(
            r"risk(?:\s|_|-)*description\s*:\s*(.+)",
            doc.lower()
        )

        for m in matches:

            cleaned = m.strip()

            if cleaned:
                risks.append(cleaned)

    return risks


def aggregate_risks(docs):

    risks = extract_risks_from_docs(docs)

    if not risks:
        return ["No risks found."]

    counter = Counter(risks)

    most_common = counter.most_common(5)

    results = []

    for i, (risk, count) in enumerate(most_common):

        results.append(
            f"{i+1}. {risk} (appeared {count} times)"
        )

    return results


# =========================
# TEXT SPLITTING
# =========================

def split_text(
    text,
    chunk_size=500,
    overlap=50
):

    chunks = []

    start = 0

    text_length = len(text)

    while start < text_length:

        end = start + chunk_size

        chunk = text[start:end]

        if chunk.strip():
            chunks.append(chunk)

        start += chunk_size - overlap

    print("Chunks created:", len(chunks))

    return chunks


# =========================
# NUMBER EXTRACTION
# =========================

def extract_numbers(text):

    numbers = re.findall(r"\d+", text)

    return numbers


def _normalize_tags(tags) -> List[str]:
    if not tags:
        return []

    if isinstance(tags, str):
        raw_tags = [t.strip() for t in tags.split(",")]
    else:
        raw_tags = [str(t).strip() for t in tags]

    # Keep order while removing duplicates and empty values.
    seen = set()
    normalized = []

    for tag in raw_tags:
        clean = tag.lower()
        if clean and clean not in seen:
            normalized.append(clean)
            seen.add(clean)

    return normalized


def _sanitize_extra_metadata(extra_metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not extra_metadata:
        return {}

    clean = {}

    for key, value in extra_metadata.items():
        key_str = str(key).strip().lower()
        if not key_str:
            continue

        safe_key = re.sub(r"[^a-z0-9_]+", "_", key_str)
        safe_key = safe_key.strip("_")
        if not safe_key:
            continue

        namespaced_key = f"meta_{safe_key[:50]}"

        if isinstance(value, (str, int, float, bool)):
            clean[namespaced_key] = value
        elif value is None:
            continue
        else:
            # Chroma metadata supports scalar values; fallback to string.
            clean[namespaced_key] = str(value)

    return clean


def _resolve_collection_name(
    collection_name: Optional[str] = None,
    client_id: Optional[str] = None
) -> str:
    if collection_name:
        return collection_name

    normalized_client = normalize_client_id(client_id)
    if normalized_client:
        return f"{COLLECTION_NAME}__{CLIENT_COLLECTION_PREFIX}__{normalized_client}"

    return COLLECTION_NAME


def _matches_tag_filter(metadata, tag_filter: Optional[str]) -> bool:
    if not tag_filter:
        return True

    if not metadata:
        return False

    tags_csv = str(metadata.get("tags", "")).strip().lower()
    if not tags_csv:
        return False

    current_tags = [t.strip() for t in tags_csv.split(",") if t.strip()]
    return tag_filter.strip().lower() in current_tags


# =========================
# ADD TEXT TO VECTOR DB
# =========================

def add_text(
    text,
    source,
    collection_name=None,
    tags=None,
    client_id=None,
    extra_metadata=None
):
    _ensure_initialized()

    print("\n=== ADD TEXT ===")

    normalized_client = normalize_client_id(client_id)
    collection_name = _resolve_collection_name(
        collection_name=collection_name,
        client_id=normalized_client
    )
    normalized_client = normalized_client or "shared"

    print("Source:", source)
    print("Collection:", collection_name)
    normalized_tags = _normalize_tags(tags)
    tags_csv = ",".join(normalized_tags)
    sanitized_extra_metadata = _sanitize_extra_metadata(extra_metadata)

    collection = _get_or_create_collection_by_name(collection_name)

    chunks = split_text(text)

    ids = []
    documents = []
    metadatas = []

    for i, chunk in enumerate(chunks):

        unique_id = f"{source}_{uuid.uuid4()}"

        ids.append(unique_id)

        documents.append(chunk)

        metadata = {
            "source": source,
            "chunk_index": i,
            "collection": collection_name,
            "tags": tags_csv,
            "client_id": normalized_client
        }
        metadata.update(sanitized_extra_metadata)
        metadatas.append(metadata)

    if documents:

        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

        print(
            f"Added {len(documents)} chunks to {collection_name}"
        )

    else:

        print("No documents added.")


# =========================
# BULK ADD (BATCHED — for db_sync etc.)
# =========================

def add_texts_bulk(
    items,
    collection_name=None,
    client_id=None,
):
    """Embed and persist many (text, source) pairs in a single Chroma write.

    items: list of dicts with keys {text, source, tags?, extra_metadata?}.
    All items go into the same collection. Per-item Chroma overhead is
    amortized across the whole batch, so this is ~50x faster than calling
    add_text() per row.
    """
    _ensure_initialized()

    if not items:
        return

    normalized_client = normalize_client_id(client_id)
    collection_name = _resolve_collection_name(
        collection_name=collection_name,
        client_id=normalized_client,
    )
    normalized_client = normalized_client or "shared"

    collection = _get_or_create_collection_by_name(collection_name)

    ids = []
    documents = []
    metadatas = []

    for item in items:
        text = item.get("text", "")
        source = item.get("source", "")
        if not text or not text.strip():
            continue

        normalized_tags = _normalize_tags(item.get("tags"))
        tags_csv = ",".join(normalized_tags)
        sanitized_extra = _sanitize_extra_metadata(item.get("extra_metadata"))

        chunks = split_text(text)
        for i, chunk in enumerate(chunks):
            ids.append(f"{source}_{uuid.uuid4()}")
            documents.append(chunk)
            metadata = {
                "source": source,
                "chunk_index": i,
                "collection": collection_name,
                "tags": tags_csv,
                "client_id": normalized_client,
            }
            metadata.update(sanitized_extra)
            metadatas.append(metadata)

    if documents:
        collection.add(ids=ids, documents=documents, metadatas=metadatas)
        print(
            f"Bulk added {len(documents)} chunks "
            f"from {len(items)} items to {collection_name}"
        )


# =========================
# MAIN HYBRID SEARCH
# =========================

def vector_keyword_search(
    query,
    k=DEFAULT_K,
    tag_filter=None,
    client_id=None
):
    _ensure_initialized()

    print("\n=== COLLECTION SEARCH ===")

    print("Query:", query)

    output_docs = []

    # FIX — search ALL collections instead of just rag_collection
    collections = client.list_collections()

    print(
        f"\nSearching across {len(collections)} collections"
    )

    for col_info in collections:

        target_collection_name = col_info.name

        print(f"\nSearching collection: {target_collection_name}")

        collection = _get_or_create_collection_by_name(
            target_collection_name
        )

        try:

            results = collection.query(
                query_texts=[query],
                n_results=max(1, int(k))
            )

        except Exception as e:

            print(
                f"Query error in {target_collection_name}:",
                e
            )
            continue

        documents = results.get(
            "documents",
            [[]]
        )[0]

        metadatas = results.get(
            "metadatas",
            [[]]
        )[0]

        print(
            f"Found {len(documents)} results in {target_collection_name}"
        )

        for i in range(len(documents)):

            doc = documents[i]

            metadata = {}

            if i < len(metadatas):

                metadata = metadatas[i]

            source = metadata.get(
                "source",
                "unknown"
            )

            chunk_index = metadata.get(
                "chunk_index",
                "unknown"
            )

            if not _matches_tag_filter(metadata, tag_filter):
                continue

            tags_value = metadata.get(
                "tags",
                "none"
            ) or "none"
            client_value = metadata.get(
                "client_id",
                "shared"
            ) or "shared"
            extra_meta_items = []
            for meta_key, meta_value in metadata.items():
                if str(meta_key).startswith("meta_"):
                    extra_meta_items.append(f"{meta_key[5:]}={meta_value}")
            extra_meta_text = ", ".join(extra_meta_items) if extra_meta_items else "none"

            formatted_doc = f"""
{doc}

-----------------------
SOURCE INFORMATION:

Collection: {target_collection_name}
Source: {source}
Chunk Index: {chunk_index}
Tags: {tags_value}
Client: {client_value}
Metadata: {extra_meta_text}
"""

            output_docs.append(
                formatted_doc
            )

    print(
        "\nTotal documents returned:",
        len(output_docs)
    )

    # ==========================================================
    # NEW — RISK AGGREGATION TRIGGER
    # ==========================================================

    if detect_risk_query(query):

        print("\n=== RISK AGGREGATION TRIGGERED ===")

        return aggregate_risks(output_docs)

    return output_docs


# =========================
# DEBUG UTILITIES
# =========================

def debug_collection():
    _ensure_initialized()

    print("\n=== COLLECTION DEBUG ===")

    try:

        count = collection.count()

        print(
            "Total stored chunks:",
            count
        )

    except Exception as e:

        print(
            "Collection debug error:",
            e
        )


# =========================
# RESET COLLECTION (Optional)
# =========================

def reset_collection():

    global collection
    _ensure_initialized()

    print("\nResetting collection...")

    client.delete_collection(
        COLLECTION_NAME
    )
    _collection_cache.pop(COLLECTION_NAME, None)

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function
    )
    _collection_cache[COLLECTION_NAME] = collection

    print("Collection reset complete.")
