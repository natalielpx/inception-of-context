"""UI code calls only these functions. `direct` mode reads Qdrant and the events log (Part 1).
`api` mode calls the IoC API (Parts 2-3) and must return the same shapes.

Every function is synchronous (the UI wraps it in `run.io_bound`). Failures come back as
{"error": "..."} instead of raising, except NotImplementedError for features not built yet.
"""
import functools, json, os
from collections import Counter, deque
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny, MatchValue

# ==== Configurations ====
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "chunks")
TARGET_PATH = Path(os.getenv("TARGET_PATH", "/workspace"))
LOG_FILE = Path(os.getenv("LOG_FILE", "/data/ioc_events.jsonl"))
API_URL = os.getenv("API_URL", "http://api:8000")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# ==== QDRANT CLIENT ====
_client: QdrantClient | None = None
def client() -> QdrantClient:
	global _client 
	if _client is None:
		_client = QdrantClient(url=QDRANT_URL, timeout=5)
	return _client

# Qdrant filter
# Recommendation: create keyword payload index on path in indexer:
# client.create_payload_index(COLLECTION, "path", models.PayloadSchemaType.KEYWORD)
def _path_filter(path: str | None) -> Filter | None:
	if not path:
		return None
	return Filter(must=[FieldCondition(key="path", match=MatchValue(value=path))])

# List points without query vector
def _scroll_all(flt=None, payload=True) -> list:
	points, cursor = [], None
	while True:
		page, cursor = client().scroll(COLLECTION, scroll_filter=flt, limit=256, offset=cursor, with_payload=payload)
		points += page
		if cursor is None:
			return points


# ==== DIRECT / API====
def source_mode() -> str:
	"""Swicth between direct (p1) and api (p2 & p3)"""
	mode = os.getenv("IOC_SOURCE", "direct").lower()
	if mode not in ("api", "direct"):
		raise ValueError(f"IOC_SOURCE must be 'api' or 'direct', got {mode!r}")
	return mode


# ==== CRASH SAFETY NET ====
def _index_fn(fn):
	"""Turns any backend failure into {"error": ...} instead of raising errors"""
	@functools.wraps(fn)
	def wrapper(*args, **kwargs):
		if source_mode() == "api":
			raise NotImplementedError("api mode arrives in Part 2")  # TODO(p2): call API_URL with httpx
		try:
			return fn(*args, **kwargs)
		# connection refused, missing collection, unreadable file...
		except Exception as e:
			return {"error": f"{type(e).__name__}: {e}"}
	return wrapper


# ==== P1 ====

# OVERVIEW: files indexed
@_index_fn
def get_files() -> list[dict]:
	counts = Counter(p.payload.get("path") for p in _scroll_all(payload=["path"]))
	return [{"path": path, "chunks": n} for path, n in sorted(counts.items())]

# OVERVIEW: target path, LLM models
@_index_fn
def get_status() -> dict:
	files = get_files()
	if isinstance(files, dict):
		return files	# failure
	return {			# success
		"chunks": client().count(COLLECTION, exact=True).count,
		"files": len(files),
		"target_path": str(TARGET_PATH),
		"qdrant_url": QDRANT_URL,
		"collection": COLLECTION,
		"embedding_model": EMBEDDING_MODEL,
		"ask_model": None,   # set by the API in Part 2
		"code_model": None,  # set by the API in Part 3
	}

# OVERVIEW: live activity
def get_events(n: int = 50) -> list[dict]:
	# API
	if source_mode() == "api":
		raise NotImplementedError("api mode arrives in Part 2")  # TODO(p2): GET /events (SSE)
	# Direct: read from file
	try:
		with LOG_FILE.open() as f:
			lines = deque(f, maxlen=n)
	except FileNotFoundError:
		return []
	except OSError as e:
		return {"error": str(e)}
	# Obtain events starting from newest
	events = []
	for line in reversed(lines):
		try:
			events.append(json.loads(line))
		except json.JSONDecodeError:
			pass  # watcher may be mid-write
	return events

# FILES
def _rel(p: str) -> str:
	"""Payload path -> path relative to the target (what the UI shows)."""
	try:
		return str(Path(p).resolve().relative_to(TARGET_PATH.resolve()))
	except ValueError:
		return p

@_index_fn
def get_file(path: str) -> dict:
	root = TARGET_PATH.resolve()
	full = (root / path).resolve()
	if not full.is_relative_to(root):
		return {"error": f"path outside target: {path}"}
	# match the chunk whether the indexer stored it relative or absolute
	flt = Filter(must=[FieldCondition(key="path", match=MatchAny(any=[path, str(full)]))])
	points = _scroll_all(flt, payload=["start_line", "end_line", "kind"])
	chunks = sorted(({"id": str(p.id), **p.payload} for p in points), key=lambda c: c["start_line"])
	if not full.is_file():
		return {"error": "file was deleted", "missing": True, "chunks": chunks}
	content = full.read_text(errors="replace")
	return {
		"path": path,
		"content": content,
		"lines": len(content.splitlines()),
		"bytes": full.stat().st_size,
		"chunks": chunks,
	}


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
