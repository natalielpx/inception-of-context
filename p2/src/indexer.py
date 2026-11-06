from fastapi import APIRouter
import httpx
from config import qdrant_client, COLLECTION


router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "healthy"}

@router.get("/status")
async def status():
    try:
        is_up = qdrant_client.get_collection(collection_name=COLLECTION).status == "green"
        return {"status": "running" if is_up else "stopped"}
    except httpx.HTTPError:
        return {"status": "stopped"}

@router.get("/files")
async def list_files():
    files = set()
    offset = None
    while True:
        pts, offset = qdrant_client.scroll(
            collection_name=COLLECTION,
            limit=256,
            offset=offset,
            with_payload=["path"]
        )
        for p in pts:
            files.add(p.payload.get("path"))
        if offset is None:
            break
    return {"files": list(files)}

def get_chunks(key: str = None) -> list:
    chunks = {}
    while True:
        pts, offset = qdrant_client.scroll(
            collection_name=COLLECTION,
            limit=256,
            offset=None,
            with_payload=["path", "text"]
        )
        for p in pts:
            path = p.payload.get("path")
            text = p.payload.get("text")
            if key is None or path == key:
                if path not in chunks:
                    chunks[path] = []
                chunks[path].append(text)
        if offset is None:
            break
    return chunks.get(key, []) if key else chunks

@router.get("/file")
async def get_file(path: str):
    return {"path": path, "chunks": get_chunks(path)}

@router.post("/chunks")
async def upload_chunk():
    # Placeholder for chunk upload logic
    return {"result": get_chunks()}