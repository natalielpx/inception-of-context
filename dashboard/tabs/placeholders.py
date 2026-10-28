"""Ask & Retrieve (Part 2) and Patch Loop (Part 3): final forms, disabled until those parts exist."""
from nicegui import ui
from src.ask.panel import AskRetrievePanel


def ask_and_retrieve():
    # TODO(p2): enable when source_mode() == "api"; wire to data.retrieve / data.ask
    ui.label("Available in Part 2: retrieval and grounded Q&A over the index.").classes("text-grey-5")
    AskRetrievePanel()

def patch_loop():
    # TODO(p3): enable when source_mode() == "api"; wire to data.run_patch
    ui.label("Available in Part 3: generate, apply, validate and roll back patches.").classes("text-grey-5")
    with ui.card().classes("w-full bg-slate-800"):
        ui.textarea("Intent").classes("w-full").disable()
        with ui.row().classes("items-center"):
            ui.number("k", value=5).classes("w-20").disable()
            ui.number("max attempts", value=3).classes("w-28").disable()
            ui.button("Run loop").disable()
