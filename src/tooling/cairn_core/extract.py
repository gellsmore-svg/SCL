"""Extract Cairn skeleton text from markdown wrappers (.cairn.md)."""

from __future__ import annotations

import re

_SECTION = re.compile(r"^##\s+(.+)$")
_FENCE = re.compile(r"^```(?:\w*)?\s*$")
_CONTEXT_BULLET = re.compile(r"^-\s+\*\*(.+?)\*\*\s+[—–-]\s+(.+)$")


def _section_keyword(section: str) -> str | None:
    lower = section.lower()
    if lower.startswith("context"):
        return "CONTEXT"
    if lower.startswith("requirements"):
        return "REQUIREMENTS"
    if lower.startswith("outcomes"):
        return "OUTCOMES"
    if lower.startswith("plan"):
        return "PLAN"
    if "process" in lower:
        return "PROCESS"
    return None


def _markdown_context_lines(lines: list[str]) -> list[str]:
    out: list[str] = ["CONTEXT"]
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        bullet = _CONTEXT_BULLET.match(stripped)
        if bullet:
            out.append(f"{bullet.group(1)} — {bullet.group(2)}")
        elif stripped.startswith("- "):
            out.append(stripped[2:].strip())
        elif out and out[-1] != "CONTEXT" and not _is_block_keyword(stripped):
            out[-1] = f"{out[-1]} {stripped}"
        else:
            out.append(stripped)
    return out


def _is_block_keyword(line: str) -> bool:
    upper = line.upper()
    return upper in {"CONTEXT", "OUTCOMES", "REQUIREMENTS"} or upper.startswith(
        ("PLAN ", "PROCESS ")
    )


def _outcomes_lines(lines: list[str]) -> list[str]:
    out: list[str] = ["OUTCOMES"]
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "---":
            continue
        out.append(stripped)
    return out


def _plan_lines(lines: list[str]) -> list[str]:
    """Keep PLAN skeleton lines; drop pure markdown chrome."""
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        out.append(line.rstrip())
    return out


def extract_cairn_source(text: str) -> tuple[str, str]:
    """Return (cairn_source, source_kind) where kind is ``markdown`` or ``cairn``."""
    if "## " not in text and "```" not in text:
        return text.strip(), "cairn"

    lines = text.splitlines()
    blocks: list[str] = []
    section_key: str | None = None
    in_fence = False
    fence_buf: list[str] = []
    prose_buf: list[str] | None = None

    def flush_prose() -> None:
        nonlocal prose_buf
        if prose_buf is None:
            return
        if section_key == "CONTEXT":
            blocks.append("\n".join(_markdown_context_lines(prose_buf)))
        elif section_key == "OUTCOMES":
            blocks.append("\n".join(_outcomes_lines(prose_buf)))
        elif section_key == "PLAN":
            plan_body = _plan_lines(prose_buf)
            if plan_body:
                blocks.append("\n".join(plan_body))
        prose_buf = None

    for line in lines:
        sec = _SECTION.match(line)
        if sec:
            flush_prose()
            section_key = _section_keyword(sec.group(1).strip())
            if section_key in {"CONTEXT", "OUTCOMES", "PLAN"}:
                prose_buf = []
            else:
                prose_buf = None
            continue

        if _FENCE.match(line.strip()):
            if in_fence:
                if fence_buf:
                    header = section_key or ""
                    # PROCESS/PLAN fences already carry their own header line.
                    if header in {"PROCESS", "PLAN"}:
                        blocks.append("\n".join(fence_buf))
                    elif header:
                        blocks.append(header + "\n" + "\n".join(fence_buf))
                    else:
                        blocks.append("\n".join(fence_buf))
                fence_buf = []
                in_fence = False
            else:
                in_fence = True
            continue

        if in_fence:
            fence_buf.append(line)
        elif prose_buf is not None:
            prose_buf.append(line)

    flush_prose()
    if fence_buf:
        header = section_key or ""
        if header in {"PROCESS", "PLAN"}:
            blocks.append("\n".join(fence_buf))
        elif header:
            blocks.append(header + "\n" + "\n".join(fence_buf))
        else:
            blocks.append("\n".join(fence_buf))

    if not blocks:
        return text.strip(), "cairn"
    return "\n\n".join(blocks).strip(), "markdown"
