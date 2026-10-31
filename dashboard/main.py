"""IoC Architect dashboard"""

from itertools import takewhile

from nicegui import ui

import data
from tabs import failed, fetch, files, overview, placeholders

# Tabs that open an external browser tab instead of showing a panel
EXTERNAL_TABS = {"Qdrant Explorer": "http://localhost:6333/dashboard"}


def _key(event: dict) -> tuple:
	return event.get("ts"), event.get("path"), event.get("type")


@ui.page("/")
def index():
	ui.dark_mode(True)
	ui.query("body").classes("font-mono text-sm")

	# ==== HEADER ====

	with ui.header().classes("items-center gap-3 px-4 py-2 bg-slate-900"):
		ui.label("Inception-of-Context").classes("text-base font-bold")
		ui.space()
		live = ui.badge("○ offline", color="grey-7")

	# ==== TABS ====

	# Define tabs
	with ui.tabs().classes("w-full") as tabs:
		names = ["Overview", "Files", "Ask & Retrieve", "Patch Loop", *EXTERNAL_TABS]
		tab = {name: ui.tab(name) for name in names}
	# Configure self hosted tabs
	with ui.tab_panels(tabs, value=tab["Overview"]).classes("w-full max-w-6xl mx-auto bg-transparent"):
		with ui.tab_panel(tab["Overview"]):
			update_overview = overview.build()
		with ui.tab_panel(tab["Files"]):
			update_files = files.build()
		with ui.tab_panel(tab["Ask & Retrieve"]):
			placeholders.ask_and_retrieve()
		with ui.tab_panel(tab["Patch Loop"]):
			placeholders.patch_loop()
	# Track current tab
	current = {"tab": tab["Overview"]}
	# If opens new browser tab, stay on current tab
	def on_tab_change(e):
		for name, url in EXTERNAL_TABS.items():
			if e.value in (name, tab[name]):
				ui.navigate.to(url, new_tab=True)
				tabs.set_value(current["tab"])
				return
		current["tab"] = e.value
	# Handler
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
		new = [] if state["tick"] == 0 else list(takewhile(lambda e: _key(e) != state["head"], events))
		# --- Every 5 ticks ---
		if changed or state["tick"] % 5 == 0:
			# Read Qdrant
			status, file_list = await fetch(data.get_status), await fetch(data.get_files)
			# Update live/offline badge
			ok = not failed(status)
			live.set_text("● live" if ok else "○ offline")
			live.props(f"color={'positive' if ok else 'grey-7'}")
			# If something changed, push snapshots to tabs
			if changed or status != state["status"]:
				snap = {"events": events, "new": new, "status": status, "files": file_list}
				for update in (update_overview, update_files):
					await update(snap)
		# Update variables
			state["status"] = status
		state["head"] = head
		state["tick"] += 1
	# Tick length = 1s
	ui.timer(1.0, tick)


if __name__ in {"__main__", "__mp_main__"}:
	ui.run(title="IoC Architect", host="0.0.0.0", port=8080, dark=True, show=False, reload=False)
