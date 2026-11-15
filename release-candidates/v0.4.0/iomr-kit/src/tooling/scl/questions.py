"""The single open-question list."""

from __future__ import annotations

import re
from pathlib import Path

from scl.contracts import ServiceError
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


def next_question_id(existing: list[dict[str, str]]) -> str:
    numbers = []
    for question in existing:
        match = re.fullmatch(r"OQ-(\d+)", question.get("ID", ""))
        if match:
            numbers.append(int(match.group(1)))
    return f"OQ-{(max(numbers) if numbers else 0) + 1:03d}"


def normalize_question(question: dict, existing: list[dict[str, str]]) -> dict[str, str]:
    """Fill the register identity and reject a question that cannot be listed."""
    if not isinstance(question, dict):
        raise ServiceError("questions.fields", "Question must be an object.")
    item = {field: str(question.get(field, "")).strip() for field in FIELDS}
    if any("\n" in value or "\r" in value for value in item.values()):
        raise ServiceError("questions.fields", "Question fields must be single lines.", item.get("ID", ""))
    if not item["ID"]:
        item["ID"] = next_question_id(existing)
    if re.fullmatch(r"OQ-[0-9]{3,}", item["ID"]) is None:
        raise ServiceError("questions.fields", "Question ID must look like OQ-001.", item["ID"])
    if any(other.get("ID") == item["ID"] for other in existing):
        raise ServiceError("questions.fields", "Question ID already exists; update it.", item["ID"])
    if not item["Status"]:
        item["Status"] = "open"
    if not item["Resolution"]:
        item["Resolution"] = "unresolved"
    missing = [field for field in FIELDS if not item[field]]
    if missing:
        raise ServiceError("questions.fields", f"missing {', '.join(missing)}", item["ID"])
    if item["Risk Level"] not in RISK_LEVELS:
        raise ServiceError("questions.fields", "Risk Level is not in the allowed set", item["ID"])
    return item


def render_questions(questions: list[dict[str, str]]) -> str:
    lines = [
        "# Open questions",
        "",
        "This is the only independent list. Refer to a question by its ID.",
        "",
    ]
    for question in questions:
        lines.append(f"## {question['ID']}")
        lines.append("")
        for field in FIELDS:
            lines.append(f"- {field}: {question[field]}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


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


def _unresolved_hot(questions: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        question
        for question in questions
        if question.get("Risk Level") in HOT and question.get("Status", "").lower() not in {"resolved", "closed"}
    ]


def influence_findings(text: str, questions: list[dict[str, str]]) -> list[Finding]:
    """A recommendation that names an unresolved High/Critical question must show the risk.

    The word "depend" is not itself a dependency. Resolved questions do not escalate.
    """
    if "recommendation" not in text.lower():
        return []
    findings = []
    for question in _unresolved_hot(questions):
        record_id = question.get("ID") or ""
        if not record_id or record_id not in text:
            continue
        if question.get("Risk Level") not in text or "may change" not in text.lower():
            findings.append(
                Finding(
                    "questions.influence",
                    "recommendation must name the risk and state that results may change once resolved",
                    record_id,
                )
            )
    return findings
