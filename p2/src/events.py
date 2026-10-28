from fastapi import APIRouter
from fastapi.sse import EventSourceResponse
import time

router = APIRouter()

@router.get("/events", response_class=EventSourceResponse)
async def retrieve_context():
    yield {
        "event": "message", "context": f"This is the record of the file change."
    }