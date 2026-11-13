"""Tag parsing and dimension classification (GRAMMAR.md §tags, SPEC §7)."""

from __future__ import annotations

import re

_TAG_RE = re.compile(r"\[([^\]]+)\]")

ACTORS = frozenset({"LLM", "HUMAN", "CODE", "EXTERNAL"})
DETERMINISM = frozenset({"DETERMINISTIC", "STOCHASTIC"})
TIMING = frozenset({"SYNC", "ASYNC"})
EFFECT = frozenset({"PURE", "SIDE-EFFECT", "IDEMPOTENT"})
CONTROL = frozenset({"BLOCKING", "GATED", "CACHED", "BATCH"})
DIMENSIONS = ("actor", "determinism", "timing", "effect", "control", "domain")

DOMAIN = frozenset({
    "EMOTIONAL", "COGNITIVE", "APPRAISAL", "REGULATION", "MOTIVATIONAL",
    "METACOGNITIVE", "BEHAVIORAL",
    "TRANSDIAGNOSTIC", "INTERPERSONAL", "AVOIDANT",
    "LEADERSHIP", "STRATEGIC", "CULTURAL", "POWER", "STAKEHOLDER",
    "STRUCTURAL", "ALIGNMENT", "RESISTANCE",
    "SOCIAL", "GROUP", "NORM", "ROLE", "SYMBOLIC",
    "HEURISTIC", "FRAMED", "NUDGED",
    "INCENTIVE", "COMMON_KNOWLEDGE", "RECIPROCAL",
    "INTERACTIVE", "OVERLOAD", "DISCOVERABLE",
})
_RESERVED_PREFIXES = ACTORS | DETERMINISM | TIMING | EFFECT | CONTROL | DOMAIN


def split_tag_list(raw: str) -> list[str]:
    """Split comma-separated tag content, respecting ASSISTED-BY / SATISFIES spans."""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    for char in raw:
        if char == "[":
            depth += 1
            buf.append(char)
        elif char == "]":
            depth = max(0, depth - 1)
            buf.append(char)
        elif char == "," and depth == 0:
            piece = "".join(buf).strip()
            if piece:
                parts.append(piece)
            buf = []
        else:
            buf.append(char)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def extract_bracket_tags(text: str) -> tuple[str, list[str]]:
    tags = _TAG_RE.findall(text)
    cleaned = _TAG_RE.sub("", text).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned, tags


def classify_tag(tag: str) -> tuple[str | None, str]:
    """Return (dimension, normalized_tag) or (None, tag) for custom/structured tags."""
    upper = tag.strip()
    if upper.upper().startswith("ASSISTED-BY:"):
        return "assisted_by", upper
    if upper.upper().startswith("SATISFIES:"):
        return "satisfies", upper
    if ":" in upper and not upper.upper().startswith(("LLM:", "HUMAN:", "CODE:", "EXTERNAL:")):
        ns, _ = upper.split(":", 1)
        if ns and ns[0].isalpha() and ns.isidentifier() is False:
            # namespace:word custom tag
            if re.match(r"^[A-Za-z][\w-]*:\S+", upper):
                return "custom", upper
        if re.match(r"^[a-z][\w-]*:\S+", upper):
            return "custom", upper

    token = upper.split("[", 1)[0].strip()
    if ":" in token and token.split(":", 1)[0] in ACTORS:
        return "actor", upper
    root = token.split(":", 1)[0].upper()
    if root in ACTORS:
        return "actor", upper
    if root in DETERMINISM:
        return "determinism", upper
    if root in TIMING:
        return "timing", upper
    if root in EFFECT:
        return "effect", upper
    if root in CONTROL:
        return "control", upper
    if root in DOMAIN:
        return "domain", upper
    if re.match(r"^[a-z][\w-]*:\S+", upper):
        return "custom", upper
    return None, upper


def tag_dimensions(tags: list[str]) -> dict[str, list[str]]:
    dims: dict[str, list[str]] = {}
    for bracket in tags:
        for piece in split_tag_list(bracket):
            dim, norm = classify_tag(piece)
            if dim:
                dims.setdefault(dim, []).append(norm)
    return dims


def has_llm_actor(tags: list[str]) -> bool:
    for bracket in tags:
        for piece in split_tag_list(bracket):
            root = piece.split(":", 1)[0].strip().upper()
            if root == "LLM":
                return True
            if piece.upper().startswith("ASSISTED-BY:"):
                if "LLM" in piece.upper():
                    return True
    return False


def modifier_keys(modifiers: list[str]) -> set[str]:
    keys: set[str] = set()
    for mod in modifiers:
        for part in mod.split(";"):
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                keys.add(part.split(":", 1)[0].strip().upper())
            else:
                keys.add(part.upper())
    return keys