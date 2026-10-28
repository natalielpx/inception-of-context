"""UI code calls only these functions. `direct` mode reads Qdrant and the events log (Part 1).
`api` mode calls the IoC API (Parts 2-3) and must return the same shapes.

Every function is synchronous (the UI wraps it in `run.io_bound`). Failures come back as
{"error": "..."} instead of raising, except NotImplementedError for features not built yet.
"""
import functools
import json
import os
from collections import Counter, deque
from pathlib import Path

from qdrant_client import QdrantClient, models

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "chunks")
TARGET_PATH = Path(os.getenv("TARGET_PATH", "/workspace"))
LOG_FILE = Path(os.getenv("LOG_FILE", "/data/ioc_events.jsonl"))
API_URL = os.getenv("API_URL", "http://api:8000")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

_client: QdrantClient | None = None


def source_mode() -> str:
    return "api" if os.getenv("IOC_SOURCE", "direct").lower() == "api" else "direct"


def client() -> QdrantClient:
    global _client  # one client per process, created on first use
    if _client is None:
        _client = QdrantClient(url=QDRANT_URL, timeout=5)
    return _client


def _index_fn(fn):
    """Direct-mode only for now; turns any backend failure into {"error": ...}."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if source_mode() == "api":
            raise NotImplementedError("api mode arrives in Part 2")  # TODO(p2): call API_URL with httpx
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # connection refused, missing collection, unreadable file...
            return {"error": f"{type(e).__name__}: {e}"}
    return wrapper


def _path_filter(path: str | None) -> models.Filter | None:
    if not path:
        return None
    return models.Filter(must=[models.FieldCondition(key="path", match=models.MatchValue(value=path))])


def _scroll_all(flt=None, payload=True) -> list:
    points, cursor = [], None
    while True:
        page, cursor = client().scroll(COLLECTION, scroll_filter=flt, limit=256, offset=cursor, with_payload=payload)
        points += page
        if cursor is None:
            return points


@_index_fn
def get_files() -> list[dict]:
    counts = Counter(p.payload.get("path") for p in _scroll_all(payload=["path"]))
    return [{"path": path, "chunks": n} for path, n in sorted(counts.items())]


@_index_fn
def get_status() -> dict:
    files = get_files()
    if isinstance(files, dict):
        return files
    return {
        "chunks": client().count(COLLECTION, exact=True).count,
        "files": len(files),
        "target_path": str(TARGET_PATH),
        "qdrant_url": QDRANT_URL,
        "collection": COLLECTION,
        "embedding_model": EMBEDDING_MODEL,
        "ask_model": None,   # set by the API in Part 2
        "code_model": None,  # set by the API in Part 3
    }


@_index_fn
def get_file(path: str) -> dict:
    root = TARGET_PATH.resolve()
    full = (root / path).resolve()
    if not full.is_relative_to(root):
        return {"error": f"path outside target: {path}"}
    if not full.is_file():
        return {"error": "file was deleted", "missing": True}
    content = full.read_text(errors="replace")
    points = _scroll_all(_path_filter(path), payload=["start_line", "end_line", "symbol", "kind"])
    chunks = sorted(({"id": str(p.id), **p.payload} for p in points), key=lambda c: c["start_line"])
    return {"path": path, "content": content, "lines": len(content.splitlines()),
            "bytes": full.stat().st_size, "chunks": chunks}


@_index_fn
def get_chunks(path_filter: str | None = None, limit: int = 50, cursor=None):
    page, next_cursor = client().scroll(COLLECTION, scroll_filter=_path_filter(path_filter),
                                        limit=limit, offset=cursor, with_payload=True)
    return [{"id": str(p.id), **p.payload} for p in page], next_cursor


def get_events(n: int = 50) -> list[dict]:
    if source_mode() == "api":
        raise NotImplementedError("api mode arrives in Part 2")  # TODO(p2): GET /events (SSE)
    try:
        with LOG_FILE.open() as f:
            lines = deque(f, maxlen=n)
    except FileNotFoundError:
        return []
    except OSError as e:
        return {"error": str(e)}
    events = []
    for line in reversed(lines):
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass  # the watcher may be mid-write
    return events


# ---- Part 2-3 contract (not implemented yet) ----

def retrieve(query: str, k: int = 5) -> list[dict]:
    """POST /context -> chunks with a `score` key."""
    raise NotImplementedError("retrieve arrives in Part 2")


def ask(question: str, k: int = 5, session_id: str | None = None) -> dict:
    """POST /ask -> {answer, session_id, resolved_facts, sources}."""
    raise NotImplementedError("ask arrives in Part 2")


def run_patch(intent: str, k: int = 5, max_attempts: int = 3) -> dict:
    """-> {status: success|failed|rejected, attempts_used, rolled_back, reason, final_patch, attempts}."""
    raise NotImplementedError("run_patch arrives in Part 3")
