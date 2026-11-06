import threading
import time
from pathlib import Path
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

from files import is_included_dir, is_included_file
from indexer import Indexer, SyncError
from logger import log_event

EVENTS_IGNORED = ["opened", "closed_no_write"]


class Watcher(FileSystemEventHandler):

	DELAY = 1.5
	WAIT = 0.3
	FULL_SYNC = 30 


	def __init__(self, indexer: Indexer, target_root):
		self.indexer = indexer
		self.target_root = Path(target_root)
		self.pending = {}  # path -> last event time
		self.lock = threading.Lock()
		self.observer = None
		self.stopped = threading.Event()


	# Method defined by FileSystemEventHandler
	def on_any_event(self, e):
		# Ignore unwanted events
		if e.event_type in EVENTS_IGNORED:
			return
		if e.is_directory and e.event_type == "modified": # children report themselves
			return
		# Collect paths the event affects
		paths = [e.src_path]
		if e.event_type == "moved":
			paths.append(e.dest_path)
		# Add wanted path(s) to queue
		for path in paths:
			if e.is_directory and not is_included_dir(self.target_root, path):
				continue
			elif not is_included_file(self.target_root, path):
				continue
			log_event(e.event_type, path)
			with self.lock:
				self.pending[path] = time.monotonic()


	def _ready_paths(self):
		now = time.monotonic()
		ready = []
		with self.lock:
			for path, last_event in list(self.pending.items()):
				if now - last_event > self.DELAY:
					del self.pending[path]
					ready.append(path)
		return ready


	def _sync_path(self, path: str):
		try:
			self.indexer.sync_path(path)
		except SyncError as e:
			for f, err in e.errors.items():
				log_event("error", f, "error", {"msg": f"{type(err).__name__}: {err}"})
		except Exception as e:
			log_event("error", path, "error", {"msg": f"{type(e).__name__}: {e}"})


	def _sync_ready_paths(self):
		for path in self._ready_paths():
			self._sync_path(path)


	def _run(self):
		last_full = time.monotonic()
		while not self.stopped.wait(self.WAIT):
			# Trigger synchronisation for changed files
			self._sync_ready_paths()
			# Trigger full synchronisation
			if time.monotonic() - last_full >= self.FULL_SYNC:
				self._sync_path(str(self.target_root))
				last_full = time.monotonic()


	def start(self):
		threading.Thread(target=self._run, daemon=True).start()
		self.observer = PollingObserver(timeout=1)
		self.observer.schedule(self, str(self.target_root), recursive=True)
		self.observer.start()


	def stop(self):
		self.stopped.set()
		if self.observer:
			self.observer.stop()
			self.observer.join(timeout=5)
