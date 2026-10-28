from fastapi import APIRouter
from config import OLLAMA_MODEL, ollama
from retriever import retrieve_context
from fastapi.concurrency import run_in_threadpool

router = APIRouter()

class Prompt:
    def __init__(self, question: str, context: dict):
        self.question = question
        self.context = context

    class File:
        def __init__(self, path: str, start_line: int, end_line: int, content: str):
            self.path = path
            self.start_line = start_line
            self.end_line = end_line
            self.content = content

        def as_prompt(self) -> str:
            return f"File: {self.path}, Lines: {self.start_line}-{self.end_line}\n\nContent:\n{self.content}\n"

    def generate_prompt(self) -> str:
        context_str = "\n".join(self.File(hit["path"], hit["start_line"], hit["end_line"], hit["text"]).as_prompt() for hit in self.context.get("hits", []))
        return f"Context:\n{context_str}\n\nQuestion: {self.question}\nAnswer:"

@router.post("/ask")
async def ask_question(query: str, k: int = 5):
    # Placeholder for question answering logic
    context = await run_in_threadpool(retrieve_context, query, k)
    prompt = Prompt(query, context)
    generated_prompt = prompt.generate_prompt()

    res = await ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that answers questions based on the provided context."
            },
            {
                "role": "user",
                "content": generated_prompt
            }
        ]
    )

    ans = res["message"]["content"]
    return {
        "question": query,
        "answer": ans,
        "hits": context.get("hits", [])
    }
