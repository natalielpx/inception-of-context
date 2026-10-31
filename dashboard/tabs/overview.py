"""Overview: general information, indexed files, live activity feed"""

from nicegui import ui
from datetime import datetime

from . import failed

BADGE = {
    "created":  "positive",   # green: new file indexed
    "modified": "primary",    # blue: file changed, reindexed
    "moved":    "purple",     # purple: renamed / relocated
    "deleted":  "orange",     # orange: chunks removed
    "error":    "negative",   # red: something failed
}

def _row(label: str, value) -> None:
	with ui.row().classes("w-full items-center no-wrap gap-4 py-1 border-b border-slate-700"):
		ui.label(label).classes("w-40 shrink-0 text-xs uppercase text-grey-5")
		ui.label(str(value)).classes("truncate")

def build():

	# ==== GENERAL INFORMATION ====

	@ui.refreshable
	def info(status: dict | None):
		if failed(status):
			ui.label(f"Index unavailable: {status['error']}").classes("text-negative")
			return
		s = status or {}
		with ui.column().classes("w-full gap-0"):
			_row("chunks indexed", s.get("chunks", "…"))
			_row("files indexed", s.get("files", "…"))
			_row("target project", s.get("target_path", "…"))
			_row("embedding model", s.get("embedding_model", "…"))
			_row("ask model", s.get("ask_model") or "— (Part 2)")
			_row("code model", s.get("code_model") or "— (Part 3)")

	with ui.card().classes("w-full bg-slate-800"):
		ui.label("GENERAL INFORMATION").classes("text-xs text-grey-5")
		info(None)

	# ==== INDEXED FILES ====

	@ui.refreshable
	def file_list(files: list | None):
		if not files or failed(files):
			ui.label("No indexed files.").classes("text-grey-6")
			return
		top = max(f["chunks"] for f in files)
		for f in files:
			with ui.row().classes("w-full items-center no-wrap gap-4"):
				ui.label(f["path"]).classes("w-1/2 truncate")
				ui.linear_progress(f["chunks"] / top, show_value=False, size="4px").classes("w-1/3")
				ui.label(f"{f['chunks']} chunks").classes("ml-auto text-grey-5")

	with ui.card().classes("w-full bg-slate-800 mt-4"):
		ui.label("INDEXED FILES").classes("text-xs text-grey-5")
		file_list(None)

	# ==== LIVE ACTIVITY ====
	
	@ui.refreshable
	def activity(events: list):
		if not events:
			ui.label("No file activity yet. Edit a file in the target to see live updates.").classes("text-grey-6")
		for e in events:
			kind = "error" if e.get("level", 0) >= 40 else e.get("kind", "?")
			with ui.row().classes("w-full items-center no-wrap gap-3"):
				ui.label(datetime.fromtimestamp(e["ts"]).strftime("%H:%M:%S")).classes("text-grey-5")
				ui.badge(kind, color=BADGE.get(kind, "grey"))
				ui.label(e.get("path", "").removeprefix("/workspace/")).classes("truncate")
				if "chunks" in e:
					ui.label(f"{e['chunks']} chunks").classes("ml-auto text-grey-5")

	with ui.card().classes("w-full bg-slate-800 mt-4"):
		ui.label("LIVE ACTIVITY").classes("text-xs text-grey-5")
		activity([])

	# ==== UPDATE HOOK ====

	async def update(snap: dict):
		info.refresh(snap["status"])
		file_list.refresh(snap["files"])
		activity.refresh(snap["events"])
		for e in snap["new"][:3]:
			print(e)
			ui.notify(
				f"{e.get('type')}: {e.get('path')}",
				type="negative" if e.get("type") == "error" else "info",
				position="bottom-right",
				timeout=2000
			)

	return update
