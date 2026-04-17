import json
import os
import tempfile
import threading
import uuid
from typing import Optional


CLOUD_LINKS_FILE = "cloud_links.json"
_lock = threading.Lock()


def _read_store() -> dict:
    if not os.path.exists(CLOUD_LINKS_FILE):
        return {"links": []}

    with open(CLOUD_LINKS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        return {"links": []}

    links = data.get("links", [])
    if not isinstance(links, list):
        links = []

    return {"links": links}


def _write_store(data: dict) -> None:
    directory = os.path.dirname(os.path.abspath(CLOUD_LINKS_FILE)) or "."
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=directory,
        suffix=".tmp"
    ) as tmp_file:
        json.dump(data, tmp_file, ensure_ascii=True, indent=2)
        tmp_path = tmp_file.name

    os.replace(tmp_path, CLOUD_LINKS_FILE)


def create_cloud_link(
    name: str,
    url: str,
    provider: Optional[str] = None,
    client_id: Optional[str] = None,
    tags: Optional[list[str]] = None,
    metadata: Optional[dict] = None
) -> dict:
    with _lock:
        store = _read_store()
        link_id = uuid.uuid4().hex[:16]
        link = {
            "id": link_id,
            "name": name.strip(),
            "url": url.strip(),
            "provider": (provider or "").strip().lower(),
            "client_id": client_id,
            "tags": tags or [],
            "metadata": metadata or {}
        }
        store["links"].append(link)
        _write_store(store)
        return link


def list_cloud_links(
    client_id: Optional[str] = None,
    provider: Optional[str] = None
) -> list[dict]:
    with _lock:
        store = _read_store()
        links = store.get("links", [])

    output = []
    provider_filter = (provider or "").strip().lower()

    for link in links:
        if client_id and link.get("client_id") != client_id:
            continue
        if provider_filter and link.get("provider") != provider_filter:
            continue
        output.append(link)

    return output


def get_cloud_link(link_id: str) -> Optional[dict]:
    with _lock:
        store = _read_store()
        links = store.get("links", [])

    for link in links:
        if link.get("id") == link_id:
            return link

    return None


def delete_cloud_link(link_id: str) -> bool:
    with _lock:
        store = _read_store()
        links = store.get("links", [])

        new_links = [link for link in links if link.get("id") != link_id]
        if len(new_links) == len(links):
            return False

        store["links"] = new_links
        _write_store(store)
        return True
