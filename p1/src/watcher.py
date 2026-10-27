import os
import threading
import time
import logging
import sys
from pathlib import Path
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

from files import dir_to_be_indexed, path_to_be_watched


logging.basicConfig(
	level=os.environ.get("LOG_LEVEL", "INFO"),
	format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
	datefmt="%H:%M:%S",
	stream=sys.stdout,
)
logging.getLogger("watchdog").setLevel(logging.WARNING)

log = logging.getLogger("watch")

class Watcher(FileSystemEventHandler):

	DELAY = 1.5
	WAIT = 0.3
	FULL_SYNC = 30 

	def __init__(self, indexer, target_root, on_change=None):
		self.indexer = indexer
		self.target_root = Path(target_root)
		self.on_change = on_change or (lambda kind, path: None)
		self.pending = {}  # path -> last event time
		self.lock = threading.Lock()
		self.observer = None

	# time.monotonic() never jumps backwards if system clock changes
	def add_to_queue(self, path):
		with self.lock:
			requeued = path in self.pending
			self.pending[path] = time.monotonic()
		log.debug("%s %s", "requeued" if requeued else "queued", path)

	def on_any_event(self, e):

		if e.event_type == "moved":
			paths = [e.src_path, e.dest_path]
		elif e.event_type in ("created", "modified", "deleted"):
			paths = [e.src_path]
		else:
			return

		kind = "dir" if e.is_directory else "file"
		for path in paths:
			if e.is_directory:
				# skip a folder's own "modified" when a child changes
				wanted = e.event_type != "modified" and dir_to_be_indexed(self.target_root, path)
			else:
				wanted = path_to_be_watched(self.target_root, path)
			if wanted:
				log.info("event %-8s %-4s %s", e.event_type, kind, path)
				self.add_to_queue(path)
			else:
				log.debug("ignored %-8s %-4s %s", e.event_type, kind, path)

	def _nearest_existing_dir(self, path):
		p = Path(path)
		while not p.is_dir() and p != self.target_root:
			p = p.parent
		return p

	def _drain(self):
		last_full_sync = time.monotonic()
		while True:
			time.sleep(self.WAIT)
			now = time.monotonic()
			ready = []
			with self.lock:
				for path, last_event in list(self.pending.items()):
					if now - last_event > self.DELAY:
						del self.pending[path]
						ready.append(path)

			for path in ready:
				start = time.monotonic()
				try:
					with self.indexer.lock:
						if os.path.isfile(path):
							self.indexer.sync_file(path)
							action, target = "indexed", path
						else:
							target = self._nearest_existing_dir(path)
							self.indexer.sync_dir(str(target))
							action = "synced"
					ms = (time.monotonic() - start) * 1000
					if action == "indexed":
						log.info("indexed file %s (%.0f ms)", target, ms)
					else:
						log.info("synced dir %s/ after change to %s (%.0f ms)",
							target, path, ms)
					self.on_change(action, path)
				except Exception:
					log.exception("failed on %s", path)

			if now - last_full_sync >= self.FULL_SYNC:
				last_full_sync = now
				start = time.monotonic()
				try:
					with self.indexer.lock:
						self.indexer.sync_dir(str(self.target_root))
					# log.info("periodic full sync (%.0f ms)", (time.monotonic() - start) * 1000)
				except Exception:
					log.exception("periodic full sync failed")

	def start(self):
		threading.Thread(target=self._drain, daemon=True).start()
		self.observer = PollingObserver(timeout=1)
		self.observer.schedule(self, str(self.target_root), recursive=True)
		self.observer.start()
		log.info("watching %s (polling every 1s)", self.target_root)

	def stop(self):
		if self.observer:
			self.observer.stop()
			self.observer.join(timeout=5)
			log.info("watcher stopped")