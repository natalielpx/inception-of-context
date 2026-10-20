import streamlit as st


def ask():
    # TODO(p2): enable when source_mode() == "api"; Retrieve -> data.retrieve, Ask LLM -> data.ask.
    st.info("Available in Part 2: retrieval and grounded Q&A over the index.")
    st.text_area("Question or intent", placeholder="explain how NoteService.search works", disabled=True)
    cols = st.columns([1, 1, 1, 1, 4])
    cols[0].number_input("k", min_value=1, max_value=20, value=5, disabled=True, key="ask_k")
    cols[1].button("Retrieve", disabled=True)
    cols[2].button("Ask LLM", disabled=True)
    cols[3].button("New conversation", disabled=True)


def patch():
    # TODO(p3): enable when source_mode() == "api"; Run loop -> data.run_patch.
    st.info("Available in Part 3: generate, apply, validate and roll back patches.")
    st.text_area("Intent", placeholder="add a function whisper(name) in main.py", disabled=True)
    cols = st.columns([1, 1, 1, 5])
    cols[0].number_input("k", min_value=1, max_value=20, value=5, disabled=True, key="patch_k")
    cols[1].number_input("max attempts", min_value=1, max_value=3, value=3, disabled=True)
    cols[2].button("Run loop", disabled=True)
