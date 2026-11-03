"""Overview: general information, indexed files, live activity feed"""

from nicegui import ui
from datetime import datetime

from . import failed
from styles import TRUNC, W_2, W_3, ROW, TEXT, CARD

BADGE = {
    "created":  "positive",   # green: new file indexed
    "modified": "primary",    # blue: file changed, reindexed
    "moved":    "purple",     # purple: renamed / relocated
    "deleted":  "orange",     # orange: chunks removed
    "error":    "negative",   # red: something failed
}


def build():

	# ==== GENERAL INFORMATION ====

	def _row(label: str, value) -> None:
		with ui.row().classes(ROW):
			ui.label(label).classes("w-40 shrink-0" + TEXT)
			ui.label(str(value)).classes(TRUNC)

	@ui.refreshable
	def info(status: dict | None):
		if failed(status):
			ui.label(f"{status['error']}").classes("text-negative")
			return
		s = status or {}
		with ui.column().classes("w-full gap-0"):
			_row("chunks indexed",	s.get("chunks", "-"))
			_row("files indexed",	s.get("files", "-"))
			_row("target project",	s.get("target_path", "-"))
			_row("embedding model",	s.get("embedding_model" or "-"))
			_row("ask model",		s.get("ask_model") or "-")
			_row("code model",		s.get("code_model") or "-")

	with ui.card().classes(CARD):
		ui.label("GENERAL INFORMATION").classes(TEXT)
		info(None)

	# ==== INDEXED FILES ====

	@ui.refreshable
	def file_list(files: list | None):
		if not files or failed(files):
			ui.label("No indexed files.").classes("text-grey-6")
			return
		top = max((f["chunks"] for f in files), default=0) or 1
		for f in files:
			ratio = f["chunks"] / top
			with ui.row().classes(ROW):
				ui.label(f["path"]).classes(W_2 + TRUNC)
				ui.linear_progress(ratio, show_value=False, size="4px").classes(W_3)
				ui.label(f"{f['chunks']} chunks").classes("ml-auto text-grey-5")

	with ui.card().classes(CARD):
		ui.label("INDEXED FILES").classes(TEXT)
		file_list(None)

	# ==== LIVE ACTIVITY ====
	
	@ui.refreshable
	def activity(events: list):
		if not events:
			ui.label("No file activity yet.").classes("text-grey-6")
		for e in events:
			kind = "error" if e.get("level", 0) >= 40 else e.get("kind", "?")
			time = datetime.fromtimestamp(e["ts"]).strftime("%H:%M:%S")
			with ui.row().classes(ROW):
				ui.label(time).classes("text-grey-5")
				ui.badge(kind, color=BADGE.get(kind, "grey"))
				ui.label(e.get("path", "").removeprefix("/workspace/")).classes(TRUNC)
				if "chunks" in e:
					ui.label(f"{e['chunks']} chunks").classes("ml-auto text-grey-5")

	with ui.card().classes(CARD):
		ui.label("LIVE ACTIVITY").classes(TEXT)
		activity([])

	# ==== UPDATE HOOK ====

	async def update(snap: dict):
		info.refresh(snap["status"])
		file_list.refresh(snap["files"])
		activity.refresh(snap["events"])
		for e in snap["new"][:3]:
			if e.get("type") == "error":
				type = "negative"
			else:
				type = "info"
			ui.notify(
				f"{e.get('type')}: {e.get('path')}",
				type=type,
				position="bottom-right",
				timeout=2000
			)

	return update
