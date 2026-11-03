import os, signal, sys, threading
from pathlib import Path
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from indexer import Indexer
from watcher import Watcher

def main() -> int:

	target = Path(os.environ.get("TARGET_PATH", "/workspace")).resolve()
	try:
		next(target.iterdir(), None)
	except NotADirectoryError:
		sys.exit(f"TARGET_PATH is not a directory: {target}")
	except OSError as err:
		sys.exit(f"cannot open TARGET_PATH {target}: {err.strerror}")

	indexer = Indexer(
		client = QdrantClient(
			host=os.environ.get("QDRANT_HOST", "localhost"),
			port=int(os.environ.get("QDRANT_PORT", 6333))
		),
		embedder=SentenceTransformer("all-MiniLM-L6-v2"),
		target_root=target
	)
	indexer.sync_path(target)

	watcher = Watcher(
		indexer,
		target
	)
	watcher.start()

	stop = threading.Event()
	signal.signal(signal.SIGTERM, lambda *_: stop.set())
	signal.signal(signal.SIGINT, lambda *_: stop.set())
	stop.wait()
	watcher.stop()
	return 0

if __name__ == '__main__':
	sys.exit(main())