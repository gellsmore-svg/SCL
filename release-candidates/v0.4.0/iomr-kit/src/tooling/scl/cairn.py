"""Project the IOMR model to and from a Cairn process.

The model stays the source of truth. Export, check, and propose use the
vendored process-description core. They do not import the Deborah package.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from scl.findings import Finding

# Same token Deborah accepts after a step number: `1. <receive-invoice> …`.
STEP_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_LEADING_NAME = re.compile(r"^<([A-Za-z][A-Za-z0-9_-]*)>\s*(.*)$")
_SCL_TAG = re.compile(r"(?:^|[\s,])scl:([A-Za-z][A-Za-z0-9_-]*)(?=$|[\s,\]])", re.I)
_PROCESS_TITLE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*(?: [A-Za-z0-9_-]+)*")


class CairnUnavailable(RuntimeError):
    """The vendored process-description core could not be imported."""


def step_token(value: str, fallback: str) -> str:
    """Return a Deborah step-name token, or the fallback when the text is not one."""
    if STEP_NAME.fullmatch(value):
        return value
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    if not slug or not slug[0].isalpha():
        slug = fallback
    if not STEP_NAME.fullmatch(slug):
        return fallback
    return slug


def _prose(text: str) -> str:
    cleaned = text.replace("[", "(").replace("]", ")").replace("\n", " ")
    return " ".join(cleaned.split())


def _process_title(model: dict) -> str:
    name = str(model.get("name") or "").strip()
    if _PROCESS_TITLE.fullmatch(name):
        return name
    return str(model["id"])


def render_cairn(loaded) -> str:
    """Render each model as a Cairn process. Recorded steps keep their names."""
    lines = [
        "CONTEXT",
        "Generated from the IOMR model. The model remains the source of truth.",
        "",
    ]
    models = [node for node in loaded.nodes if node.get("type") == "Model"]
    models.sort(key=lambda node: ((node.get("metadata") or {}).get("order", 0), node["id"]))
    for model in models:
        lines.append(f"PROCESS {_process_title(model)}")
        raw_steps = model.get("steps") or []
        if not isinstance(raw_steps, list) or not raw_steps:
            token = step_token(str(model["id"]), "model-step")
            lines.append(f"  1. <{token}> {_prose(str(model.get('description') or model['id']))}.")
            lines.append("")
            continue
        number = 0
        for step in raw_steps:
            if not isinstance(step, dict):
                continue
            number += 1
            explicit = step.get("name")
            if isinstance(explicit, str) and explicit.strip():
                token = step_token(explicit.strip(), f"step-{number}")
            else:
                token = step_token(str(step.get("message") or ""), f"step-{number}")
            message = _prose(str(step.get("message") or token))
            lines.append(f"  {number}. <{token}> {message}.")
            binds = step.get("binds") or []
            if isinstance(binds, list):
                named = [item.strip() for item in binds if isinstance(item, str) and item.strip()]
                if named:
                    lines.append(f"     BINDS: {', '.join(named)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _load_parser():
    try:
        from cairn_core import parse_document, validate_document
    except ImportError as exc:
        raise CairnUnavailable(
            "The process-description core is not on the path. "
            "Check and propose expect the vendored cairn_core package."
        ) from exc
    return parse_document, validate_document


def _binds_from_step(step) -> list[str]:
    found: list[str] = []
    for annotation in getattr(step, "annotations", []) or []:
        if getattr(annotation, "keyword", "") != "BINDS":
            continue
        found.extend(part.strip() for part in str(annotation.text).split(",") if part.strip())
    for raw in getattr(step, "tags", []) or []:
        for match in _SCL_TAG.finditer(str(raw)):
            found.append(match.group(1))
    return found


def _step_name(step) -> str | None:
    name = getattr(step, "name", None)
    if isinstance(name, str) and name:
        return name
    text = str(getattr(step, "text", "") or "")
    match = _LEADING_NAME.match(text)
    if match:
        return match.group(1)
    return None


def _walk_steps(steps, found: list[dict], process_name: str) -> None:
    for step in steps:
        found.append(
            {
                "name": _step_name(step),
                "binds": _binds_from_step(step),
                "text": str(getattr(step, "text", "") or ""),
                "line": getattr(step, "lineno", 0),
                "process": process_name,
            }
        )
        _walk_steps(getattr(step, "children", []) or [], found, process_name)


def _loose_binds(elements, found: list[dict], process_name: str) -> None:
    """BINDS sitting on the process, rather than on a step, stay visible."""
    for element in elements or []:
        if getattr(element, "keyword", "") != "BINDS":
            continue
        binds = [part.strip() for part in str(getattr(element, "text", "") or "").split(",") if part.strip()]
        found.append(
            {
                "name": None,
                "binds": binds,
                "text": "",
                "line": getattr(element, "lineno", 0),
                "process": process_name,
                "placement": "process",
            }
        )


def _take_process(process, found: list[dict]) -> None:
    process_name = str(getattr(process, "name", "") or "")
    _loose_binds(getattr(process, "elements", []) or [], found, process_name)
    _walk_steps(getattr(process, "steps", []) or [], found, process_name)


def steps_from_document(doc) -> list[dict]:
    found: list[dict] = []
    for process in getattr(doc, "processes", []) or []:
        _take_process(process, found)
    for plan in getattr(doc, "plans", []) or []:
        process = getattr(plan, "process", None)
        if process is not None:
            _take_process(process, found)
    return found


def binding_findings(requirement_ids: set[str], steps: list[dict]) -> list[Finding]:
    """A bind must name a requirement. Names that are present must be unique tokens."""
    findings: list[Finding] = []
    seen: set[str] = set()
    for step in steps:
        name = step.get("name")
        label = str(name or step.get("line") or "")
        if name:
            if STEP_NAME.fullmatch(str(name)) is None:
                findings.append(Finding("cairn.name", f"step name {name} is not a token", label))
            elif name in seen:
                findings.append(Finding("cairn.name", f"duplicate step name {name}", label))
            else:
                seen.add(str(name))
        for bind in step.get("binds") or []:
            if bind not in requirement_ids:
                findings.append(Finding("cairn.bind", f"{bind} is not a requirement", label or bind))
            elif step.get("placement") == "process":
                findings.append(Finding("cairn.bind", f"{bind} is not attached to a step", label or bind))
    return findings


def check_text(text: str, requirement_ids: set[str]) -> tuple[list[Finding], list[dict]]:
    """Parse with the vendored core, then resolve binds against requirement ids."""
    parse_document, validate_document = _load_parser()
    document = parse_document(text)
    findings = [Finding("cairn.parse", error) for error in document.parse_errors]
    if not document.parse_errors:
        findings.extend(Finding("cairn.shape", error) for error in validate_document(document))
    steps = steps_from_document(document)
    findings.extend(binding_findings(requirement_ids, steps))
    return findings, steps


def propose_from_process(
    process_name: str,
    steps: list[dict],
    slug: str,
    inference: str,
    model_id: str | None = None,
) -> tuple[list[dict], list[dict]]:
    """Build a proposed slice. This does not write the authoritative model."""
    from scl.slice import inferred_node

    model_id = model_id or f"model-{slug}"
    nodes = [
        inferred_node(
            model_id,
            "Model",
            process_name,
            f"Proposed from Cairn process {process_name}.",
            inference,
            slug,
        )
    ]
    relationships = []
    for step in steps:
        name = step.get("name")
        if not isinstance(name, str) or STEP_NAME.fullmatch(name) is None:
            continue
        requirement_id = f"requirement-{name}"
        description = _prose(str(step.get("text") or name)) or name
        node = inferred_node(requirement_id, "Requirement", name, description, inference, slug)
        node["metadata"]["acceptance"] = (
            f"Given the process, when step {name} finishes, then its output is recorded."
        )
        nodes.append(node)
        relationships.append(
            {
                "id": f"{requirement_id}-specifies-{model_id}",
                "type": "specifies",
                "from": requirement_id,
                "to": model_id,
                "rationale": f"{requirement_id} is the constraint inferred from Cairn step {name}.",
            }
        )
    return nodes, relationships


def _process_token(name: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "process"
    if not token[0].isalpha():
        token = "process-" + token
    return token


def _model_ids(slug: str, process_names: list[str]) -> dict[str, str]:
    """One process keeps model-{slug}. Several processes each get their own model."""
    if len(process_names) == 1:
        return {process_names[0]: f"model-{slug}"}
    assigned: dict[str, str] = {}
    used: set[str] = set()
    for name in process_names:
        candidate = f"model-{slug}-{_process_token(name)}"
        number = 2
        while candidate in used:
            candidate = f"model-{slug}-{_process_token(name)}-{number}"
            number += 1
        used.add(candidate)
        assigned[name] = candidate
    return assigned


def _other_slice_ids(model: Path, slug: str) -> set[str]:
    found: set[str] = set()
    for folder in ("nodes", "relationships"):
        directory = model / folder
        if not directory.is_dir():
            continue
        for path in directory.glob("slice-*.json"):
            other = path.name[len("slice-") : -len(".json")]
            if other == slug:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            rows = data if isinstance(data, list) else [data]
            for item in rows:
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    found.add(item["id"])
    return found


def propose_cairn(root: Path, text: str, slug: str) -> list[Finding]:
    """Write a slice file. Layer files stay untouched."""
    from scl.model import contained_path, load_model
    from scl.slice import propose_slice

    if _SLUG.fullmatch(slug) is None:
        return [Finding("cairn.slug", "slug must be lowercase words separated by hyphens", slug)]
    loaded = load_model(root)
    requirement_ids = {node["id"] for node in loaded.nodes if node.get("type") == "Requirement"}
    try:
        findings, steps = check_text(text, requirement_ids)
    except CairnUnavailable as exc:
        return [Finding("cairn.runtime", str(exc))]
    blocking = [
        item for item in findings if item.rule in {"cairn.parse", "cairn.shape", "cairn.name", "cairn.bind"}
    ]
    if blocking:
        return blocking
    for step in steps:
        if step.get("placement") == "process":
            continue
        name = step.get("name")
        if not isinstance(name, str) or not name:
            return [Finding("cairn.name", "propose needs a name on every step", str(step.get("line") or ""))]
    named = [step for step in steps if step.get("name") and step.get("placement") != "process"]
    if not named:
        return [Finding("cairn.name", "propose needs at least one named step")]
    order: list[str] = []
    grouped: dict[str, list[dict]] = {}
    for step in named:
        process_name = str(step.get("process") or slug)
        if process_name not in grouped:
            order.append(process_name)
            grouped[process_name] = []
        grouped[process_name].append(step)
    inference = f"Inferred from Cairn process steps in slice {slug}."
    model_ids = _model_ids(slug, order)
    nodes: list[dict] = []
    relationships: list[dict] = []
    for process_name in order:
        built_nodes, built_rels = propose_from_process(
            process_name,
            grouped[process_name],
            slug,
            inference,
            model_id=model_ids[process_name],
        )
        nodes.extend(built_nodes)
        relationships.extend(built_rels)
    config = json.loads((root / "imk.json").read_text(encoding="utf-8"))
    model = contained_path(root, config.get("model", ""))
    if model is None:
        return [Finding("cairn.slug", "model path escapes the project", slug)]
    node_file = model / "nodes" / f"slice-{slug}.json"
    rel_file = model / "relationships" / f"slice-{slug}.json"
    if node_file.exists() or rel_file.exists():
        return [Finding("cairn.slug", f"slice {slug} already exists", slug)]
    known = set(loaded.by_id) | _other_slice_ids(model, slug)
    collisions = [node["id"] for node in nodes if node["id"] in known]
    if collisions:
        return [Finding("cairn.collision", "proposed id already exists: " + ", ".join(collisions))]
    propose_slice(root, slug, nodes, relationships)
    return []
