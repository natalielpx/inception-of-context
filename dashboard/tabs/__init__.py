"""Small helpers shared by the tabs."""
from pathlib import PurePath

from nicegui import run, ui

LANGS = {".py": "python", ".yml": "yaml", ".yaml": "yaml", ".md": "markdown",
         ".json": "json", ".js": "javascript", ".ts": "typescript"}


async def fetch(fn, *args):
    """Run a data.py function off the event loop; unbuilt features become an error dict."""
    try:
        return await run.io_bound(fn, *args)
    except NotImplementedError as e:
        return {"error": str(e)}


def failed(result) -> bool:
    return isinstance(result, dict) and "error" in result


def language(path: str) -> str:
    return LANGS.get(PurePath(path).suffix.lower(), "text")


def code(text: str, lang: str) -> None:
    # ui.code wraps content in a ``` fence; a zero-width space keeps nested fences (e.g. in a README) from closing it
    ui.code(text.replace("```", "`​``"), language=lang).classes("w-full")
