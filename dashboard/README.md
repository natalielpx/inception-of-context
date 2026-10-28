## Dashboard (`p1/dashboard`)

A NiceGUI app on <http://localhost:8080> with five tabs: **Overview · Files · Ask & Retrieve · Patch Loop · Qdrant Explorer**. In Part 1 only Overview, Files and Qdrant Explorer are live; the other two show their final forms, disabled.

### Run

```bash
docker compose up --build dashboard
open http://localhost:8080
```

Without Docker (Qdrant running on localhost):

```bash
pip install -r p1/dashboard/requirements.txt
cd p1/dashboard && QDRANT_URL=http://localhost:6333 TARGET_PATH=../../demo LOG_FILE=/tmp/ioc_events.jsonl python main.py
```

### Environment variables

| Variable | Default | Used in |
|---|---|---|
| `IOC_SOURCE` | `direct` | where data comes from (see below) |
| `QDRANT_URL` | `http://qdrant:6333` | `direct` |
| `QDRANT_COLLECTION` | `chunks` | both |
| `TARGET_PATH` | `/workspace` | `direct` (mounted read-only) |
| `LOG_FILE` | `/data/ioc_events.jsonl` | `direct`; must be **outside** the target, or the watcher sees its own writes |
| `API_URL` | `http://api:8000` | `api` (Part 2+) |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | display only |

### `IOC_SOURCE`

All data access goes through `data.py`; the UI never touches Qdrant, the disk or the API itself.

- `direct` (Part 1): reads Qdrant, the target files and the watcher's events log. Needs only Qdrant and the watcher, so Part 1 keeps working on its own even after Parts 2–3 exist.
- `api` (Parts 2–3): the same functions call the IoC FastAPI server and return the same shapes. Until Part 2 is built, they raise `NotImplementedError`.

### Contract with the indexer

Each Qdrant point payload: `path, start_line, end_line, symbol, kind, hash, text`.
The watcher appends one JSON line per change to `LOG_FILE`:

```json
{"ts": "2026-10-21T20:45:12+00:00", "type": "indexed", "path": "notes/service.py", "chunks": 8, "added": 1, "updated": 2, "removed": 0, "detail": ""}
```

`type` is `indexed`, `deleted` or `error`. The dashboard polls the log every second and refreshes the activity feed, cards, file list and the open file when it changes.
