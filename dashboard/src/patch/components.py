import json
from nicegui import ui


class QueryForm:

	def __init__(self, on_patch) -> None:
		self._question = ui.textarea("Intent").classes("w-full")
		self._question.on("keydown.ctrl.enter", on_patch)
		with ui.row().classes("items-center"):
			self._k = ui.number("k", value=5, precision=0).classes("w-20")
			self._max_attempts = ui.number("max attempts", value=3, precision=0).classes("w-20")
			ui.space()
			self._buttons = ui.button("Patch", on_click=on_patch)

	@property
	def question(self) -> str:
		return (self._question.value or "").strip()

	@property
	def k(self) -> int:
		return int(self._k.value or 5)

	@property
	def max_attempts(self) -> int:
		return int(self._max_attempts.value or 3)

	def reset(self) -> None:
		self._question.value = ""

	def set_busy(self, busy: bool) -> None:
		self._button.set_enabled(not busy)
		if busy:
			self._button.props("loading")
		else:
			self._button.props(remove="loading")


class PatchView:

    def __init__(self) -> None:
        self._box = ui.column().classes("w-full")

    def clear(self) -> None:
        self._box.clear()

    def show(self, res: dict) -> None:
        self.clear()
        with self._box:
            ok = res["status"] == "success"
            ui.badge(f"{res['status'].upper()} in {len(res['attempts'])} attempt(s)",
                     color="green" if ok else "red")
            if res.get("final_patch"):
                with ui.expansion("Final patch", value=True).classes("w-full"):
                    ui.code(json.dumps(res["final_patch"], indent=2), language="json").classes("w-full")
            for a in res["attempts"]:
                label = f"attempt {a['n']} · {a['stage']} · " + ("OK" if a["ok"] else a["error"] or "")
                with ui.expansion(label).classes("w-full"):
                    ui.code(a["raw"] or "(no output)").classes("w-full")
