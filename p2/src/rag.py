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


PATCH_SYSTEM = """
You are a code-patching engine.
Return ONLY a JSON object of this exact shape:
{"summary": "<one line>", "files": [{"path": "<relative path>", "op": "create|modify|delete", "content": "<complete file after the change>"}]}
Rules: content is the FULL file, never a diff. No markdown, no prose, no stubs.
"""

@router.post("/patch")
async def patch_loop(query: str, k: int = 5, max_attempts: int = 3):
	context = await run_in_threadpool(retrieve_context, query, k)
	prompt = Prompt(query, context)
	attempts, error_log, final = [], None, None

	for n in range(1, max_attempts + 1):
		att = {
			"n": n,
			"stage": "generated",
			"ok": False,
			"error": None,
			"raw": None,
			"patch": None
		}
		attempts.append(att)
		try:
			res = await ollama.chat(
				model=OLLAMA_MODEL,
				format="json",
				options={"temperature": 0.2},
				messages=[
					{"role": "system", "content": PATCH_SYSTEM},
					{"role": "user", "content": prompt.generate_patch_prompt(error_log)},
				],
			)
			att["raw"] = res["message"]["content"]

			print(att["raw"])

			# att["patch"] = parse_patch(att["raw"]); att["stage"] = "parsed"

			# problems = sanity_check(att["patch"]); att["stage"] = "sanity"
			# if problems:
			# 	raise ValueError("; ".join(problems))

			# # TODO next: snapshot -> apply (*.ioc.tmp + os.replace) -> validate
			# att["ok"] = True
			# final = att["patch"]
			# break
		except Exception as e:
			att["error"] = f"{type(e).__name__}: {e}"
			error_log = att["error"]               # fed back on the next attempt

	if final:
		status = "success"
	else:
		status = "failed"
	hits = [{"path": h["path"], "start_line": h["start_line"]} for h in context.get("hits", [])]
	return {
		"intent": query,
		"status": status,
		"attempts": attempts,
		"final_patch": final,
		"hits": hits,
	}