import streamlit as st

import data
from tabs import explorer, files, overview, placeholders

st.set_page_config(page_title="IoC Architect", layout="wide")
st.title("Inception-of-Context Architect")

try:
    status = data.get_status()
    chunks = status.get("chunks", "?")
except NotImplementedError:
    chunks = "?"
st.caption(f"chunks {chunks} · Qdrant: {data.COLLECTION} · source: {data.source_mode()}")

TABS = {
    "Overview": overview.render,
    "Files": files.render,
    "Ask & Retrieve": placeholders.ask,
    "Patch Loop": placeholders.patch,
    "Qdrant Explorer": explorer.render,
}
for tab, render in zip(st.tabs(list(TABS)), TABS.values()):
    with tab:
        try:
            render()
        except NotImplementedError as e:
            st.warning(str(e))
