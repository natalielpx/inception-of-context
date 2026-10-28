import os
from pathlib import Path


EXCL_DIRS = {
	"node_modules", ".git", "dist", "build", "venv", ".venv", "__pycache__",
	".pio", ".qdrant", "out", "bin", "obj",
}
INCL_EXTS = {
	".cpp", ".c", ".h", ".hpp", ".yml", ".yaml", ".md", ".txt"
}


def _is_binary(path: Path) -> bool:
	"""Catches binary files with included extensions"""
	try:
		with open(path, "rb") as fh:
			return b"\0" in fh.read(8192)
	except OSError:
		return False  # unreadable/vanished: let indexer decide

def _file_ok(name: str) -> bool:
	return not name.startswith(".") and Path(name).suffix.lower() in INCL_EXTS

def _dir_ok(name: str) -> bool:
	return not name.startswith(".") and name.lower() not in EXCL_DIRS

def to_be_indexed(root: str, path: str) -> bool:
	"""Should this path be indexed? Works for deleted files too."""
	p = Path(path)
	try:
		rel = p.resolve().relative_to(Path(root).resolve())
	except ValueError:
		return False
	if not rel.parts:
		return False
	*dirs, name = rel.parts
	if not (all(_dir_ok(d) for d in dirs) and _file_ok(name)):
		return False
	# return False
	return not (p.is_file() and _is_binary(p))


def files_to_be_indexed(root: str, path: str) -> list[Path]:
	"""Files to index under `path` (file,directory, or missing)"""
	p = Path(path)
	if p.is_file():
		candidates = [p]
	elif p.is_dir():
		candidates = []
		for cur, dirnames, filenames in os.walk(p):
			dirnames[:] = [d for d in dirnames if _dir_ok(d)]  # prune early
			candidates += [Path(cur, f) for f in filenames]
	else:
		return []
	return [f for f in candidates if to_be_indexed(root, f)]