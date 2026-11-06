"""Structured patch format: {summary, files: [{path, op, content}]}."""
from __future__ import annotations

import json
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError, model_validator


class PatchParseError(Exception):
    pass


class FileOp(BaseModel):
    path: str = Field(min_length=1)
    op: Literal["create", "modify", "delete"]
    content: Optional[str] = None

    @model_validator(mode="after")
    def _content_rules(self) -> "FileOp":
        if self.op in ("create", "modify") and self.content is None:
            raise ValueError(f"{self.op} on {self.path} requires content")
        if self.op == "delete":
            self.content = None
        return self


class Patch(BaseModel):
    summary: str = Field(min_length=1)
    files: list[FileOp] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_paths(self) -> "Patch":
        seen = set()
        for f in self.files:
            key = f.path.strip().replace("\\", "/").lstrip("./")
            if key in seen:
                raise ValueError(f"duplicate path in patch: {f.path}")
            seen.add(key)
        return self


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def _first_json_object(text: str) -> str:
    """Return the first balanced {...} block, string-aware."""
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            c = text[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        start = text.find("{", start + 1)
    raise PatchParseError("no JSON object found in model output")


def parse_patch(raw: str) -> Patch:
    """Parse LLM output into a Patch. Tolerates code fences and chatter."""
    if not raw or not raw.strip():
        raise PatchParseError("empty model output")
    m = _FENCE.search(raw)
    body = m.group(1) if m else raw
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        try:
            data = json.loads(_first_json_object(body))
        except json.JSONDecodeError as e:
            raise PatchParseError(f"invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise PatchParseError("patch must be a JSON object")
    try:
        return Patch.model_validate(data)
    except ValidationError as e:
        raise PatchParseError(f"schema error: {e}") from e