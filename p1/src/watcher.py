import threading
import time
from pathlib import Path
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

import files
from logger import log_event

class Watcher(FileSystemEventHandler):

	DELAY = 1.5
	WAIT = 0.3
	FULL_SYNC = 30 

	def __init__(self, indexer, target_root):
		self.indexer = indexer
		self.target_root = Path(target_root)
		self.pending = {}  # path -> last event time
		self.lock = threading.Lock()
		self.observer = None
		self.stopped = threading.Event()

	# Method defined by FileSystemEventHandler
	def on_any_event(self, e):
		# Collect paths the event affects
		if e.event_type == "moved":
			paths = [e.src_path, e.dest_path]
		elif e.event_type in ("created", "modified", "deleted"):
			paths = [e.src_path]
		else:
			return
		# Skip folder's own "modified" event when it's child changes
		if e.is_directory and e.event_type == "modified":
			return
		# Add path(s) to queue
		for path in paths:
			if files.to_be_indexed(str(self.target_root), path):
				log_event(e.event_type, path)
				self._add_to_queue(path)

	# time.monotonic() never jumps backwards if system clock changes
	def _add_to_queue(self, path):
		with self.lock:
			self.pending[path] = time.monotonic()

	def _nearest_existing_dir(self, path):
		p = Path(path)
		while not p.is_dir() and p != self.target_root:
			p = p.parent
		return p

	def _ready_paths(self):
		now = time.monotonic()
		ready = []
		with self.lock:
			for path, last_event in list(self.pending.items()):
				if now - last_event > self.DELAY:
					del self.pending[path]
					ready.append(path)
		return ready

	def _sync_ready_paths(self):
		for path in self._ready_paths():
			try:
				self.indexer.sync_path(path)
			except Exception:
				log_event("error", path, "error")

	def _periodic_sync(self):
		try:
			self.indexer.sync_path(str(self.target_root))
		except Exception:
			log_event("error", str(self.target_root), "error")

	def _run(self):
		last_full = time.monotonic()
		while not self.stopped.wait(self.WAIT):
			# Trigger synchronisation for changed files
			self._sync_ready_paths()
			# Trigger full synchronisation
			# if time.monotonic() - last_full >= self.FULL_SYNC:
			# 	self._periodic_sync()
			# 	last_full = time.monotonic()

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