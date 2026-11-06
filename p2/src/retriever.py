from fastapi import APIRouter
from config import qdrant_client, COLLECTION, embedder
from fastapi.concurrency import run_in_threadpool

router = APIRouter()

def retrieve_context(query: str, k: int = 5) -> dict:
    hits = qdrant_client.query_points(
        collection_name=COLLECTION,
        query=embedder.encode(query).tolist(),
        limit=k,
        with_payload=True
    )
    return {"query": query, "hits": [
        {
            "id": hit.id,
            "text": hit.payload.get("text", ""),
            "path": hit.payload.get("path", ""),
            "start_line": hit.payload.get("start_line", None),
            "end_line": hit.payload.get("end_line", None),
            "score": hit.score
        } for hit in hits.points
    ]}

@router.post("/context")
async def get_context(query: str, k: int = 5):
    context = await run_in_threadpool(retrieve_context, query, k)
    return context
