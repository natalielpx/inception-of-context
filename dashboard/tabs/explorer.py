"""Qdrant Explorer: browse raw points page by page, inspect one payload."""
import json

from nicegui import ui

import data
from . import code, failed, fetch, language

COLUMNS = [{"name": n, "label": n, "field": f, "align": "left", "sortable": True}
           for n, f in [("id", "short_id"), ("path", "path"), ("lines", "lines"),
                        ("symbol", "symbol"), ("kind", "kind"), ("hash", "short_hash")]]


def build():
    state = {"cursor": None, "loaded": False, "payloads": {}}

    with ui.row().classes("items-end gap-4"):
        path_select = ui.select(["All"], value="All", label="path", on_change=lambda: reload()).classes("w-72")
        search = ui.input("filter loaded rows (symbol, path…)").classes("w-72")
    table = ui.table(columns=COLUMNS, rows=[], row_key="id", pagination={"rowsPerPage": 0}) \
        .props("dense flat").classes("w-full bg-slate-800")
    search.bind_value_to(table, "filter")
    table.on("rowClick", lambda e: detail.refresh(state["payloads"].get(e.args[1]["id"])))
    more = ui.button("Load more", on_click=lambda: load()).props("flat")

    @ui.refreshable
    def detail(payload: dict | None):
        if payload:
            with ui.expansion(f"point {payload['id']}", value=True).classes("w-full bg-slate-800"):
                code(payload.get("text", ""), language(payload.get("path", "")))
                code(json.dumps(payload, indent=2), "json")

    detail(None)

    async def load():
        path = None if path_select.value == "All" else path_select.value
        result = await fetch(data.get_chunks, path, 50, state["cursor"])
        if failed(result):
            ui.notify(result["error"], type="negative")
            return
        rows, state["cursor"] = result
        state["loaded"] = True
        state["payloads"].update({r["id"]: r for r in rows})
        table.add_rows([{"id": r["id"], "short_id": r["id"][:8], "path": r.get("path"), "symbol": r.get("symbol"),
                         "kind": r.get("kind"), "lines": f"{r.get('start_line')}–{r.get('end_line')}",
                         "short_hash": str(r.get("hash", ""))[:8]} for r in rows])
        more.set_enabled(state["cursor"] is not None)

    async def reload():
        state["cursor"] = None
        state["payloads"].clear()
        table.update_rows([])
        detail.refresh(None)
        await load()

    async def update(snap: dict):
        if not failed(snap["files"]):
            paths = [f["path"] for f in snap["files"]]
            current = path_select.value if path_select.value in paths else "All"
            path_select.set_options(["All", *paths], value=current)
        if not state["loaded"]:
            await reload()

    return update
