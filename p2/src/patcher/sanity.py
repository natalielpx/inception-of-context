"""Phase 2: sanity checks run on a parsed Patch before anything touches disk.

This module never writes. Its only disk access is reading the files a patch
is about to modify. Every check returns ``SanityFailure | None``;
``run_sanity`` collects all of them and never raises.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable

import yaml

from p3.config import IocConfig
from p3.paths import UnsafePathError, safe_resolve
from p3.patch_schema import FileOp, Patch

CPP_SUFFIXES = frozenset({".cpp", ".cc", ".cxx", ".h", ".hpp", ".hh"})
YAML_SUFFIXES = frozenset({".yml", ".yaml"})
EMPTY_SENTINELS = frozenset({"", "None", "null"})
SHRINK_MIN_CHARS = 200

# Shared with Phase 1, which renders retrieval hits with these delimiters.
CONTEXT_OPEN = "<<<FILE"
CONTEXT_CLOSE = "<<<END>>>"
RETRIEVAL_MARKERS: list[re.Pattern[str]] = [
    re.compile(re.escape(CONTEXT_OPEN)),
    re.compile(re.escape(CONTEXT_CLOSE)),
    re.compile(r"score="),
    re.compile(r'^\s*"?(?:score|start_line|end_line|chunk_id)"?\s*:', re.MULTILINE),
]
# In YAML, `score:` is a legitimate key, so only the delimiters count.
YAML_RETRIEVAL_MARKERS: list[re.Pattern[str]] = RETRIEVAL_MARKERS[:2]


@dataclass(frozen=True)
class SanityFailure:
    check: str
    path: str | None
    reason: str


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def _suffix(path: str) -> str:
    return PurePosixPath(path.replace("\\", "/")).suffix.lower()


def is_cpp(path: str) -> bool:
    return _suffix(path) in CPP_SUFFIXES


def is_yaml(path: str) -> bool:
    return _suffix(path) in YAML_SUFFIXES


def _is_binary_bytes(data: bytes) -> bool:
    if b"\x00" in data:
        return True
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def read_current(target: Path) -> str | None:
    """Current file text (UTF-8, errors replaced), or None if missing/binary."""
    if not target.is_file():
        return None
    data = target.read_bytes()
    if _is_binary_bytes(data):
        return None
    return data.decode("utf-8", errors="replace")


# --------------------------------------------------------------------------
# patch-level and path checks
# --------------------------------------------------------------------------

def check_too_many_files(patch: Patch, cfg: IocConfig) -> SanityFailure | None:
    """Fail when the patch touches more than ``cfg.max_files`` files."""
    n = len(patch.files)
    if n <= cfg.max_files:
        return None
    return SanityFailure(
        "too_many_files", None,
        f"patch touches {n} files (max {cfg.max_files}) — "
        f"limit the change to at most {cfg.max_files} files",
    )


def check_unsafe_path(fop: FileOp, root: Path, cfg: IocConfig) -> SanityFailure | None:
    """Fail when ``safe_resolve`` rejects the path (escape, hidden, excluded, ...)."""
    try:
        safe_resolve(root, fop.path, list(cfg.exclude))
    except UnsafePathError as e:
        return SanityFailure(
            "unsafe_path", fop.path,
            f"{e} — use a relative path inside the project, outside excluded folders",
        )
    return None


def check_create_existing(fop: FileOp, target: Path) -> SanityFailure | None:
    """Fail when ``op == create`` and the file already exists."""
    if fop.op != "create" or not target.exists():
        return None
    return SanityFailure(
        "create_existing", fop.path,
        "file already exists — use op 'modify' with the complete new file content",
    )


def check_missing_target(fop: FileOp, target: Path) -> SanityFailure | None:
    """Fail when ``op`` is modify/delete and the path is not an existing file."""
    if fop.op not in ("modify", "delete"):
        return None
    if target.is_dir():
        return SanityFailure(
            "missing_target", fop.path,
            "path is a directory, not a file — target a single file",
        )
    if target.exists():
        return None
    return SanityFailure(
        "missing_target", fop.path,
        f"cannot {fop.op}: file does not exist — use op 'create' or fix the path",
    )


def check_binary_file(fop: FileOp, target: Path) -> SanityFailure | None:
    """Fail when ``op == modify`` targets a file that is not valid UTF-8 text."""
    if fop.op != "modify" or not target.is_file():
        return None
    if not _is_binary_bytes(target.read_bytes()):
        return None
    return SanityFailure(
        "binary_file", fop.path,
        "file is binary (not UTF-8 text) — do not modify binary files",
    )


# --------------------------------------------------------------------------
# content checks
# --------------------------------------------------------------------------

def check_retrieval_markers(fop: FileOp, old: str | None) -> SanityFailure | None:
    """Fail when content contains leaked retrieval-context artifacts.

    Case-sensitive. YAML files only check the ``<<<`` delimiters. For
    ``modify``, a marker counts only if it appears more often than in the
    current file, so existing code like ``score=0`` does not block a patch.
    """
    if fop.content is None:
        return None
    patterns = YAML_RETRIEVAL_MARKERS if is_yaml(fop.path) else RETRIEVAL_MARKERS
    base = old if fop.op == "modify" and old else ""
    hits = [
        p.pattern for p in patterns
        if len(p.findall(fop.content)) > len(p.findall(base))
    ]
    if not hits:
        return None
    return SanityFailure(
        "retrieval_markers", fop.path,
        f"content contains retrieval context markers ({', '.join(hits)}) — "
        f"output only the file's source, without {CONTEXT_OPEN} ...>>> / "
        f"{CONTEXT_CLOSE} wrappers or chunk metadata",
    )


def check_emptied_file(fop: FileOp, old: str | None) -> SanityFailure | None:
    """Fail when ``modify`` replaces a non-empty file with "", "None" or "null"."""
    if fop.op != "modify" or fop.content is None or not old or not old.strip():
        return None
    if fop.content.strip() not in EMPTY_SENTINELS:
        return None
    return SanityFailure(
        "emptied_file", fop.path,
        f"would replace a non-empty file with {fop.content.strip()!r} — return the "
        "complete file content, or use op 'delete' if removal is intended",
    )


def check_excessive_shrink(
    fop: FileOp, old: str | None, cfg: IocConfig
) -> SanityFailure | None:
    """Fail when ``modify`` shrinks the file below ``(1 - max_shrink)`` of its size.

    Lengths ignore trailing whitespace. Files under 200 characters are
    skipped, and emptied files are left to ``emptied_file``.
    """
    if fop.op != "modify" or fop.content is None or not old:
        return None
    old_r, new_r = old.rstrip(), fop.content.rstrip()
    if len(old_r) < SHRINK_MIN_CHARS or new_r.strip() in EMPTY_SENTINELS:
        return None
    if len(new_r) >= (1 - cfg.max_shrink) * len(old_r):
        return None
    pct = round(100 * (1 - len(new_r) / len(old_r)))
    return SanityFailure(
        "excessive_shrink", fop.path,
        f"file would shrink by {pct}% ({len(old_r)} -> {len(new_r)} chars, limit "
        f"{round(cfg.max_shrink * 100)}%) — return the COMPLETE file including "
        "unchanged code, not only the edited part",
    )


def check_noop_modify(fop: FileOp, old: str | None) -> SanityFailure | None:
    """Fail when ``modify`` content is identical to the current file."""
    if fop.op != "modify" or old is None or fop.content != old:
        return None
    return SanityFailure(
        "noop_modify", fop.path,
        "new content is identical to the current file — make the requested "
        "change, or leave this file out of the patch",
    )


def check_invalid_yaml(fop: FileOp) -> SanityFailure | None:
    """Fail when a .yml/.yaml file's content is rejected by ``yaml.safe_load_all``."""
    if fop.content is None or not is_yaml(fop.path):
        return None
    try:
        for _ in yaml.safe_load_all(fop.content):
            pass
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None) or getattr(e, "context_mark", None)
        where = f" at line {mark.line + 1}" if mark is not None else ""
        problem = getattr(e, "problem", None) or str(e).splitlines()[0]
        return SanityFailure(
            "invalid_yaml", fop.path,
            f"invalid YAML{where}: {problem} — fix the indentation/syntax and "
            "return the full valid file",
        )
    return None


def check_stub_body(fop: FileOp, old: str | None) -> SanityFailure | None:
    """Fail when a C++ create/modify introduces placeholder function bodies.

    For ``modify`` only new stubs count (see ``new_stub_names``).
    """
    if fop.op not in ("create", "modify") or fop.content is None:
        return None
    if not is_cpp(fop.path):
        return None
    base = (old or "") if fop.op == "modify" else ""
    names = new_stub_names(base, fop.content)
    if not names:
        return None
    listed = ", ".join(f"{n}()" for n in names)
    return SanityFailure(
        "stub_body", fop.path,
        f"stub body in {listed} — write the full implementation, not a placeholder",
    )


# --------------------------------------------------------------------------
# C++ stub scanner
# --------------------------------------------------------------------------

_STUB_COMMENT = re.compile(r"\b(?:TODO|FIXME)\b|\bimplement", re.IGNORECASE)
_NOT_IMPL_MSG = re.compile(r"not\s+(?:yet\s+)?implemented|todo|stub", re.IGNORECASE)
_RAW_PREFIXES = frozenset({"R", "u8R", "uR", "UR", "LR"})


@dataclass(frozen=True)
class _Stripped:
    code: str         # comments, literal contents and preprocessor lines blanked
    no_comments: str  # comments and preprocessor lines blanked, literals kept
    marker_spans: tuple[tuple[int, int], ...]  # comments that held TODO/FIXME/...


@dataclass(frozen=True)
class CppFunction:
    name: str
    stub_kind: str | None  # None = real body

    @property
    def is_stub(self) -> bool:
        return self.stub_kind is not None


def _blank(chars: list[str], start: int, end: int) -> None:
    for k in range(start, end):
        if chars[k] != "\n":
            chars[k] = " "


def _token_before(src: str, i: int) -> str:
    k = i
    while k > 0 and (src[k - 1].isalnum() or src[k - 1] == "_"):
        k -= 1
    return src[k:i]


def _quoted_end(src: str, i: int, quote: str) -> int:
    """Index just past a "..." or '...' literal starting at i (stops at newline)."""
    j = i + 1
    while j < len(src):
        ch = src[j]
        if ch == "\\":
            j += 2
        elif ch == quote:
            return j + 1
        elif ch == "\n":
            return j
        else:
            j += 1
    return len(src)


def _raw_string_end(src: str, i: int) -> int | None:
    """End of R"delim(...)delim" starting at the quote, or None if malformed."""
    paren = src.find("(", i + 1, i + 18)
    if paren == -1:
        return None
    closer = ")" + src[i + 1:paren] + '"'
    end = src.find(closer, paren)
    return len(src) if end == -1 else end + len(closer)


def _comment_end(src: str, i: int) -> int:
    if src.startswith("//", i):
        end = src.find("\n", i)
        return len(src) if end == -1 else end
    end = src.find("*/", i + 2)
    return len(src) if end == -1 else end + 2


def _literal_end(src: str, i: int) -> int | None:
    """End of a string/char literal at i, or None if i does not start one."""
    ch = src[i]
    token = _token_before(src, i)
    if ch == '"':
        if token in _RAW_PREFIXES:
            raw = _raw_string_end(src, i)
            if raw is not None:
                return raw
        return _quoted_end(src, i, '"')
    if ch == "'" and not (token and token[0].isdigit()):  # skip 1'000 separators
        return _quoted_end(src, i, "'")
    return None


def _blank_preprocessor(code: list[str], nc: list[str]) -> None:
    text = "".join(code)
    pos, continuing = 0, False
    for line in text.split("\n"):
        if continuing or line.lstrip().startswith("#"):
            _blank(code, pos, pos + len(line))
            _blank(nc, pos, pos + len(line))
            continuing = line.rstrip().endswith("\\")
        pos += len(line) + 1


def strip_cpp(src: str) -> _Stripped:
    """Blank comments, literal contents and preprocessor lines, keeping offsets."""
    code, nc = list(src), list(src)
    markers: list[tuple[int, int]] = []
    i = 0
    while i < len(src):
        if src.startswith(("//", "/*"), i):
            end = _comment_end(src, i)
            if _STUB_COMMENT.search(src, i, end):
                markers.append((i, end))
            _blank(code, i, end)
            _blank(nc, i, end)
            i = end
            continue
        end = _literal_end(src, i) if src[i] in "\"'" else None
        if end is None:
            i += 1
            continue
        closed = src[end - 1] == src[i] and end - 1 > i
        _blank(code, i + 1, end - 1 if closed else end)  # keep the quotes
        i = end
    _blank_preprocessor(code, nc)
    return _Stripped("".join(code), "".join(nc), tuple(markers))


_NOT_FUNCTIONS = frozenset({
    "if", "for", "while", "switch", "catch", "return", "sizeof", "decltype",
    "noexcept", "alignas", "alignof", "throw", "static_assert", "typeid",
    "defined", "__attribute__", "__declspec", "requires", "co_return",
})
_COMPONENT = r"(?:~\s*)?[A-Za-z_]\w*(?:\s*<[^<>;{}()]*>)?"
_OPERATOR = r"operator\s*(?:\(\s*\)|\[\s*\]|[^\w\s()\[\]]+|[A-Za-z_][\w:]*\s*[*&]*)"
_NAME_AT_END = re.compile(rf"((?:{_COMPONENT}\s*::\s*)*(?:{_OPERATOR}|{_COMPONENT}))\s*$")
_TAIL_OK = re.compile(
    r"\s*(?:(?:const|volatile|override|final|mutable)\b\s*|&&\s*|&\s*"
    r"|noexcept\s*(?:\([^()]*\))?\s*|throw\s*\(\s*\)\s*|\[\[[^\]]*\]\]\s*)*"
    r"(?:->[^{};]*)?"
)
_CTOR_INIT = re.compile(r"\s*(?:noexcept\s*(?:\([^()]*\))?\s*)?:(?!:)")
_INIT_NAME = re.compile(r"\s*[A-Za-z_][\w:]*(?:\s*<[^<>{};]*>)?\s*")
_NAMESPACE = re.compile(r"\bnamespace\b|^\s*extern\s*(?:\"\s*\")?\s*$")
_ENUM = re.compile(r"\benum\b")
_CLASS_KW = re.compile(r"\b(?:class|struct|union)\b")
_STUB_RETURNS_RAW = (
    "return;", "return 0;", "return nullptr;", "return {};",
    "return false;", "return NULL;",
)


def _compact(text: str) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s*([^\w\s])\s*", r"\1", t)


_STUB_RETURNS = frozenset(_compact(s) for s in _STUB_RETURNS_RAW)


def _match_group(code: str, k: int) -> int:
    """Index of the bracket closing the ( or { at k, or -1."""
    open_ch = code[k]
    close_ch = ")" if open_ch == "(" else "}"
    depth = 0
    for j in range(k, len(code)):
        if code[j] == open_ch:
            depth += 1
        elif code[j] == close_ch:
            depth -= 1
            if depth == 0:
                return j
    return -1


def _top_level_parens(header: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    depth, start = 0, -1
    for k, ch in enumerate(header):
        if ch == "(":
            if depth == 0:
                start = k
            depth += 1
        elif ch == ")" and depth > 0:
            depth -= 1
            if depth == 0:
                spans.append((start, k))
    return spans


def _strip_template(part: str) -> str:
    return re.sub(r"<.*>$", "", part).strip()


def _last_component(name: str) -> str:
    return _strip_template(name.split("::")[-1])


def _is_macro(name: str) -> bool:
    return re.fullmatch(r"[A-Z][A-Z0-9_]+", name) is not None


def _norm_name(name: str) -> str:
    return re.sub(r"\s*(::|~)\s*", r"\1", re.sub(r"\s+", " ", name.strip()))


def _find_signature(header: str) -> tuple[str, str, int] | None:
    """(kind, name, colon_index) for a function header ending before '{'.

    kind is "func" or "ctor_init"; colon_index is only meaningful for the latter.
    """
    for o, c in _top_level_parens(header):
        m = _NAME_AT_END.search(header[:o])
        if not m:
            continue
        name = _norm_name(m.group(1))
        last = _last_component(name)
        if last in _NOT_FUNCTIONS or _is_macro(last):
            continue
        tail = header[c + 1:]
        init = _CTOR_INIT.match(tail)
        if init:
            return ("ctor_init", name, c + init.end())
        if _TAIL_OK.fullmatch(tail):
            return ("func", name, -1)
    return None


def _class_name(header: str) -> tuple[bool, str | None]:
    kws = list(_CLASS_KW.finditer(header))
    if not kws:
        return False, None
    rest = re.split(r"(?<!:):(?!:)", header[kws[-1].end():])[0]
    rest = re.sub(r"\[\[.*?\]\]|alignas\s*\([^)]*\)", " ", rest)
    words = [w for w in re.findall(r"[A-Za-z_][\w:]*", rest) if w != "final"]
    return True, (_last_component(words[-1]) if words else None)


def _is_ctor_or_dtor(name: str, cls: str | None) -> bool:
    parts = [_strip_template(p) for p in name.split("::")]
    last = parts[-1]
    if last.startswith("~"):
        return True
    if len(parts) >= 2 and last == parts[-2]:
        return True
    return cls is not None and last == cls


def _skip_ctor_init(code: str, k: int) -> int:
    """From just after a ctor's ':', return the index of its body '{', or -1."""
    while k < len(code):
        m = _INIT_NAME.match(code, k)
        if not m or m.end() >= len(code) or code[m.end()] not in "({":
            return -1
        close = _match_group(code, m.end())
        if close < 0:
            return -1
        k = close + 1
        while k < len(code) and code[k].isspace():
            k += 1
        if code.startswith("...", k):
            k += 3
            while k < len(code) and code[k].isspace():
                k += 1
        if k < len(code) and code[k] == ",":
            k += 1
            continue
        return k if k < len(code) and code[k] == "{" else -1
    return -1


def _is_not_implemented_throw(body_code: str, body_nc: str) -> bool:
    if not re.match(r"throw\b", body_code) or body_code.count(";") != 1:
        return False
    if not body_code.endswith(";"):
        return False
    literals = re.findall(r'"((?:[^"\\\n]|\\.)*)"', body_nc)
    return any(_NOT_IMPL_MSG.search(lit) for lit in literals)


def _stub_kind(s: _Stripped, o: int, c: int) -> str | None:
    """Classify the body between braces at o and c."""
    body = _compact(s.code[o + 1:c])
    if body in ("", ";"):
        has_marker = any(o < a and b <= c + 1 for a, b in s.marker_spans)
        return "todo_comment" if has_marker else "empty"
    if body in _STUB_RETURNS:
        return "trivial_return"
    if _is_not_implemented_throw(body, s.no_comments[o + 1:c]):
        return "throw_not_implemented"
    return None


class _Scanner:
    """Walks declaration scopes (namespace/class) and skips function bodies whole."""

    def __init__(self, stripped: _Stripped) -> None:
        self.s = stripped
        self.code = stripped.code
        self.n = len(self.code)
        self.stack: list[str | None] = []
        self.funcs: list[CppFunction] = []

    def run(self) -> list[CppFunction]:
        i = start = depth = 0
        while i < self.n:
            ch = self.code[i]
            if ch in "([":
                depth += 1
            elif ch in ")]":
                depth = max(0, depth - 1)
            elif ch == ";":
                depth, start = 0, i + 1
            elif ch == "}" and depth == 0:
                if self.stack:
                    self.stack.pop()
                start = i + 1
            elif ch == "{" and depth == 0:
                i = start = self._open(start, i)
                continue
            i += 1
        return self.funcs

    def _skip(self, i: int) -> int:
        close = _match_group(self.code, i)
        return self.n if close < 0 else close + 1

    def _open(self, start: int, i: int) -> int:
        header = self.code[start:i]
        if _NAMESPACE.search(header):
            self.stack.append(None)
            return i + 1
        if _ENUM.search(header):
            return self._skip(i)
        sig = _find_signature(header)
        if sig:
            return self._function(sig, start, i)
        is_cls, name = _class_name(header)
        if is_cls:
            self.stack.append(name)
            return i + 1
        return self._skip(i)  # initializer, lambda, unknown block

    def _function(self, sig: tuple[str, str, int], start: int, i: int) -> int:
        kind, name, colon = sig
        cls = self.stack[-1] if self.stack else None
        if kind == "ctor_init":
            body = _skip_ctor_init(self.code, start + colon + 1)
            return self._skip(body if body >= 0 else i)
        if _is_ctor_or_dtor(name, cls):
            return self._skip(i)
        close = _match_group(self.code, i)
        if close < 0:
            return self.n
        display = name if "::" in name or cls is None else f"{cls}::{name}"
        self.funcs.append(CppFunction(display, _stub_kind(self.s, i, close)))
        return close + 1


def find_cpp_functions(src: str) -> list[CppFunction]:
    """Function definitions in C++ source, excluding ctors and dtors."""
    return _Scanner(strip_cpp(src)).run()


def _unique(names: list[str]) -> list[str]:
    return list(dict.fromkeys(names))


def new_stub_names(old_src: str, new_src: str) -> list[str]:
    """Names of stubs that ``new_src`` introduces relative to ``old_src``.

    Fails only if new has more stubs than old, or a name that was a real
    function in old is now a stub.
    """
    old = find_cpp_functions(old_src) if old_src else []
    new = find_cpp_functions(new_src)
    old_stub = Counter(f.name for f in old if f.is_stub)
    new_stub = Counter(f.name for f in new if f.is_stub)
    old_real = {f.name for f in old if not f.is_stub}
    if sum(new_stub.values()) > sum(old_stub.values()):
        return _unique(list((new_stub - old_stub).elements()))
    return [n for n in new_stub if n in old_real and new_stub[n] > old_stub[n]]


# --------------------------------------------------------------------------
# orchestration
# --------------------------------------------------------------------------

def _guarded(path: str | None, fn: Callable[..., SanityFailure | None],
             *args: object) -> SanityFailure | None:
    try:
        return fn(*args)
    except Exception as e:  # noqa: BLE001 - a check must never crash the loop
        return SanityFailure(
            "internal_error", path,
            f"sanity check {getattr(fn, '__name__', fn)} crashed "
            f"({type(e).__name__}: {e}) — regenerate the patch",
        )


def _check_file(fop: FileOp, root: Path, cfg: IocConfig) -> list[SanityFailure]:
    unsafe = _guarded(fop.path, check_unsafe_path, fop, root, cfg)
    if unsafe:
        return [unsafe]
    target = safe_resolve(root, fop.path, list(cfg.exclude))
    out = [
        _guarded(fop.path, check_create_existing, fop, target),
        _guarded(fop.path, check_missing_target, fop, target),
        _guarded(fop.path, check_binary_file, fop, target),
    ]
    old = read_current(target) if fop.op == "modify" else None
    out += [
        _guarded(fop.path, check_retrieval_markers, fop, old),
        _guarded(fop.path, check_emptied_file, fop, old),
        _guarded(fop.path, check_excessive_shrink, fop, old, cfg),
        _guarded(fop.path, check_noop_modify, fop, old),
        _guarded(fop.path, check_stub_body, fop, old),
        _guarded(fop.path, check_invalid_yaml, fop),
    ]
    return [f for f in out if f is not None]


def run_sanity(patch: Patch, root: Path, cfg: IocConfig) -> list[SanityFailure]:
    """Run every check and return all failures; an empty list means pass."""
    failures: list[SanityFailure] = []
    first = _guarded(None, check_too_many_files, patch, cfg)
    if first:
        failures.append(first)
    for fop in patch.files:
        try:
            failures.extend(_check_file(fop, Path(root), cfg))
        except Exception as e:  # noqa: BLE001 - e.g. OSError while reading
            path = getattr(fop, "path", None)
            failures.append(SanityFailure(
                "internal_error", path,
                f"could not check this file ({type(e).__name__}: {e}) — "
                "regenerate the patch with a valid path",
            ))
    return failures


def format_feedback(failures: list[SanityFailure]) -> str:
    """Render failures as a compact bullet list for the retry prompt."""
    lines = []
    for f in failures:
        where = f" {f.path}:" if f.path else ""
        lines.append(f"- [{f.check}]{where} {f.reason}")
    return "\n".join(lines)