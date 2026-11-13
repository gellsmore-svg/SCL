"""Skill discovery, then verification, then execution."""

from __future__ import annotations

import re
from pathlib import Path

from scl.findings import Finding

FIELDS = ("ID", "Name", "Purpose", "Criticality", "Verification")
CRITICALITY = {"critical", "required", "optional"}


def parse_skills(text: str) -> list[dict[str, str]]:
    skills = []
    for block in re.split(r"\n(?=## )", text):
        if not block.startswith("## "):
            continue
        fields: dict[str, str] = {}
        for line in block.splitlines():
            if line.startswith("- ") and ": " in line:
                key, value = line[2:].split(": ", 1)
                fields[key] = value.strip()
        if fields:
            skills.append(fields)
    return skills


def load_skills(root: Path) -> tuple[list[dict[str, str]], list[Finding]]:
    path = root / "meta" / "required-skills.md"
    if not path.is_file():
        return [], [Finding("skills.registry", "missing meta/required-skills.md")]
    skills = parse_skills(path.read_text(encoding="utf-8"))
    findings: list[Finding] = []
    if not skills:
        findings.append(Finding("skills.registry", "skills registry has no entries"))
    for skill in skills:
        record_id = skill.get("ID", "?")
        missing = [field for field in FIELDS if not skill.get(field)]
        if missing:
            findings.append(Finding("skills.registry", f"missing {', '.join(missing)}", record_id))
        if skill.get("Criticality") not in CRITICALITY:
            findings.append(Finding("skills.registry", "Criticality must be critical, required, or optional", record_id))
    return skills, findings


def verify_skills(root: Path) -> tuple[list[Finding], bool]:
    """Return findings and whether execution must stop.

    A missing or malformed registry is a discovery failure. A known critical
    skill whose file is absent is a different halt.
    """
    skills, findings = load_skills(root)
    halt = any(finding.rule == "skills.registry" for finding in findings)
    for skill in skills:
        verification = skill.get("Verification", "")
        record_id = skill.get("ID", "")
        if not verification.startswith("file:"):
            findings.append(Finding("skills.missing", "Verification must be a file: path", record_id))
            if skill.get("Criticality") == "critical":
                halt = True
            continue
        relative = verification[len("file:") :]
        path = root / relative
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        name = skill.get("Name", "")
        ok = bool(text) and f"name: {name}" in text
        if ok:
            continue
        action = f"Restore {relative} so it declares name: {name}, then rerun."
        findings.append(
            Finding(
                "skills.missing",
                f"FAIL skill: {name}; impact: {skill.get('Purpose', '')}; action: {action}",
                record_id,
            )
        )
        if skill.get("Criticality") == "critical":
            halt = True
    return findings, halt
