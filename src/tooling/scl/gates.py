"""Behaviour checks for implemented requirements.

Framework and structural rules enforce the rest. Planned requirements are
recorded in the model and are not in this set.
"""

from __future__ import annotations

from pathlib import Path

from scl.findings import Finding
from scl.gap import potential_model_gap
from scl.interpreter import Boundary, failures
from scl.model import Loaded, contained_path
from scl.questions import influence_findings, parse_questions, question_findings, questions_path

# requirement id -> framework or structural rule that enforces it.
RULE_COVERAGE = {
    "requirement-versioned": "framework.release-version",
    "requirement-change-docs": "framework.change-docs",
    "requirement-reproducible": "framework.reproducible",
    "requirement-self-contained": "framework.self-contained",
    "requirement-repository-structure": "framework.structure",
    "requirement-validation-instructions": "framework.validation-instructions",
    "requirement-consistency-validation": "framework.suite",
    "requirement-refines-discipline-enforced": "refines.discipline",
    "requirement-upgrade-instructions": "framework.upgrade-guide",
    "requirement-consumer-impact-test": "framework.consumer-impact",
    "requirement-lifecycle-four-steps": "framework.lifecycle",
    "requirement-ai-test-before-release": "framework.ai-test",
}


def behavior_findings(root: Path, loaded: Loaded) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(_capture_why(loaded))
    findings.extend(_persistent(root, loaded))
    findings.extend(_gap())
    findings.extend(_human_authored(loaded))
    findings.extend(_eligibility_examples())
    findings.extend(_version_discovery(root))
    findings.extend(_interpreter())
    findings.extend(question_findings(root))
    findings.extend(_influence(root))
    findings.extend(_narrative_contract(loaded))
    return findings


def implemented_ids() -> set[str]:
    return set(RULE_COVERAGE) | set(BEHAVIOR_IDS)


BEHAVIOR_IDS = {
    "requirement-release-eligibility",
    "requirement-model-is-source-of-truth",
    "requirement-version-discovery",
    "requirement-capture-why",
    "requirement-context-persistent-inspectable",
    "requirement-raise-gap-challenge",
    "requirement-support-human-authored-mode",
    "requirement-support-ai-inferred-mode",
    "requirement-expose-ai-understanding",
    "requirement-narrative-per-role",
    "requirement-narrative-role-scope",
    "requirement-narrative-human-constraint-budget",
    "requirement-narrative-traceable",
    "requirement-narrative-flag-manual-eval",
    "requirement-open-questions-central",
    "requirement-open-question-fields",
    "requirement-open-question-influence",
    "requirement-skills-registry",
    "requirement-verify-skills-before-ops",
    "requirement-interpreter-honours-layers",
    "requirement-no-expressiveness-penalty",
}


def _capture_why(loaded: Loaded) -> list[Finding]:
    intents = [node for node in loaded.nodes if node["type"] == "Intent"]
    outcomes = [node for node in loaded.nodes if node["type"] == "Outcome"]
    if not intents or not outcomes:
        return [Finding("trace.coverage", "model needs at least one Intent and one Outcome", "requirement-capture-why")]
    return []


def _persistent(root: Path, loaded: Loaded) -> list[Finding]:
    findings = []
    for source in loaded.sources:
        if not isinstance(source, dict):
            continue
        path = source.get("path")
        if isinstance(path, str) and contained_path(root, path) is None:
            findings.append(
                Finding("context.external", "declared source path escapes the repository", str(source.get("alias") or ""))
            )
    for node in loaded.nodes:
        if not isinstance(node, dict):
            continue
        evidence = (node.get("metadata") or {}).get("evidence") or []
        if not isinstance(evidence, list):
            continue
        record_id = str(node.get("id") or "")
        for item in evidence:
            if not isinstance(item, str):
                continue
            _alias, _sep, rest = item.partition(":")
            path = rest.split("#", 1)[0]
            resolved = contained_path(root, path)
            if resolved is None:
                findings.append(Finding("context.external", "evidence points outside the repository", record_id))
            elif not resolved.is_file():
                findings.append(Finding("context.external", "evidence file is not in the repository", record_id))
    return findings


def _gap() -> list[Finding]:
    text = potential_model_gap(
        "No interaction is recorded for a suspected handoff.",
        "Adding one would invent a fact.",
        "The handoff may belong to an existing model, or it may be out of scope.",
        "Which existing model, if any, should own it?",
    )
    needed = ("POTENTIAL MODEL GAP", "Observation:", "Concern:", "Possibilities:", "Question:")
    if any(part not in text for part in needed):
        return [Finding("gap.challenge", "gap challenge is missing a required part")]
    return []


def _human_authored(loaded: Loaded) -> list[Finding]:
    findings = []
    for node in loaded.nodes:
        basis = (node.get("metadata") or {}).get("basis")
        if basis == "inferred":
            findings.append(Finding("author.invented", "integrated model contains an inferred record", node["id"]))
    return findings


def _eligibility_examples() -> list[Finding]:
    from scl.framework import release_eligible

    consumer = ["src/schemas/project-manifest.schema.json", "changelog/CHANGELOG.md"]
    internal = ["meta/open-questions.md", "changelog/CHANGELOG.md"]
    other = ["tests/test_scl.py"]
    if not release_eligible(consumer):
        return [Finding("release.eligibility", "a schema change must be eligible for release")]
    if release_eligible(internal) or release_eligible(other):
        return [Finding("release.eligibility", "internal-only or test-only changes must not cut a release")]
    return []


def _version_discovery(root: Path) -> list[Finding]:
    import json

    from scl.manifest import validate_manifest

    schema = root / "src" / "schemas" / "project-manifest.schema.json"
    example = root / "src" / "examples" / "project-manifest.json"
    if not schema.is_file() or not example.is_file():
        return [Finding("manifest.discovery", "project manifest schema or example is missing")]
    data = json.loads(example.read_text(encoding="utf-8"))
    errors = validate_manifest(json.loads(schema.read_text(encoding="utf-8")), data)
    if errors:
        return [Finding("manifest.discovery", "; ".join(errors))]
    for key in ("iomrVersion", "modelLocation", "upgradeEligibility"):
        if key not in data:
            return [Finding("manifest.discovery", f"example manifest is missing {key}")]
    return []


def _interpreter() -> list[Finding]:
    boundary = Boundary("requirement-no-expressiveness-penalty", "breaks_shall", True)
    novel = {"novel_route": "unfamiliar-but-conformant", "note": "not a known pattern"}
    broken = {"novel_route": "unfamiliar-but-conformant", "breaks_shall": True}
    if failures(novel, [boundary]):
        return [Finding("interpreter.penalty", "a conformant unfamiliar solution was failed")]
    if failures(broken, [boundary]) != ["requirement-no-expressiveness-penalty"]:
        return [Finding("interpreter.boundary", "a real boundary violation was not failed")]
    return []


def _influence(root: Path) -> list[Finding]:
    path = questions_path(root)
    if not path.is_file():
        return []
    questions = parse_questions(path.read_text(encoding="utf-8"))
    findings = []
    for candidate in (root / "docs").glob("recommendations*.md"):
        findings.extend(influence_findings(candidate.read_text(encoding="utf-8"), questions))
    return findings


def _narrative_contract(loaded: Loaded) -> list[Finding]:
    from scl.narrative import render_role

    findings = []
    requirement_ids = {node["id"] for node in loaded.nodes if node["type"] == "Requirement"}
    seen = set()
    for role in ("developer", "tester", "power-user"):
        main, appendix = render_role(loaded, role)
        combined = main + (appendix or "")
        if f"**Reader:** {role}." not in main or "**Next step:**" not in main:
            findings.append(Finding("narrative.role", f"{role} narrative does not name the reader and next step"))
        if "Human-constraint budget:" not in main or "cognitive load" not in main:
            findings.append(Finding("narrative.budget", f"{role} narrative does not record the budget"))
        if "⚖" not in combined:
            findings.append(Finding("narrative.flag", f"{role} narrative drops human-judgement markers"))
        for record_id in requirement_ids:
            if record_id in combined:
                seen.add(record_id)
        if role == "power-user" and "SemVer" in combined:
            findings.append(Finding("narrative.scope", "power-user narrative uses technical release language"))
        if role == "developer":
            for model in loaded.nodes:
                if model.get("type") != "Model":
                    continue
                status = model.get("status") or "unspecified"
                gaps = str((model.get("metadata") or {}).get("gaps") or "").strip()
                if status not in {"partial", "planned"} and not gaps:
                    continue
                status_line = f"Model status: {status}."
                identity = f"`{model['id']}` is {status}"
                if status_line not in combined and identity not in combined:
                    findings.append(
                        Finding("narrative.gap", f"developer narrative hides the status of {model['id']}", model["id"])
                    )
                if gaps and gaps not in combined:
                    findings.append(
                        Finding("narrative.gap", f"developer narrative hides the gap on {model['id']}", model["id"])
                    )
            missing = sorted(requirement_ids - {record_id for record_id in requirement_ids if record_id in combined})
            if missing:
                findings.append(Finding("narrative.trace", f"developer narrative omits {', '.join(missing[:5])}"))
    return findings
