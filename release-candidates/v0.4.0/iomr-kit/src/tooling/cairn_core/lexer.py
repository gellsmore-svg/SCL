"""Line-based lexer with indentation tracking for Cairn grammar."""

from __future__ import annotations

import re
from dataclasses import dataclass

_BLANK = re.compile(r"^\s*$")
_COMMENT = re.compile(r"^\s*#")
_RENDER_PROFILE = re.compile(r"^render-profile:\s*(\S+)\s*$", re.I)


@dataclass(frozen=True)
class Line:
    lineno: int
    indent: int
    text: str
    raw: str


def _indent_of(raw: str) -> int:
    expanded = raw.replace("\t", "    ")
    return len(expanded) - len(expanded.lstrip(" "))


def tokenize_lines(text: str) -> list[Line]:
    """Split *text* into non-blank, non-comment lines with indentation."""
    lines: list[Line] = []
    for index, raw in enumerate(text.splitlines(), start=1):
        if _BLANK.match(raw) or _COMMENT.match(raw):
            continue
        indent = _indent_of(raw)
        content = raw[ len(raw) - len(raw.lstrip(" \t")) :].strip()
        if content:
            lines.append(Line(lineno=index, indent=indent, text=content, raw=raw))
    return lines


def is_render_profile(line: Line) -> str | None:
    match = _RENDER_PROFILE.match(line.text)
    return match.group(1) if match else None