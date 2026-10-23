"""The single open-question list."""

from __future__ import annotations

import re
from pathlib import Path

from scl.findings import Finding

FIELDS = (
    "ID",
    "Question",
    "Context",
    "Raised by",
    "Date raised",
    "Status",
    "Risk Level",
    "Owner",
    "Blocks",
    "Resolution",
    "Evidence",
)
RISK_LEVELS = {"Critical", "High", "Medium", "Low", "Informational"}
HOT = {"Critical", "High"}


def questions_path(root: Path) -> Path:
    return root / "meta" / "open-questions.md"


def parse_questions(text: str) -> list[dict[str, str]]:
    questions = []
    for block in re.split(r"\n(?=## )", text):
        if not block.startswith("## "):
            continue
        fields: dict[str, str] = {}
        for line in block.splitlines():
            if line.startswith("- ") and ": " in line:
                key, value = line[2:].split(": ", 1)
                fields[key] = value.strip()
        if fields:
            questions.append(fields)
    return questions


def question_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    lists = sorted(root.rglob("open-questions*.md"))
    canonical = questions_path(root)
    extras = [path for path in lists if path.resolve() != canonical.resolve()]
    if extras:
        names = ", ".join(str(path.relative_to(root)) for path in extras)
        findings.append(Finding("questions.central", f"open questions also listed in {names}"))
    if not canonical.is_file():
        findings.append(Finding("questions.fields", "missing meta/open-questions.md"))
        return findings
    for question in parse_questions(canonical.read_text(encoding="utf-8")):
        record_id = question.get("ID", "?")
        missing = [field for field in FIELDS if not question.get(field)]
        if missing:
            findings.append(Finding("questions.fields", f"missing {', '.join(missing)}", record_id))
        if question.get("Risk Level") not in RISK_LEVELS:
            findings.append(Finding("questions.fields", "Risk Level is not in the allowed set", record_id))
    return findings


def influence_findings(text: str, questions: list[dict[str, str]]) -> list[Finding]:
    """A recommendation that depends on an open High/Critical question must name it."""
    if "recommendation" not in text.lower() or "depend" not in text.lower():
        return []
    hot = [
        question
        for question in questions
        if question.get("Risk Level") in HOT and question.get("Status", "").lower() not in {"resolved", "closed"}
    ]
    named = [question for question in hot if question.get("ID") and question["ID"] in text]
    if not named:
        return [
            Finding(
                "questions.influence",
                "recommendation depends on an unresolved High/Critical question but does not name it",
            )
        ]
    findings = []
    for question in named:
        if question["Risk Level"] not in text or "may change" not in text.lower():
            findings.append(
                Finding(
                    "questions.influence",
                    "recommendation must name the risk and state that results may change once resolved",
                    question.get("ID", ""),
                )
            )
    return findings
