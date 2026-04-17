import json
import os
from dataclasses import dataclass
from typing import Any, Dict


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
                # Keep existing environment values as higher priority.
                os.environ.setdefault(key, value)


def _read_config_file(config_path: str) -> Dict[str, Any]:
    if not config_path or not os.path.exists(config_path):
        return {}

    _, ext = os.path.splitext(config_path.lower())

    if ext == ".json":
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}

    if ext in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "YAML config requested but PyYAML is not installed."
            ) from e

        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}

    raise RuntimeError(
        f"Unsupported config file extension: {ext}. Use .json, .yaml, or .yml."
    )


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class AppConfig:
    ollama_url: str
    model_name: str
    ollama_timeout_seconds: int
    ollama_stream_timeout_seconds: int
    cloud_import_timeout_seconds: int
    background_sync_interval_seconds: int
    redis_url: str
    cache_ttl_seconds: int


def load_app_config() -> AppConfig:
    _load_dotenv(".env")

    config_file = os.getenv("APP_CONFIG_FILE", "config.json")
    file_cfg = _read_config_file(config_file)

    default_cfg: Dict[str, Any] = {
        "OLLAMA_URL": "http://localhost:11434/api/generate",
        "MODEL_NAME": "phi3:mini",
        "OLLAMA_TIMEOUT_SECONDS": 180,
        "OLLAMA_STREAM_TIMEOUT_SECONDS": 300,
        "CLOUD_IMPORT_TIMEOUT_SECONDS": 120,
        "BACKGROUND_SYNC_INTERVAL_SECONDS": 30,
        "REDIS_URL": "",
        "CACHE_TTL_SECONDS": 86400,
    }

    merged_cfg = default_cfg.copy()
    merged_cfg.update(file_cfg)

    # Environment variables are highest priority.
    for key in default_cfg.keys():
        env_val = os.getenv(key)
        if env_val is not None:
            merged_cfg[key] = env_val

    return AppConfig(
        ollama_url=str(merged_cfg["OLLAMA_URL"]),
        model_name=str(merged_cfg["MODEL_NAME"]),
        ollama_timeout_seconds=_to_int(merged_cfg["OLLAMA_TIMEOUT_SECONDS"], 180),
        ollama_stream_timeout_seconds=_to_int(
            merged_cfg["OLLAMA_STREAM_TIMEOUT_SECONDS"], 300
        ),
        cloud_import_timeout_seconds=_to_int(
            merged_cfg["CLOUD_IMPORT_TIMEOUT_SECONDS"], 120
        ),
        background_sync_interval_seconds=_to_int(
            merged_cfg["BACKGROUND_SYNC_INTERVAL_SECONDS"], 30
        ),
        redis_url=str(merged_cfg["REDIS_URL"]),
        cache_ttl_seconds=_to_int(
            merged_cfg["CACHE_TTL_SECONDS"], 86400
        ),
    )
