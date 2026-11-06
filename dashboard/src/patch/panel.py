import httpx
from nicegui import ui

import data
from src.patch.components import QueryForm, PatchView


class PatchLoopPanel:

	def __init__(self) -> None:
		with ui.card().classes("w-full bg-slate-800"):
			self.form = QueryForm(self.on_patch)
			self.answer = PatchView()

	async def _call(self):
		q = self.form.question
		if not q:
			ui.notify("Enter an intent first", type="warning")
			return None
		self.form.set_busy(True)
		try:
			return await data.patch(q, self.form.k, self.form.max_attempts)
		except httpx.HTTPError as e:
			ui.notify(f"API error: {e}", type="negative")
			return None
		finally:
			self.form.set_busy(False)

	async def on_patch(self) -> None:
		result = await self._call()
		if result:
			self.answer.show(result)
