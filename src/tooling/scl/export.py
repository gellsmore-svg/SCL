"""Write generated artifacts. The model wins when they disagree."""

from __future__ import annotations

from pathlib import Path

from scl.findings import Finding
from scl.model import Loaded
from scl.narrative import render_role, traceability

ROLES = ("developer", "tester", "power-user")


def generated_texts(loaded: Loaded) -> dict[str, str]:
    texts = {"TRACEABILITY.md": traceability(loaded)}
    for role in ROLES:
        main, appendix = render_role(loaded, role)
        texts[f"docs/REQUIREMENTS-{role}.md"] = main
        if appendix:
            texts[f"docs/REQUIREMENTS-{role}-appendix.md"] = appendix
    return texts


def write_generated(root: Path, loaded: Loaded) -> dict[str, str]:
    texts = generated_texts(loaded)
    for relative, text in texts.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    for role in ROLES:
        appendix = root / f"docs/REQUIREMENTS-{role}-appendix.md"
        if appendix.is_file() and f"docs/REQUIREMENTS-{role}-appendix.md" not in texts:
            appendix.unlink()
    return texts


def generated_findings(root: Path, loaded: Loaded) -> list[Finding]:
    expected = generated_texts(loaded)
    findings = []
    for relative, text in expected.items():
        path = root / relative
        if not path.is_file():
            findings.append(Finding("model.source", f"missing generated {relative}"))
            continue
        if path.read_text(encoding="utf-8") != text:
            findings.append(Finding("model.source", f"{relative} does not match the model; regenerate it"))
    return findings
