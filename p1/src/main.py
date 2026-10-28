import os
import signal
import sys
import threading
from pathlib import Path
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from indexer import Indexer
from watcher import Watcher

def main() -> int:

	# Take in target repository
	if len(sys.argv) != 2:
		print(f"Usage: {sys.argv[0]} <target_path>", file=sys.stderr)
		return 1
	target = Path(sys.argv[1]).expanduser().resolve()
	if not target.is_dir():
		print(f"Target repository not found: {target}", file=sys.stderr)
		return 1

	# Create indexer and launch 1st synchronisation
	indexer = Indexer(
		client = QdrantClient(
			host=os.environ.get("QDRANT_HOST", "localhost"),
			port=int(os.environ.get("QDRANT_PORT", 6333))
		),
		embedder=SentenceTransformer("all-MiniLM-L6-v2"),
		target_root=target
	)
	indexer.sync_path(target)

	# Launch watcher and handle all changes
	watcher = Watcher(
		indexer,
		target
	)
	watcher.start()

	# Run until docker stop (SIGTERM) or Ctrl+C (SIGINT)
	stop = threading.Event()
	signal.signal(signal.SIGTERM, lambda *_: stop.set())
	signal.signal(signal.SIGINT, lambda *_: stop.set())
	stop.wait()
	watcher.stop()
	return 0

if __name__ == '__main__':
	sys.exit(main())