import json
import os
from typing import Optional


DATA_DIR = os.getenv("DATA_DIR", ".")
CACHE_FILE = os.getenv("CACHE_FILE", os.path.join(DATA_DIR, "cache.json"))
DEFAULT_CACHE_TTL_SECONDS = 86400
_cache_store = {}
_redis_client = None


def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)


def _to_int(value: Optional[str], default: int) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _load_file_cache() -> None:
    global _cache_store
    if not os.path.exists(CACHE_FILE):
        _cache_store = {}
        return

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            _cache_store = data if isinstance(data, dict) else {}
    except Exception:
        _cache_store = {}


def _save_file_cache() -> None:
    cache_dir = os.path.dirname(CACHE_FILE)
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(_cache_store, f, ensure_ascii=True)


def _init_cache_backend() -> None:
    global _redis_client
    _load_dotenv(".env")

    redis_url = os.getenv("REDIS_URL", "").strip()
    if redis_url:
        try:
            import redis  # type: ignore

            _redis_client = redis.from_url(redis_url, decode_responses=True)
            _redis_client.ping()
            return
        except Exception:
            _redis_client = None

    _load_file_cache()


_init_cache_backend()


def get_cached_response(question: str) -> Optional[str]:
    if _redis_client is not None:
        try:
            return _redis_client.get(question)
        except Exception:
            pass

    return _cache_store.get(question)


def cache_response(question: str, response: str) -> None:
    if _redis_client is not None:
        ttl_seconds = _to_int(
            os.getenv("CACHE_TTL_SECONDS"),
            DEFAULT_CACHE_TTL_SECONDS
        )
        try:
            _redis_client.setex(question, ttl_seconds, response)
            return
        except Exception:
            pass

    _cache_store[question] = response
    _save_file_cache()
