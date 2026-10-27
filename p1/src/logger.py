import json, os
from datetime import datetime, timezone

EVENTS_LOG = os.getenv("EVENTS_LOG", "/data/ioc_events.jsonl")


def log_event(type_, path, chunks=0, added=0, updated=0, removed=0, detail=""):
    event = {"ts": datetime.now(timezone.utc).isoformat(), "type": type_, "path": path,
             "chunks": chunks, "added": added, "updated": updated, "removed": removed, "detail": detail}
    os.makedirs(os.path.dirname(EVENTS_LOG), exist_ok=True)
    with open(EVENTS_LOG, "a") as f:
        f.write(json.dumps(event) + "\n")
  