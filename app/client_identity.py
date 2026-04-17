import re
from typing import Optional


MAX_CLIENT_ID_LENGTH = 64


def normalize_client_id(client_id: Optional[str]) -> Optional[str]:
    if client_id is None:
        return None

    normalized = str(client_id).strip().lower()
    if not normalized:
        return None

    # Canonical form to keep collections/cache keys stable.
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = re.sub(r"[^a-z0-9_-]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")

    if not normalized:
        raise ValueError("Invalid client_id after normalization.")

    return normalized[:MAX_CLIENT_ID_LENGTH]
