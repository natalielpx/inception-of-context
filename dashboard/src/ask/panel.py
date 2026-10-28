# panel.py
import httpx
from nicegui import ui
import data
from src.ask.components import QueryForm, AnswerView, HitsList


class AskRetrievePanel:
    """Wires the components together and talks to the API."""

    def __init__(self) -> None:
        ui.label("Retrieval and grounded Q&A over the index.").classes("text-grey-5")
        with ui.card().classes("w-full bg-slate-800"):
            self.form = QueryForm(self.on_retrieve, self.on_ask, self.on_new)
            self.answer = AnswerView()
            self.hits = HitsList()

    async def on_retrieve(self) -> None:
        res = await self._call(data.retrieve, "retrieve")
        if res:
            self.answer.clear()
            self.hits.show(res["hits"])

    async def on_ask(self) -> None:
        res = await self._call(data.ask, "ask")
        if res:
            self.answer.show(res["answer"])
            self.hits.show(res["hits"])

    def on_new(self) -> None:
        self.form.reset()
        self.answer.clear()
        self.hits.clear()

    async def _call(self, fn, which: str):
        q = self.form.question
        if not q:
            ui.notify("Enter a question first", type="warning")
            return None
        self.form.set_busy(True, which)
        try:
            return await fn(q, self.form.k)
        except httpx.HTTPError as e:
            ui.notify(f"API error: {e}", type="negative")
            return None
        finally:
            self.form.set_busy(False, which)

