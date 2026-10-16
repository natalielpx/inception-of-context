import os
import sys
from pathlib import Path
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from indexer import Indexer


def main() -> int:
	"""p1"""

	indexer = Indexer(
		client = QdrantClient(
			host=os.environ.get("QDRANT_HOST", "localhost"),
			port=int(os.environ.get("QDRANT_PORT", 6333))
		),
		embedder=SentenceTransformer("all-MiniLM-L6-v2"),
		target_root=Path(os.environ.get("IOC_TARGET", "/workspace"))
	)
	indexer.index_all()
	
	return 0

if __name__ == '__main__':
	sys.exit(main())