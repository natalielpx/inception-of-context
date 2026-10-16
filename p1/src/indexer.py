import os
import pprint
from dataclasses import asdict
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, FilterSelector, Filter, FieldCondition, MatchAny
from sentence_transformers import SentenceTransformer

from chunker import Chunker

class Indexer:

	COLLECTION = "chunks"
	EXCL_FILES = {"node_modules", "dist", "build", "venv", ".venv", ".pio", ".qdrant"}
	INCL_FILES = {".cpp", ".h", ".hpp", ".md", ".txt"}

	def __init__(self, client: QdrantClient, embedder: SentenceTransformer, target_root: Path):
		self.client = client
		self.embedder = embedder
		self.target_root = target_root
		self.chunker = Chunker()
		if not self.client.collection_exists(self.COLLECTION):
			self.client.create_collection(
				collection_name=self.COLLECTION,
				vectors_config=VectorParams(size=self.embedder.get_sentence_embedding_dimension(), distance=Distance.COSINE),
			)
		self.hashmap = self.load_hashmap()

	def load_hashmap(self) -> dict:
		hashmap = {}
		offset = None
		while True:
			points, offset = self.client.scroll(
				collection_name=self.COLLECTION,
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

	def dir_to_be_included(self, filepath: str) -> bool:
		if filepath in self.EXCL_FILES:
			return False
		if filepath.startswith("."):
			return False
		return True

	def file_to_be_included(self, filepath: str) -> bool:
		if os.path.splitext(filepath)[1] in self.INCL_FILES:
			return True
		return False
	
	def index_file(self, filepath: str):

		# Non-existent files
		if not os.path.isfile(filepath):
			del self.hashmap[filepath]
			return
		# Not to be indexed files
		if not self.file_to_be_included(filepath):
			return

		# Obtain chunks
		chunks = self.chunker.chunk(filepath)
		new_hashes = {c.point_id: c.hash_value for c in chunks}
		old_hashes = self.hashmap.get(filepath, {})

		# Delete stale chunks via point_id
		stale = list(old_hashes.keys() - new_hashes.keys())
		if stale:
			self.client.delete(
				collection_name=self.COLLECTION,
				points_selector=[p_id for p_id in stale]
			)

		# Update changed chunks (determined via changed hash value)
		changed = [c for c in chunks if old_hashes.get(c.point_id) != c.hash_value]
		if changed:
			self.client.upload_collection(
				collection_name=self.COLLECTION,
				ids=[c.point_id for c in changed],
				vectors=self.embedder.encode([c.text for c in changed]).tolist(),
				payload=[asdict(c) for c in changed],
				batch_size=64,
				wait=True,
			)

		# Update dict of target file in hashmap
		self.hashmap[filepath] = new_hashes

	def index_all(self):

		# Walk through target directory and obtain target files
		files = []
		for dirpath, dirnames, filenames in os.walk(self.target_root):
			dirnames[:] = [d for d in dirnames if self.dir_to_be_included(d) ]
			filenames = [f for f in filenames if self.file_to_be_included(f)]
			files.extend([os.path.join(dirpath, f) for f in filenames])
		pprint.pp(files)

		# Delete chunks of files that no longer exist
		self.client.delete(
			collection_name=self.COLLECTION,
			points_selector=FilterSelector(
				filter=Filter(must_not=[FieldCondition(key="path", match=MatchAny(any=files))])
			),
			wait=True,
		)

		# Prune hashmap of deleted files
		for deleted in self.hashmap.keys() - set(files):
			del self.hashmap[deleted]

		# (Re-)index all target files
		for f in files:
			self.index_file(f)
