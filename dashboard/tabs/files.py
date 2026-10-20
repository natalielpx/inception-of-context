from pathlib import Path

import streamlit as st

import data

LANGUAGES = {".py": "python", ".yml": "yaml", ".yaml": "yaml", ".md": "markdown",
             ".json": "json", ".js": "javascript", ".ts": "typescript"}


def render():
    files = data.get_files()
    if err := data.error_of(files):
        return st.error(err)
    if not files:
        return st.info("Nothing indexed yet.")

    counts = {f["path"]: f["chunks"] for f in files}
    left, right = st.columns([1, 3])
    path = left.radio("Files in target", list(counts), format_func=lambda p: f"{p} · {counts[p]}")

    with right:
        f = data.get_file(path)
        if err := data.error_of(f):
            return st.error(err)
        st.subheader(path)
        st.caption(f"{f['lines']} lines · {f['bytes']} bytes · {len(f['chunks'])} chunks")
        language = LANGUAGES.get(Path(path).suffix.lower(), "text")
        for title, start, end in sections(f):
            st.markdown(title)
            show_lines(f["content"], start, end, language)


def sections(f):
    """(title, start, end) for every chunk, plus non-blank gaps between chunks. Lines are 1-based."""
    lines, pos = f["content"].splitlines(), 1
    out = []
    for i, c in enumerate(f["chunks"], 1):
        start, end = c["start_line"], c["end_line"]
        if start > pos and "".join(lines[pos - 1:start - 1]).strip():
            out.append(("**(not in any chunk)**", pos, start - 1))
        symbol = f" · `{c['symbol']}`" if c.get("symbol") else ""
        out.append((f"**▶ chunk #{i} — lines {start}–{end}**{symbol}", start, end))
        pos = max(pos, end + 1)
    if pos <= len(lines) and "".join(lines[pos - 1:]).strip():
        out.append(("**(not in any chunk)**", pos, len(lines)))
    return out


def show_lines(content, start, end, language):
    # st.code numbers every block from 1, so print the real file line numbers ourselves.
    all_lines = content.splitlines()
    lines, width = all_lines[start - 1:end], len(str(len(all_lines)))
    st.code("\n".join(f"{n:>{width}}  {line}" for n, line in enumerate(lines, start)), language=language)
