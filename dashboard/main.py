"""IoC Architect dashboard. Each tab panel calls one build function; one timer feeds them all."""
from itertools import takewhile

from nicegui import ui

import data
from tabs import explorer, failed, fetch, files, overview, placeholders


def _key(event: dict) -> tuple:
    return event.get("ts"), event.get("path"), event.get("type")


@ui.page("/")
def index():
    ui.dark_mode(True)
    ui.query("body").classes("font-mono text-sm")

    with ui.header().classes("items-center gap-3 px-4 py-2 bg-slate-900"):
        ui.label("Inception-of-Context Architect").classes("text-base font-bold")

        @ui.refreshable
        def badges(status: dict | None):
            chunks = "?" if not status or failed(status) else status["chunks"]
            ui.badge(f"chunks {chunks}", color="blue-grey-8")
            ui.badge(f"Qdrant: {data.COLLECTION}", color="blue-grey-8")
            ui.badge(f"source: {data.source_mode()}", color="blue-grey-8")

        badges(None)
        ui.space()
        live = ui.badge("○ offline", color="grey-7")

    with ui.tabs().classes("w-full") as tabs:
        names = ["Overview", "Files", "Ask & Retrieve", "Patch Loop", "Qdrant Explorer"]
        tab = {name: ui.tab(name) for name in names}
    with ui.tab_panels(tabs, value=tab["Overview"]).classes("w-full max-w-6xl mx-auto bg-transparent"):
        with ui.tab_panel(tab["Overview"]):
            update_overview = overview.build()
        with ui.tab_panel(tab["Files"]):
            update_files = files.build()
        with ui.tab_panel(tab["Ask & Retrieve"]):
            placeholders.ask_and_retrieve()
        with ui.tab_panel(tab["Patch Loop"]):
            placeholders.patch_loop()
        with ui.tab_panel(tab["Qdrant Explorer"]):
            update_explorer = explorer.build()

    state = {"tick": 0, "head": None, "status": None}

    async def tick():
        """Every second: read the events log. On a change (or every 5 s) also re-read Qdrant."""
        events = await fetch(data.get_events, 50)
        events = [] if failed(events) else events
        head = _key(events[0]) if events else None
        changed = head != state["head"]
        new = [] if state["tick"] == 0 else list(takewhile(lambda e: _key(e) != state["head"], events))
        if changed or state["tick"] % 5 == 0:
            status, file_list = await fetch(data.get_status), await fetch(data.get_files)
            ok = not failed(status)
            live.set_text("● live" if ok else "○ offline")
            live.props(f"color={'positive' if ok else 'grey-7'}")
            if changed or status != state["status"]:
                snap = {"events": events, "new": new, "status": status, "files": file_list}
                badges.refresh(status)
                for update in (update_overview, update_files, update_explorer):
                    await update(snap)
            state["status"] = status
        state["head"] = head
        state["tick"] += 1

    ui.timer(1.0, tick)


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="IoC Architect", host="0.0.0.0", port=8080, dark=True, show=False, reload=False)
