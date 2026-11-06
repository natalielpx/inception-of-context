import logging, os, signal, sys, threading
from pathlib import Path

import embedder, vectordb
from indexer import Indexer
from watcher import Watcher


TARGET_PATH = os.environ.get("TARGET_PATH", "/workspace")

log = logging.getLogger("ioc")


def main() -> int:

	target = Path(TARGET_PATH).resolve()
	try:
		next(target.iterdir(), None)
	except NotADirectoryError:
		log.error("TARGET_PATH is not a directory: %s", target); return 1
	except OSError as err:
		log.error("cannot open TARGET_PATH %s: %s", target, err.strerror); return 1

	indexer = Indexer(
		client=vectordb.client(),
		embedder=embedder.model(),
		target_root=target
	)
	indexer.sync_path(target)

	watcher = Watcher(
		indexer=indexer,
		target_root=target
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