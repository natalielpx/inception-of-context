import streamlit as st

import data


def render():
    status = data.get_status()
    if err := data.error_of(status):
        st.error(f"Cannot read the index: {err}")
    else:
        cols = st.columns(7)
        cols[0].metric("Chunks indexed", status["chunks"])
        cols[1].metric("Files indexed", status["files"])
        cols[2].metric("Target project", status["target_path"])
        cols[3].metric(f"Qdrant · {status['qdrant_url']}", status["collection"])
        cols[4].metric("Embedding model", status["embedding_model"])
        cols[5].metric("Ask model", status["ask_model"] or "— (Part 2)")
        cols[6].metric("Code model", status["code_model"] or "— (Part 3)")

        st.subheader("Indexed files")
        files = data.get_files()
        if not files:
            st.info("Nothing indexed yet. Run the indexer against the target.")
        elif not data.error_of(files):
            top = max(f["chunks"] for f in files)
            st.dataframe(files, hide_index=True, width="stretch", column_config={
                "chunks": st.column_config.ProgressColumn("chunks", format="%d", min_value=0, max_value=top)})

    live_activity()


@st.fragment(run_every="2s")
def live_activity():
    st.subheader("Live activity")
    events = data.get_events(50)
    if err := data.error_of(events):
        st.error(err)
    elif not events:
        st.info("No file activity yet. Edit a file in the target to see live updates.")
    else:
        keys = ("ts", "type", "path", "chunks", "added", "updated", "removed", "detail")
        st.dataframe([{k: e.get(k) for k in keys} for e in events], hide_index=True, width="stretch",
                     column_config={"ts": "time"})
