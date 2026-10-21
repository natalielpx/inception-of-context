"""Files: the on-disk file, rendered one chunk at a time."""
from nicegui import ui

import data
from . import code, failed, fetch, language


def _segments(lines: list[str], chunks: list[dict]):
    """Chunks plus the runs of lines no chunk covers, ordered by first line."""
    covered = {n for c in chunks for n in range(c["start_line"], c["end_line"] + 1)}
    gaps, start, last = [], None, None
    for n in range(1, len(lines) + 2):
        if n > len(lines) or n in covered:
            if start:
                gaps.append({"start_line": start, "end_line": last, "gap": True})
            start = None
        elif lines[n - 1].strip():  # blank lines neither open nor close a gap
            start, last = start or n, n
    return sorted([*chunks, *gaps], key=lambda s: s["start_line"])


def build():
    state = {"path": None}

    @ui.refreshable
    def file_list(files: list | None):
        for f in [] if not files or failed(files) else files:
            selected = "bg-slate-700" if f["path"] == state["path"] else ""
            with ui.row().classes(f"w-full no-wrap cursor-pointer px-2 py-1 rounded {selected}") \
                    .on("click", lambda p=f["path"]: open_file(p)):
                ui.label(f["path"]).classes("truncate")
                ui.label(str(f["chunks"])).classes("ml-auto text-grey-5")

    @ui.refreshable
    def view(file: dict | None):
        if file is None:
            ui.label("Select a file.").classes("text-grey-6")
            return
        if failed(file):
            ui.label(file["error"]).classes("text-warning" if file.get("missing") else "text-negative")
            return
        ui.label(file["path"]).classes("text-base")
        ui.label(f"{file['lines']} lines · {file['bytes']} bytes · {len(file['chunks'])} chunks").classes("text-grey-5")
        lines, lang, n = file["content"].splitlines(), language(file["path"]), 0
        for seg in _segments(lines, file["chunks"]):
            span = f"lines {seg['start_line']}–{seg['end_line']}"
            if seg.get("gap"):
                ui.label(f"(not in any chunk) — {span}").classes("text-grey-6 mt-2")
            else:
                n += 1
                ui.label(f"▶ chunk #{n} — {span} · {seg.get('symbol') or seg.get('kind', '')}").classes("text-primary mt-2")
            code("\n".join(lines[seg["start_line"] - 1:seg["end_line"]]), lang)

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

    async def update(snap: dict):
        file_list.refresh(snap["files"])
        if state["path"] and any(e.get("path") == state["path"] for e in snap["new"]):
            await open_file(state["path"])

    return update
