from fastapi import FastAPI
from indexer import router as indexer_router
from events import router as events_router
from rag import router as rag_router
from retriever import router as retriever_router

app = FastAPI()

app.include_router(indexer_router)
app.include_router(events_router)
app.include_router(rag_router)
app.include_router(retriever_router)