"""IoC Architect dashboard"""

import os, httpx
from nicegui import ui, background_tasks
from itertools import takewhile

import data
from data import SSE_ENDPOINT
from tabs import failed, fetch, files, overview
from styles import HEADER, TABS, TITLE
from src.ask.panel import AskRetrievePanel
from src.patch.panel import PatchLoopPanel

SITE_TITLE = "Inception-of-Context"
EXTERNAL_TABS = {"Qdrant Explorer": "http://localhost:6333/dashboard"}
PANEL_TABS = ["Overview", "Files", "Ask & Retrieve", "Patch Loop", *EXTERNAL_TABS]


def _key(event: dict) -> tuple:
	return event.get("ts"), event.get("path"), event.get("type")


@ui.page("/")
def index():

	ui.dark_mode(True)
	ui.query("body").classes("font-mono text-sm")

	async def consume():
		async with httpx.AsyncClient(timeout=None) as client:
			try:
				async with client.stream(
					"GET", SSE_ENDPOINT, headers={"Accept": "text/event-stream"}
				) as resp:
					ctype = resp.headers.get("content-type", "")
					print(f"status={resp.status_code} content-type={ctype}", flush=True)

					if "text/event-stream" not in ctype:
						body = await resp.aread()
						print(f"Unexpected response body: {body.decode(errors='replace')}", flush=True)
						return

					async for line in resp.aiter_lines():
						print(line, flush=True)
			except Exception as e:
				print(f"Error in SSE connection: {e}", flush=True)

	task = background_tasks.create(consume())
	ui.context.client.on_disconnect(task.cancel)

	# ==== HEADER ====

	with ui.header().classes(HEADER):
		ui.label(SITE_TITLE).classes(TITLE)
		ui.space()
		live = ui.badge("○ offline", color="grey-7")

	def _set_live_badge(is_live: bool) -> None:
		if is_live:
			live.set_text("● live")
			live.props("color='positive'")
		else:
			live.set_text("○ offline")
			live.props("color='grey-7'")

	# ==== TABS ====

	# Define tabs
	with ui.tabs().classes("w-full") as tabs:
		tab = {t: ui.tab(t) for t in PANEL_TABS}

	# Configure self hosted tabs
	with ui.tab_panels(tabs, value=tab["Overview"]).classes(TABS):
		with ui.tab_panel(tab["Overview"]):
			update_overview = overview.build()
		with ui.tab_panel(tab["Files"]):
			update_files = files.build()
		with ui.tab_panel(tab["Ask & Retrieve"]):
			AskRetrievePanel()
		with ui.tab_panel(tab["Patch Loop"]):
			PatchLoopPanel()

	# Stay on current panel when opening new browser tab
	current = {"tab": tab["Overview"]}
	def on_tab_change(e):
		for t, url in EXTERNAL_TABS.items():
			if e.value in (t, tab[t]):
				ui.navigate.to(url, new_tab=True)
				tabs.set_value(current["tab"])
				return
		current["tab"] = e.value
	tabs.on_value_change(on_tab_change)

	# ==== Reload ====

	state = {"tick": 0, "head": None, "status": None}
	async def tick():
		# --- Every tick ---
		# Read events log
		events = await fetch(data.get_events, 50)
		events = [] if failed(events) else events
		# Detect change
		head = _key(events[0]) if events else None
		changed = head != state["head"]
		# Extract new events
		if state["tick"] == 0:
			new = []
		else:
			new = list(takewhile(lambda e: _key(e) != state["head"], events))
		# --- Every 3 ticks ---
		if changed or state["tick"] % 3 == 0:
			status = await fetch(data.get_status)
			file_list = await fetch(data.get_files)
			_set_live_badge(failed(status))
			if changed or status != state["status"]:
				snap = {
					"events": events,
					"new": new,
					"status": status,
					"files": file_list
				}
				for update in (update_overview, update_files):
					await update(snap)
			state["status"] = status
		state["head"] = head
		state["tick"] += 1

	ui.timer(1.0, tick)


if __name__ in {"__main__", "__mp_main__"}:
	ui.run(
		title=SITE_TITLE,
		host="0.0.0.0",
		port=8080,
		dark=True,
		show=False,
		reload=False
	)
