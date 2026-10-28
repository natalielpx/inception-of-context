# components.py
from nicegui import ui


class QueryForm:
    """Question box, k and buttons. Knows nothing about the API."""

    def __init__(self, on_retrieve, on_ask, on_new) -> None:
        self._question = ui.textarea("Question or intent").classes("w-full")
        self._question.on("keydown.ctrl.enter", on_ask)
        with ui.row().classes("items-center"):
            self._k = ui.number("k", value=5, precision=0).classes("w-20")
            self._buttons = {
                "retrieve": ui.button("Retrieve", on_click=on_retrieve),
                "ask": ui.button("Ask LLM", on_click=on_ask),
            }
            ui.button("New conversation", on_click=on_new)

    @property
    def question(self) -> str:
        return (self._question.value or "").strip()

    @property
    def k(self) -> int:
        return int(self._k.value or 5)

    def reset(self) -> None:
        self._question.value = ""

    def set_busy(self, busy: bool, which: str) -> None:
        for b in self._buttons.values():
            b.set_enabled(not busy)
        if busy:
            self._buttons[which].props("loading")
        else:
            self._buttons[which].props(remove="loading")


class AnswerView:
    """Renders the LLM answer as markdown."""

    def __init__(self) -> None:
        self._md = ui.markdown().classes("w-full")

    def show(self, text: str) -> None:
        self._md.set_content(text)

    def clear(self) -> None:
        self._md.set_content("")


class HitsList:
    """Renders retrieved chunks as expandable items."""

    def __init__(self) -> None:
        self._box = ui.column().classes("w-full")

    def show(self, hits: list[dict]) -> None:
        self._box.clear()
        with self._box:
            n = len(hits)
            ui.label(f"{n} source{'s' if n != 1 else ''} used to answer").classes(
                "text-grey text-xs"
            )
            if hits:
                for h in hits:
                    lines = f"{h.get('start_line', '?')}-{h.get('end_line', '?')}"
                    with ui.expansion().classes("w-full") as exp:
                        with exp.add_slot("header"):
                            with ui.row().classes("items-center gap-3"):
                                ui.label(f"{h['path']}:{lines}").classes(
                                    "bg-blue-900 text-blue-200 font-mono text-xs px-2 py-1 rounded"
                                )
                                ui.label(f"score {h['score']:.2f}").classes("text-grey text-xs")
                        ui.code(h["text"])

    def clear(self) -> None:
        self._box.clear()