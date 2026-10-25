import os
from pathlib import Path


EXCL_DIRS = {
	"node_modules", ".git", "dist", "build", "venv", ".venv", "__pycache__",
	".pio", ".qdrant", "out", "bin", "obj",
}
INCL_EXTS = {
	".cpp", ".c", ".h", ".hpp", ".yml", ".yaml", ".md", ".txt"
}


def _dir_name_ok(name: str) -> bool:
	return not name.startswith(".") and name.lower() not in EXCL_DIRS


def _file_name_ok(name: str) -> bool:
	return not name.startswith(".") and Path(name).suffix.lower() in INCL_EXTS


def _is_binary(path: str) -> bool:
	try:
		with open(path, "rb") as fh:
			return b"\0" in fh.read(8192)
	except OSError:
		return True


def dir_to_be_indexed(root: str, dirpath: str) -> bool:
	"""True if `dirpath` is inside `root` and no folder on the way is excluded.
	Path-only: works for folders that no longer exist."""
	try:
		rel = Path(dirpath).resolve().relative_to(Path(root).resolve())
	except ValueError:
		return False
	return all(_dir_name_ok(name) for name in rel.parts)


def path_to_be_watched(root: str, path: str) -> bool:
	"""True if a file at `path` would be indexed, judging by its path alone.
	Path-only: works for deleted files. Used by the watcher."""
	p = Path(path)
	return _file_name_ok(p.name) and dir_to_be_indexed(root, str(p.parent))


def file_to_be_indexed(root: str, filepath: str) -> bool:
	"""path_to_be_watched, plus: it exists, is a file, and isn't binary."""
	return (
		path_to_be_watched(root, filepath)
		and os.path.isfile(filepath)
		and not _is_binary(filepath)
	)


def files_to_be_indexed(root: str, dirpath: str) -> list[str]:
	"""Every indexable file under `dirpath`."""
	if not dir_to_be_indexed(root, dirpath):
		return []

	files = []
	for current, dirnames, filenames in os.walk(dirpath):
		# Parents are already validated, so checking each name is enough
		dirnames[:] = [d for d in dirnames if _dir_name_ok(d)]
		for f in filenames:
			full = os.path.join(current, f)
			if _file_name_ok(f) and os.path.isfile(full) and not _is_binary(full):
				files.append(full)
	return files