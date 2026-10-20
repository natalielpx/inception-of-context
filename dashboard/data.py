"""Tabs call only these functions. `direct` mode reads Qdrant and the events log (Part 1).
`api` mode calls the IoC API (Parts 2–3) and must return the same shapes.

On failure, index functions return {"error": "..."} (get_chunks: ({"error": "..."}, None))
instead of raising, so tabs can show st.error. Use error_of() to test a result.
"""
import functools
import json
import os
from collections import Counter, deque
from pathlib import Path

import streamlit as st
from qdrant_client import QdrantClient, models

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "ioc_chunks")
TARGET_PATH = Path(os.getenv("TARGET_PATH", "/workspace")).resolve()
EVENTS_LOG = Path(os.getenv("EVENTS_LOG", "/data/ioc_events.jsonl"))
API_URL = os.getenv("API_URL", "http://api:8000")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")


def source_mode() -> str:
    return "api" if os.getenv("IOC_SOURCE", "direct").strip().lower() == "api" else "direct"


def error_of(result):
    """The error message if `result` is an error, else None."""
    return result.get("error") if isinstance(result, dict) else None


@st.cache_resource
def _client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL, timeout=5)


def _index(on_error=lambda msg: {"error": msg}):
    """Direct-mode index function: api mode is not wired yet, and errors become values."""
    def deco(fn):
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            if source_mode() == "api":
                # TODO(p2): call the matching API endpoint here and return the same shape.
                raise NotImplementedError("api mode arrives in Part 2")
            try:
                return fn(*args, **kwargs)
            except Exception as e:  # connection refused, timeout, bad path, unreadable file...
                return on_error(f"{type(e).__name__}: {e}")
        return inner
    return deco


def _path_filter(path):
    if not path:
        return None
    return models.Filter(must=[models.FieldCondition(key="path", match=models.MatchValue(value=path))])


def _scroll_all(path=None, fields=True):
    if not _client().collection_exists(COLLECTION):
        return []  # indexer has not run yet
    points, offset = [], None
    while True:
        batch, offset = _client().scroll(COLLECTION, scroll_filter=_path_filter(path), limit=256,
                                         offset=offset, with_payload=fields, with_vectors=False)
        points += batch
        if offset is None:
            return points


def _row(point) -> dict:
    return {"id": str(point.id), **(point.payload or {})}


@_index()
def get_status() -> dict:
    files = get_files()
    if error_of(files):
        return files
    return {"chunks": sum(f["chunks"] for f in files), "files": len(files),
            "target_path": str(TARGET_PATH), "qdrant_url": QDRANT_URL, "collection": COLLECTION,
            "embedding_model": EMBEDDING_MODEL, "ask_model": None, "code_model": None}


@_index()
def get_files() -> list[dict]:
    counts = Counter(p.payload.get("path") for p in _scroll_all(fields=["path"]) if p.payload)
    return [{"path": path, "chunks": n} for path, n in sorted(counts.items()) if path]


@_index()
def get_file(path: str) -> dict:
    full = (TARGET_PATH / path).resolve()
    if not full.is_relative_to(TARGET_PATH):
        raise ValueError(f"{path!r} is outside the target directory")
    content = full.read_text(encoding="utf-8", errors="replace")
    fields = ["start_line", "end_line", "symbol", "kind"]
    chunks = sorted((_row(p) for p in _scroll_all(path, fields)), key=lambda c: c.get("start_line") or 0)
    return {"path": path, "content": content, "lines": len(content.splitlines()),
            "bytes": full.stat().st_size, "chunks": chunks}


@_index(on_error=lambda msg: ({"error": msg}, None))
def get_chunks(path_filter=None, limit=50, cursor=None):
    if not _client().collection_exists(COLLECTION):
        return [], None
    points, next_cursor = _client().scroll(COLLECTION, scroll_filter=_path_filter(path_filter), limit=limit,
                                           offset=cursor, with_payload=True, with_vectors=False)
    return [_row(p) for p in points], next_cursor


@_index()
def get_events(n=50) -> list[dict]:
    if not EVENTS_LOG.exists():
        return []
    with EVENTS_LOG.open(encoding="utf-8", errors="replace") as f:
        last = deque(f, maxlen=n)
    events = []
    for line in reversed(last):  # newest first
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass  # a line the watcher is still writing
    return events


# --- Part 2–3 contracts (not implemented yet in either mode) ---

def retrieve(query: str, k: int) -> list[dict]:
    """Top-k chunks for `query`: get_chunks() rows plus a float `score`."""
    raise NotImplementedError("retrieve() arrives in Part 2")


def ask(question: str, k: int, session_id: str | None) -> dict:
    """{answer, session_id, resolved_facts, sources}; sources are retrieve() rows."""
    raise NotImplementedError("ask() arrives in Part 2")


def run_patch(intent: str, k: int, max_attempts: int) -> dict:
    """{status: "success"|"failed"|"rejected", attempts_used, rolled_back, reason, final_patch, attempts}."""
    raise NotImplementedError("run_patch() arrives in Part 3")
