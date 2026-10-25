import os
import threading
from dataclasses import asdict
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, FilterSelector, Filter, FieldCondition, MatchAny
from sentence_transformers import SentenceTransformer

from chunker import Chunker
from files import dir_to_be_indexed, file_to_be_indexed, files_to_be_indexed


def print_chunks(chunks, show_text=True):
    chunks = sorted(chunks, key=lambda c: (c.path, c.start_line, c.end_line))
    prev_path, prev_end = None, 0
    for c in chunks:
        if c.path != prev_path:
            print(f"\n{'#' * 80}\n# {c.path}\n{'#' * 80}")
            prev_path, prev_end = c.path, 0
        if c.start_line <= prev_end:
            print(f"!! OVERLAP: starts at {c.start_line}, previous ended at {prev_end}")
        elif c.start_line > prev_end + 1:
            print(f"   (gap: lines {prev_end + 1}-{c.start_line - 1} not in any chunk)")
        prev_end = max(prev_end, c.end_line)

        print(f"\n=== {c.chunk_id}  [{c.kind}]  {c.hash_value[:8]} ===")
        if show_text:
            for i, line in enumerate(c.text.splitlines() or [""], start=c.start_line):
                print(f"{i:5} | {line}")
    print(f"\n{len(chunks)} chunks total")

class Indexer:

	COLLECTION = "chunks"

	def __init__(self, client: QdrantClient, embedder: SentenceTransformer, target_root: str):
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
		self.lock = threading.Lock()

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

	def rm_chunks_by_path(self, files: list[str]):
		self.client.delete(
			collection_name=self.COLLECTION,
			points_selector=FilterSelector(
				filter=Filter(must=[FieldCondition(key="path", match=MatchAny(any=files))])
			),
			wait=True,
		)
		for f in files:
			self.hashmap.pop(f, None)
	
	def sync_file(self, filepath: str):

		# Non-existent or not to be indexed
		if not os.path.isfile(filepath) or not file_to_be_indexed(self.target_root, filepath):
			if filepath in self.hashmap:
				self.rm_chunks_by_path([filepath])
			return

		# Obtain chunks
		try:
			chunks = self.chunker.chunk(filepath)
			# print_chunks(chunks)
		except:
			return
		new_hashes = {c.point_id: c.hash_value for c in chunks}
		old_hashes = self.hashmap.get(filepath, {})

		# Delete stale chunks via point_id
		stale = list(old_hashes.keys() - new_hashes.keys())
		if stale:
			self.client.delete(
				collection_name=self.COLLECTION,
				points_selector=[p_id for p_id in stale],
				wait=True,
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

	def sync_dir(self, dirpath:str):

		# Obtain previously indexed files under target directory
		prefix = str(dirpath).rstrip("/") + "/"
		indexed_files = [p for p in self.hashmap if p.startswith(prefix)]

		# Non-existent, not to be indexed, or deleted
		if not os.path.isdir(dirpath) or not dir_to_be_indexed(self.target_root, dirpath):
			if indexed_files:
				self.rm_chunks_by_path(indexed_files)
			return

		# Walk through target directory and obtain target files
		files = files_to_be_indexed(self.target_root, dirpath)

		# Delete chunks of files that no longer exist
		gone = list(set(indexed_files) - set(files))
		if gone:
			self.rm_chunks_by_path(gone)

		# (Re-)index all target files
		for f in files:
			try:
				self.sync_file(f)
			except Exception as e:
				print(f"[index] {f}: {e}")
