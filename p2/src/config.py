from qdrant_client import QdrantClient
import os
from ollama import AsyncClient

from sentence_transformers import SentenceTransformer

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")

qdrant_client = QdrantClient(url=QDRANT_URL, timeout=5)
COLLECTION = os.getenv("QDRANT_COLLECTION", "chunks")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

embedder = SentenceTransformer(EMBEDDING_MODEL)



OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
ollama = AsyncClient(host=OLLAMA_HOST, timeout=120)  # create once at module level
