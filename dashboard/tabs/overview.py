"""Overview: status cards, indexed files, live activity feed."""
from nicegui import ui

from . import failed

BADGE = {"indexed": "positive", "deleted": "orange", "error": "negative"}


def _card(label: str, value) -> None:
    with ui.card().classes("p-3 min-w-36 bg-slate-800"):
        ui.label(label).classes("text-xs uppercase text-grey-5")
        ui.label(str(value)).classes("text-lg break-all")


def build():
    @ui.refreshable
    def cards(status: dict | None):
        if failed(status):
            ui.label(f"Index unavailable: {status['error']}").classes("text-negative")
            return
        s = status or {}
        with ui.row().classes("gap-3"):
            _card("chunks indexed", s.get("chunks", "…"))
            _card("files indexed", s.get("files", "…"))
            _card("target project", s.get("target_path", "…"))
            _card("qdrant", f"{s.get('qdrant_url', '…')} / {s.get('collection', '…')}")
            _card("embedding model", s.get("embedding_model", "…"))
            _card("ask model", s.get("ask_model") or "— (Part 2)")
            _card("code model", s.get("code_model") or "— (Part 3)")

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

    @ui.refreshable
    def activity(events: list):
        if not events:
            ui.label("No file activity yet. Edit a file in the target to see live updates.").classes("text-grey-6")
        for e in events:
            with ui.row().classes("w-full items-center no-wrap gap-3"):
                ui.label(str(e.get("ts", ""))[11:19]).classes("text-grey-5")
                ui.badge(e.get("type", "?"), color=BADGE.get(e.get("type"), "grey"))
                ui.label(e.get("path", "")).classes("truncate")
                counts = f"{e.get('chunks', 0)} chunks (+{e.get('added', 0)} ~{e.get('updated', 0)} −{e.get('removed', 0)})"
                ui.label(e.get("detail") or counts).classes("ml-auto text-grey-5")

    cards(None)
    with ui.card().classes("w-full bg-slate-800 mt-4"):
        ui.label("INDEXED FILES").classes("text-xs text-grey-5")
        file_list(None)
    with ui.card().classes("w-full bg-slate-800 mt-4"):
        ui.label("LIVE ACTIVITY").classes("text-xs text-grey-5")
        activity([])

    async def update(snap: dict):
        cards.refresh(snap["status"])
        file_list.refresh(snap["files"])
        activity.refresh(snap["events"])
        for e in snap["new"][:3]:
            ui.notify(f"{e.get('type')}: {e.get('path')}", type="negative" if e.get("type") == "error" else "info",
                      position="bottom-right", timeout=2000)

    return update
