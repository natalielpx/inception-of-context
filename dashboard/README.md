## Dashboard (`p1/dashboard`)

A Streamlit app at <http://localhost:8501>. It is the only dashboard in the project: Part 1 fills the
**Overview**, **Files** and **Qdrant Explorer** tabs, and Parts 2–3 switch on **Ask & Retrieve** and **Patch Loop**.

### Run it

```bash
make up                                   # or: docker compose --profile p1 up -d --build
docker compose logs -f dashboard
```

Locally, without Docker (Qdrant must be reachable):

```bash
cd p1/dashboard && pip install -r requirements.txt
QDRANT_URL=http://localhost:6333 TARGET_PATH=../../demo EVENTS_LOG=/tmp/ioc_events.jsonl streamlit run app.py
```

### Environment variables

| Variable | Default | Used in | Meaning |
|---|---|---|---|
| `IOC_SOURCE` | `direct` | both | Where the data comes from (see below). |
| `QDRANT_URL` | `http://qdrant:6333` | `direct` | Qdrant server. |
| `QDRANT_COLLECTION` | `ioc_chunks` | both | Collection the indexer writes to. |
| `TARGET_PATH` | `/workspace` | `direct` | Target project, mounted read-only. Payload `path`s are relative to it. |
| `EVENTS_LOG` | `/data/ioc_events.jsonl` | `direct` | JSON-lines file the watcher appends to. Must live outside the target. |
| `API_URL` | `http://api:8000` | `api` | IoC API (Part 2+). |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | both | Display only. |

### `IOC_SOURCE`

Every tab reads through `data.py` only. With `IOC_SOURCE=direct` (Part 1), `data.py` reads Qdrant, the
target files and the watcher's events log itself, so the dashboard needs nothing but Qdrant and the
indexer. With `IOC_SOURCE=api` (Parts 2–3), the same functions will call the FastAPI server and return
the same shapes, so the tabs never change. Until Part 2 lands, `api` mode shows "api mode arrives in
Part 2" in each tab. Leaving `direct` as the default keeps Part 1 working on its own.

### Contract with the indexer

- Each Qdrant point payload: `path, start_line, end_line, symbol, kind, hash, text` (`path` relative to the target).
- Each watcher change appends one line to `EVENTS_LOG`:
  `{"ts": "<ISO>", "type": "indexed|deleted|error", "path": "...", "chunks": 8, "added": 1, "updated": 2, "removed": 0, "detail": ""}`

### Compose service

```yaml
services:
  dashboard:
    build: ./p1/dashboard
    profiles: ["p1", "p2", "p3"]
    environment:
      IOC_SOURCE: direct
      QDRANT_URL: http://qdrant:6333
      QDRANT_COLLECTION: ioc_chunks
      TARGET_PATH: /workspace
      EVENTS_LOG: /data/ioc_events.jsonl
    volumes:
      - ${TARGET_DIR:-./demo}:/workspace:ro
      - ioc_data:/data
    depends_on:
      - qdrant
    ports:
      - "8501:8501"

volumes:
  ioc_data:
```

`qdrant` and the indexer service are defined in the same root `docker-compose.yml`; the indexer mounts
`ioc_data` at `/data` too so the dashboard can tail its events. Keep Qdrant's storage volume and
`ioc_data` out of Git.
