"""SCL command line. `imk` is the same entry, which the IOMR contract names."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scl.cairn import CairnUnavailable, check_text, propose_cairn, render_cairn
from scl.export import generated_findings, write_generated
from scl.findings import Finding
from scl.framework import framework_findings, release_eligible
from scl.gap import potential_model_gap
from scl.gates import behavior_findings
from scl.model import find_root, load_model, structural_findings
from scl.narrative import mermaid_sequence, mermaid_trace, render_role, traceability
from scl.skills import verify_skills
from scl.slice import proposal_findings


def _skill_halt(findings: list[Finding]) -> int:
    for finding in findings:
        print(finding.message)
    if any(finding.rule == "skills.registry" for finding in findings):
        print("errors: skill discovery failed")
    else:
        print("errors: critical skill missing")
    return 2


def validate(root: Path, strict: bool, proposals: bool = False) -> int:
    skill_findings, halt = verify_skills(root)
    if halt:
        return _skill_halt(skill_findings)
    findings: list[Finding] = []
    if strict:
        loaded = load_model(root)
        findings.extend(skill_findings)
        findings.extend(structural_findings(loaded))
        findings.extend(framework_findings(root))
        findings.extend(behavior_findings(root, loaded))
        findings.extend(generated_findings(root, loaded))
        findings.extend(proposal_findings(root))
    else:
        findings.extend(framework_findings(root))
        if proposals:
            findings.extend(proposal_findings(root))
    if findings:
        for finding in findings:
            print(finding.format())
        print(f"errors: {len(findings)}")
        return 1
    print("VALID")
    print("errors: 0")
    return 0


def _write_text(text: str, output: str | None) -> None:
    if output:
        Path(output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def _export(root: Path, args: argparse.Namespace) -> int:
    """Render in memory. stdout and -o are the only destinations."""
    loaded = load_model(root, include_slices=bool(args.include_slices))
    if args.kind == "markdown":
        _write_text(traceability(loaded), args.output)
        return 0
    if args.kind == "json":
        payload = {"nodes": loaded.nodes, "relationships": loaded.relationships}
        _write_text(json.dumps(payload, indent=2) + "\n", args.output)
        return 0
    if args.kind == "cairn":
        _write_text(render_cairn(loaded), args.output)
        return 0
    if args.kind == "narrative":
        text, _appendix = render_role(loaded, args.role)
        _write_text(text, args.output)
        return 0
    if args.kind == "mermaid":
        view = args.view or ""
        if view.startswith("trace:"):
            text = mermaid_trace(loaded, view.split(":", 1)[1])
        elif view.startswith("sequence:"):
            text = mermaid_sequence(loaded, view.split(":", 1)[1])
        else:
            print("mermaid needs --view trace:<intent-id> or --view sequence:<model-id>", file=sys.stderr)
            return 1
        _write_text(text, args.output)
        return 0
    print(f"unknown export {args.kind}", file=sys.stderr)
    return 1


def regenerate(root: Path) -> int:
    """Rewrite the generated documents after the model itself is valid."""
    loaded = load_model(root)
    problems = structural_findings(loaded)
    if problems:
        for finding in problems:
            print(finding.format())
        print(f"errors: {len(problems)}")
        return 1
    texts = write_generated(root, loaded)
    for relative in texts:
        print(relative)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scl")
    parser.add_argument("--root", type=Path, default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)

    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("--strict", action="store_true")
    validate_parser.add_argument("--proposals", action="store_true")

    export_parser = sub.add_parser("export")
    export_parser.add_argument("kind", choices=("markdown", "json", "mermaid", "narrative", "cairn"))
    export_parser.add_argument("-o", "--output")
    export_parser.add_argument("--view")
    export_parser.add_argument("--role", default="developer")
    export_parser.add_argument("--include-slices", action="store_true")

    api_parser = sub.add_parser("api", help="Structured model service operations")
    from scl.service import OPERATIONS
    api_parser.add_argument("operation", choices=sorted(OPERATIONS))
    api_parser.add_argument("--json", default="{}", help="JSON object, @request.json, or - for stdin")
    sub.add_parser("metamodel")
    sub.add_parser("regenerate")

    gap_parser = sub.add_parser("gap")
    gap_parser.add_argument("--observation", required=True)
    gap_parser.add_argument("--concern", required=True)
    gap_parser.add_argument("--possibilities", required=True)
    gap_parser.add_argument("--question", required=True)

    eligibility_parser = sub.add_parser("eligibility")
    eligibility_parser.add_argument("--paths", nargs="+", required=True)

    sub.add_parser("skills")

    cairn_parser = sub.add_parser("cairn")
    cairn_sub = cairn_parser.add_subparsers(dest="cairn_cmd", required=True)
    check_parser = cairn_sub.add_parser("check")
    check_parser.add_argument("path", type=Path)
    propose_parser = cairn_sub.add_parser("propose")
    propose_parser.add_argument("path", type=Path)
    propose_parser.add_argument("--slug", required=True)

    args = parser.parse_args(argv)
    root = args.root.resolve() if args.root else find_root()

    if args.cmd == "api":
        from scl.contracts import result
        from scl.service import execute
        try:
            raw = args.json
            if raw == "-":
                raw = sys.stdin.read()
            elif raw.startswith("@"):
                raw = Path(raw[1:]).read_text(encoding="utf-8")
            params = json.loads(raw)
            if not isinstance(params, dict):
                raise ValueError("request must be an object")
            response = execute(root, args.operation, **params)
        except (OSError, ValueError, TypeError) as exc:
            response = result(findings=[Finding("request.shape", str(exc))])
        print(json.dumps(response, indent=2))
        return 0 if response["status"] == "ok" else 1

    if args.cmd == "gap":
        sys.stdout.write(
            potential_model_gap(args.observation, args.concern, args.possibilities, args.question)
        )
        return 0

    skill_findings, halt = verify_skills(root)
    if halt:
        return _skill_halt(skill_findings)

    if args.cmd == "validate":
        return validate(root, args.strict, args.proposals)
    if args.cmd == "export":
        return _export(root, args)
    if args.cmd == "regenerate":
        return regenerate(root)
    if args.cmd == "metamodel":
        config = json.loads((root / "imk.json").read_text(encoding="utf-8"))
        text = (root / config["model"] / "metamodel.json").read_text(encoding="utf-8")
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
        return 0
    if args.cmd == "eligibility":
        eligible = release_eligible(args.paths)
        print("release" if eligible else "no-release")
        return 0
    if args.cmd == "skills":
        if skill_findings:
            for finding in skill_findings:
                print(finding.format())
            return 1
        print("skills verified")
        return 0
    if args.cmd == "cairn":
        return _cairn_command(root, args)
    return 1


def _cairn_command(root: Path, args: argparse.Namespace) -> int:
    path = args.path
    if not path.is_file():
        print(f"missing cairn file {path}", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    if args.cairn_cmd == "check":
        loaded = load_model(root)
        requirement_ids = {node["id"] for node in loaded.nodes if node.get("type") == "Requirement"}
        try:
            findings, _steps = check_text(text, requirement_ids)
        except CairnUnavailable as exc:
            print(str(exc), file=sys.stderr)
            return 1
        if findings:
            for finding in findings:
                print(finding.format())
            print(f"errors: {len(findings)}")
            return 1
        print("VALID")
        print("errors: 0")
        return 0
    if args.cairn_cmd == "propose":
        findings = propose_cairn(root, text, args.slug)
        if findings:
            for finding in findings:
                print(finding.format())
            print(f"errors: {len(findings)}")
            return 1
        print(f"proposed slice {args.slug}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
