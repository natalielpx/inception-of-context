"""Files: on-disk files in chunks"""

from nicegui import ui

import data
from . import code, failed, fetch, language
from styles import TRUNC

def build():
	state = {"path": None}

	@ui.refreshable
	def file_list(files: list | None):
		if not files or failed(files):
			return
		for f in files:
			with ui.row().classes("w-full no-wrap cursor-pointer px-2 py-1 rounded").on("click", lambda p=f["path"]: open_file(p)) as row:
				if f["path"] == state["path"]:
					row.classes("bg-slate-700")
				ui.label(f["path"]).classes(TRUNC)
				ui.label(str(f["chunks"])).classes("ml-auto text-grey-5")

	@ui.refreshable
	def view(file: dict | None):
		if file is None:
			ui.label("Select a file.").classes("text-grey-6")
			return
		if failed(file):
			ui.label(file["error"]).classes("text-warning" if file.get("missing") else "text-negative")
			return
		with ui.row().classes("w-full items-baseline gap-3"):
			ui.label(file["path"]).classes("text-base")
			ui.space()
			stats = (
				f"{file['lines']} lines",
				f"{file['bytes']} bytes",
				f"{len(file['chunks'])} chunks",
			)
			ui.label(" · ".join(stats)).classes("text-grey-5")
		lines, lang = file["content"].splitlines(), language(file["path"])
		for n, c in enumerate(file["chunks"], 1):
			parts = (
				f"▶ chunk #{n}",
				f"lines {c['start_line']}-{c['end_line']}",
				c.get("kind", ""),
			)
			ui.label(" · ".join(p for p in parts if p)).classes("text-primary mt-2")
			code("\n".join(lines[c["start_line"] - 1:c["end_line"]]), lang)

	async def open_file(path: str):
		state["path"] = path
		file_list.refresh()
		view.refresh(await fetch(data.get_file, path))

	with ui.splitter(value=25).classes("w-full") as split:
		with split.before:
			file_list(None)
		with split.after:
			with ui.column().classes("w-full pl-4"):
				view(None)

	# ==== UPDATE HOOK ====

	async def update(snap: dict):
		file_list.refresh(snap["files"])
		# file is open, and at least one new event is about said file
		if state["path"] and any(data._rel(e.get("path", "")) == state["path"] for e in snap["new"]):
			await open_file(state["path"])

	return update