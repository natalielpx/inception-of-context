import streamlit as st

import data

PAGE = 50
ss = st.session_state


def load_page():
    """Append the next page for the current path filter to the loaded rows."""
    path = None if ss.exp_path == "All" else ss.exp_path
    rows, cursor = data.get_chunks(path, PAGE, ss.exp_cursor)
    if err := data.error_of(rows):
        ss.exp_error = err
        return
    ss.exp_rows += rows
    ss.exp_cursor, ss.exp_done, ss.exp_error = cursor, cursor is None, None


def reset():
    ss.exp_rows, ss.exp_cursor, ss.exp_done, ss.exp_error = [], None, False, None
    load_page()


def render():
    files = data.get_files()
    if err := data.error_of(files):
        return st.error(err)

    left, right = st.columns(2)
    left.selectbox("Path", ["All"] + [f["path"] for f in files], key="exp_path", on_change=reset)
    symbol = right.text_input("Symbol contains", key="exp_symbol").strip().lower()
    if "exp_rows" not in ss:
        reset()
    if ss.exp_error:
        st.error(ss.exp_error)

    rows = [r for r in ss.exp_rows if symbol in (r.get("symbol") or "").lower()]
    st.dataframe([{"id": r["id"], "path": r.get("path"), "lines": f"{r.get('start_line')}–{r.get('end_line')}",
                   "symbol": r.get("symbol"), "kind": r.get("kind"), "hash": (r.get("hash") or "")[:8]}
                  for r in rows], hide_index=True, width="stretch")

    a, b, _ = st.columns([1, 1, 6])
    a.button("Load more", on_click=load_page, disabled=ss.exp_done)
    b.button("Refresh", on_click=reset)
    st.caption(f"{len(rows)} shown · {len(ss.exp_rows)} loaded" + (" · end of collection" if ss.exp_done else ""))

    if rows:
        by_id = {r["id"]: r for r in rows}
        point_id = st.selectbox("Point", list(by_id),
                                format_func=lambda i: f"{i} · {by_id[i].get('path')} · {by_id[i].get('symbol')}")
        point = by_id[point_id]
        st.code(point.get("text", ""), language="python" if point.get("path", "").endswith(".py") else "text")
        st.json({k: v for k, v in point.items() if k != "text"})
