import logging
import sys
import json, os, threading, time
from pathlib import Path

LOG_FILE = Path(os.environ.get("LOG_FILE", "/ioc/events/events.jsonl"))
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
_LEVELS: dict[str, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}

logging.basicConfig(
	level=os.environ.get("LOG_LEVEL", "INFO"),
	format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
	datefmt="%H:%M:%S",
	stream=sys.stdout
)
logging.getLogger("watchdog").setLevel(logging.WARNING)
log = logging.getLogger("watcher")

_log_lock = threading.Lock()

def log_event(kind: str, path: str, level: str = "info", **fields) -> None:
	lvl = _LEVELS[level]
	# Append to the dashboard’s JSONL feed
	try:
		with _log_lock, LOG_FILE.open("a", encoding="utf-8") as f:
			f.write(json.dumps({
				**fields,
				"ts": time.time(),
				"level": lvl,
				"kind": kind,
				"path": path
			}, ensure_ascii=False) + "\n")
	except OSError:
		log.warning("Could not write event to %s", LOG_FILE, exc_info=True)
	# Write into stdout
	log.log(lvl, "%s %s %s", kind, path, fields)