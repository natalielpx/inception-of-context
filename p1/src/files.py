import os
from pathlib import Path


EXCL_DIRS = {
	"node_modules", ".git", "dist", "build", "venv", ".venv", "__pycache__",
	".pio", ".qdrant", "out", "bin", "obj",
}
INCL_EXTS = {
	".cpp", ".c", ".h", ".hpp", ".yml", ".yaml", ".md", ".txt"
}


def _file_ok(name: str) -> bool:
	return not name.startswith(".") and Path(name).suffix.lower() in INCL_EXTS

def _dir_ok(name: str) -> bool:
	return not name.startswith(".") and name.lower() not in EXCL_DIRS

def _rel_parts(root: str, path: str):
	try:
		return Path(os.path.abspath(path)).relative_to(os.path.abspath(root)).parts
	except ValueError:
		return None
	
def is_included_dir(root: str, path: str):
	parts = _rel_parts(root, path)
	if parts is None:
		return False
	if not (all(_dir_ok(d) for d in parts)):
		return False
	return True

def is_included_file(root: str, path: str):
	path = os.path.abspath(path)
	if not is_included_dir(root, os.path.dirname(path)):
		return False
	return  _file_ok(os.path.basename(path))


def collect_files(root: str, path: str) -> list[str]:
	"""Files to index under `path` (file, directory, or missing)"""
	p = Path(path)
	if p.is_file() and is_included_file(root, path):
		return [path]
	elif p.is_dir() and is_included_dir(root, path):
		candidates = []
		for cur, dirnames, filenames in os.walk(p):
			dirnames[:] = [d for d in dirnames if _dir_ok(d)]
			candidates += [os.path.join(cur, f) for f in filenames if _file_ok(f)]
	else:
		return []
	return candidates