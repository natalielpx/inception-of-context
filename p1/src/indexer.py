import os, threading
from dataclasses import asdict
from fastembed import TextEmbedding
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny

import vectordb
from chunker import Chunker
from files import is_included_dir, is_included_file, collect_files


class SyncError(Exception):
	def __init__(self, errors: dict[str, Exception]):
		self.errors = errors
		super().__init__(f"{len(errors)} file(s) failed: " + ", ".join(errors))


class Indexer:

	def __init__(self,
	    client: QdrantClient,
		embedder: TextEmbedding,
		target_root: Path,
	):
		self.client = client
		self.embedder = embedder
		self.target_root = target_root
		self.chunker = Chunker()
		vectordb.ensure_collection()
		self.collection = vectordb.COLLECTION
		self.hashmap = self._load_hashmap()
		self.lock = threading.RLock()

	def _load_hashmap(self) -> dict:
		hashmap = {}
		offset = None
		while True:
			points, offset = self.client.scroll(
				collection_name=self.collection,
				limit=256,
				offset=offset,
				with_payload=["path", "hash_value"]
			)
			for p in points:
				path = p.payload["path"]
				hashmap.setdefault(path, {})
				hashmap[path][p.id] = p.payload["hash_value"]
			if offset is None:
				break
		return hashmap

	def _rm_chunks_by_paths(self, files: list[str]):
		filter = Filter(must=[FieldCondition(key="path", match=MatchAny(any=files))])
		self.client.delete(
			collection_name=self.collection,
			points_selector=filter,
			wait=True,
		)
		for f in files:
			self.hashmap.pop(f, None)

	def _rm_chunks_by_point_ids(self, p_ids: list[str]):
		if p_ids:
			self.client.delete(
				collection_name=self.collection,
				points_selector=[p_id for p_id in p_ids],
				wait=True,
			)

	def _upsert_chunks(self, chunks):
		if chunks:
			self.client.upload_collection(
				collection_name=self.collection,
				ids=[c.point_id for c in chunks],
				vectors=self.embedder.passage_embed([c.text for c in chunks]),
				payload=[asdict(c) for c in chunks],
				batch_size=64,
				wait=True,
			)
	
	def _sync_file(self, filepath: str):

		if not os.path.isfile(filepath) or not is_included_file(self.target_root, filepath):
			if filepath in self.hashmap:
				self._rm_chunks_by_paths([filepath])
			return

		chunks = self.chunker.chunk(filepath)
		new_hashes = {c.point_id: c.hash_value for c in chunks}
		old_hashes = self.hashmap.get(filepath, {})

		stale = list(old_hashes.keys() - new_hashes.keys())
		self._rm_chunks_by_point_ids(stale)

		changed = [c for c in chunks if old_hashes.get(c.point_id) != c.hash_value]
		self._upsert_chunks(changed)

		self.hashmap[filepath] = new_hashes

	def _sync_dir(self, dirpath: str):

		# Obtain previously indexed files under target directory
		prefix = str(dirpath).rstrip("/") + "/"
		indexed_files = [p for p in self.hashmap if p.startswith(prefix)]

		# Non-existent, not to be indexed, deleted
		if not os.path.isdir(dirpath) or not is_included_dir(self.target_root, dirpath):
			if indexed_files:
				self._rm_chunks_by_paths(indexed_files)
			return

		# Walk through target directory and obtain target files
		files = collect_files(self.target_root, dirpath)

		# Delete chunks of files that no longer exist
		gone = list(set(indexed_files) - set(files))
		if gone:
			self._rm_chunks_by_paths(gone)

		# (Re-)index all target files
		errors = {}
		for f in files:
			try:
				self._sync_file(f)
			except Exception as e:
				errors[f] = e
		if errors:
			raise SyncError(errors)

	def sync_path(self, path: str):
		with self.lock:
			if os.path.isdir(path):
				self._sync_dir(path)
			elif os.path.isfile(path):
				self._sync_file(path)
			else:
				self._rm_chunks_by_paths([path])