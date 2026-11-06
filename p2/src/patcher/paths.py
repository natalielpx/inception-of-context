"""Resolve patch paths safely inside the target root."""
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath


class UnsafePathError(Exception):
    pass


def safe_resolve(root: str | Path, rel: str, excludes: list[str]) -> Path:
    """Return the absolute path for `rel` under `root`, or raise.

    Rejects: empty paths, absolute paths, '..', hidden or excluded
    components, *.ioc.tmp names, and anything that escapes root via
    symlinks.
    """
    if not isinstance(rel, str) or not rel.strip():
        raise UnsafePathError("empty path")
    rel = rel.strip().replace("\\", "/")
    if "\x00" in rel:
        raise UnsafePathError("NUL byte in path")

    p = PurePosixPath(rel)
    if p.is_absolute() or (len(rel) > 1 and rel[1] == ":"):
        raise UnsafePathError(f"absolute path not allowed: {rel}")

    parts = [x for x in p.parts if x not in ("", ".")]
    if not parts:
        raise UnsafePathError(f"path points at root: {rel}")
    for part in parts:
        if part == "..":
            raise UnsafePathError(f"'..' not allowed: {rel}")
        if part.startswith("."):
            raise UnsafePathError(f"hidden path not allowed: {rel}")
        if part in excludes:
            raise UnsafePathError(f"excluded directory: {part}")
    if parts[-1].endswith(".ioc.tmp"):
        raise UnsafePathError(f"reserved temp name: {rel}")

    root_real = Path(os.path.realpath(root))
    target = root_real.joinpath(*parts)
    # realpath follows symlinks on existing ancestors
    resolved = Path(os.path.realpath(target))
    if resolved != root_real and root_real not in resolved.parents:
        raise UnsafePathError(f"escapes target root: {rel}")
    return target


def rel_to_root(root: str | Path, abs_path: Path) -> str:
    return abs_path.relative_to(Path(os.path.realpath(root))).as_posix()