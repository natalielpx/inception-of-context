import os
from qdrant_client import QdrantClient, models

import embedder


QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION = os.getenv("QDRANT_COLLECTION", "chunks")

_client: QdrantClient | None = None


def client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(
                host=QDRANT_HOST,
                port=QDRANT_PORT
            )
    return _client


def ensure_collection() -> None:
    c = client()
    if not c.collection_exists(COLLECTION):
        c.create_collection(
            collection_name=COLLECTION,
            vectors_config=models.VectorParams(
                    size=embedder.get_dimension(),
                    distance=models.Distance.COSINE
                ),
        )
