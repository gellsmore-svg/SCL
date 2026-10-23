"""Load an IOMR model and check the chain."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from scl.findings import Finding

TYPE_PREFIX = {
    "Intent": "intent-",
    "Outcome": "outcome-",
    "Model": "model-",
    "Requirement": "requirement-",
    "Actor": "actor-",
    "System": "system-",
    "Policy": "policy-",
    "Decision": "decision-",
    "Project": "project-",
}

# Relationship legality. "same" means both ends share a type. "any" means any
# declared node type. Constrains may land on any node.
SAME = "same"
ANY_TARGET = "any"
LEGAL = {
    "delivers": {("Outcome", "Intent")},
    "serves": {("Model", "Outcome")},
    "specifies": {("Requirement", "Model")},
    "refines": SAME,
    "involves": {("Model", "Actor"), ("Model", "System")},
    "constrains": {("Policy", ANY_TARGET), ("Decision", ANY_TARGET), ("Requirement", ANY_TARGET)},
    "depends_on": ANY_TARGET,
    "supersedes": SAME,
    "belongs_to": ANY_TARGET,
}

CHAIN = ("Intent", "Outcome", "Model", "Requirement")
UP = {"delivers", "serves", "specifies", "refines"}
BASIS = {"stated", "derived", "inferred"}
STATUS = {"implemented", "partial", "planned", "proposed", "retired"}


@dataclass
class Loaded:
    root: Path
    nodes: list[dict] = field(default_factory=list)
    relationships: list[dict] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    expect: list = field(default_factory=list)

    @property
    def by_id(self) -> dict[str, dict]:
        return {node["id"]: node for node in self.nodes}


def find_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "imk.json").is_file():
            return candidate
    raise SystemExit("imk.json not found")


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _collect(directory: Path, include_slices: bool) -> list[dict]:
    if not directory.is_dir():
        return []
    records: list[dict] = []
    for path in sorted(directory.glob("*.json")):
        sliced = path.name.startswith("slice-")
        if sliced and not include_slices:
            continue
        if not sliced and include_slices:
            continue
        data = _read_json(path)
        if isinstance(data, list):
            records.extend(data)
        else:
            records.append(data)
    return records


def load_model(root: Path, include_slices: bool = False) -> Loaded:
    config = _read_json(root / "imk.json")
    model_dir = root / config["model"]
    nodes = _collect(model_dir / "nodes", include_slices=False)
    relationships = _collect(model_dir / "relationships", include_slices=False)
    if include_slices:
        nodes.extend(_collect(model_dir / "nodes", include_slices=True))
        relationships.extend(_collect(model_dir / "relationships", include_slices=True))
    return Loaded(
        root=root,
        nodes=nodes,
        relationships=relationships,
        sources=list(config.get("sources") or []),
        expect=list(config.get("expect") or []),
    )


def _pairs(rule, from_type: str, to_type: str) -> bool:
    if rule == SAME:
        return from_type == to_type
    if rule == ANY_TARGET:
        return True
    for source, target in rule:
        if source != from_type:
            continue
        if target in (ANY_TARGET, to_type):
            return True
    return False


def _evidence_finding(root: Path, sources: dict[str, dict], evidence: str, record_id: str) -> Finding | None:
    if ":" not in evidence:
        return Finding("ref.evidence", "evidence must be alias:path#anchor", record_id)
    alias, rest = evidence.split(":", 1)
    source = sources.get(alias)
    if source is None:
        return Finding("ref.evidence", f"unknown source alias {alias}", record_id)
    path_part, sep, anchor = rest.partition("#")
    if path_part != source["path"]:
        return Finding("ref.evidence", f"path does not match declared source {source['path']}", record_id)
    file_path = root / path_part
    if not file_path.is_file():
        return Finding("ref.evidence", f"cited file does not exist: {path_part}", record_id)
    if not sep or not anchor:
        return Finding("ref.evidence", "evidence is missing #anchor", record_id)
    text = file_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if anchor.startswith("L") and anchor[1:2].isdigit():
        body = anchor[1:]
        if "-L" in body:
            start_s, end_s = body.split("-L", 1)
            start, end = int(start_s), int(end_s)
        else:
            start = end = int(body)
        if start < 1 or end > len(lines) or start > end:
            return Finding("ref.evidence", f"line anchor {anchor} is outside {path_part}", record_id)
        return None
    if anchor not in text:
        return Finding("ref.evidence", f"anchor not found in {path_part}: {anchor}", record_id)
    return None


def _reaches_intent(start: str, by_id: dict[str, dict], outgoing: dict[str, list[tuple[str, str]]]) -> bool:
    seen = set()
    stack = [start]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        node = by_id.get(current)
        if node and node.get("type") == "Intent":
            return True
        for _kind, target in outgoing.get(current, []):
            stack.append(target)
    return False


def structural_findings(loaded: Loaded) -> list[Finding]:
    findings: list[Finding] = []
    by_id = loaded.by_id
    sources = {item["alias"]: item for item in loaded.sources}

    if len(by_id) != len(loaded.nodes):
        findings.append(Finding("record.id-prefix", "duplicate record ids in the model"))

    for node in loaded.nodes:
        prefix = TYPE_PREFIX.get(node.get("type"))
        record_id = str(node.get("id", ""))
        if prefix is None:
            findings.append(Finding("record.id-prefix", f"unknown type {node.get('type')}", record_id))
        elif not record_id.startswith(prefix):
            findings.append(Finding("record.id-prefix", f"id must start with {prefix}", record_id))
        metadata = node.get("metadata") or {}
        basis = metadata.get("basis")
        if basis not in BASIS:
            findings.append(Finding("status.discipline", "metadata.basis must be stated, derived, or inferred", record_id))
        status = node.get("status")
        if status is not None and status not in STATUS:
            findings.append(Finding("status.discipline", f"unknown status {status}", record_id))
        if status == "partial" and not str(metadata.get("gaps") or "").strip():
            findings.append(Finding("status.discipline", "partial records require metadata.gaps", record_id))
        if status == "implemented" and not metadata.get("evidence"):
            findings.append(Finding("status.discipline", "implemented records require evidence", record_id))
        if loaded.sources and node.get("type") in CHAIN and not metadata.get("evidence"):
            findings.append(Finding("ref.unevidenced", "chain record has no evidence", record_id))
        for item in metadata.get("evidence") or []:
            found = _evidence_finding(loaded.root, sources, item, record_id)
            if found:
                findings.append(found)
        if node.get("type") == "Outcome" and not str(metadata.get("measure") or "").strip():
            findings.append(Finding("expect.measure", "Outcome requires metadata.measure", record_id))

    outgoing: dict[str, list[tuple[str, str]]] = {}
    incoming_involves: dict[str, list[str]] = {}
    refines: list[dict] = []
    for rel in loaded.relationships:
        rel_id = str(rel.get("id", ""))
        kind = rel.get("type")
        source_id = rel.get("from")
        target_id = rel.get("to")
        rationale = rel.get("rationale") or ""
        if len(rationale.strip()) < 20:
            findings.append(Finding("rel.rationale", "rationale must be at least 20 characters", rel_id))
        source = by_id.get(source_id)
        target = by_id.get(target_id)
        if source is None or target is None:
            findings.append(Finding("rel.legality", "relationship endpoint is missing", rel_id))
            continue
        rule = LEGAL.get(kind)
        if rule is None:
            findings.append(Finding("rel.legality", f"unknown relationship type {kind}", rel_id))
            continue
        target_type = target["type"]
        if rule != ANY_TARGET and not _pairs(rule, source["type"], target_type):
            findings.append(
                Finding(
                    "rel.legality",
                    f"{kind} does not allow {source['type']} -> {target_type}",
                    rel_id,
                )
            )
        if kind in UP:
            outgoing.setdefault(source_id, []).append((kind, target_id))
        if kind == "involves":
            incoming_involves.setdefault(target_id, []).append(source_id)
        if kind == "refines":
            refines.append(rel)

    for node in loaded.nodes:
        if node.get("type") in ("Outcome", "Model", "Requirement"):
            if not _reaches_intent(node["id"], by_id, outgoing):
                findings.append(Finding("trace.reach-intent", "record does not trace up to an Intent", node["id"]))

    delivered = {rel["to"] for rel in loaded.relationships if rel.get("type") == "delivers"}
    served = {rel["to"] for rel in loaded.relationships if rel.get("type") == "serves"}
    specified = {rel["to"] for rel in loaded.relationships if rel.get("type") == "specifies"}
    for node in loaded.nodes:
        kind = node.get("type")
        if kind == "Intent" and node["id"] not in delivered:
            findings.append(Finding("trace.coverage", "Intent has no Outcome", node["id"]))
        if kind == "Outcome" and node["id"] not in served:
            findings.append(Finding("trace.coverage", "Outcome has no Model", node["id"]))
        if kind == "Model" and node["id"] not in specified:
            findings.append(Finding("trace.coverage", "Model has no Requirement", node["id"]))

    parent = {rel["from"]: rel["to"] for rel in refines}
    vector_ids = {
        node["id"]
        for node in loaded.nodes
        if node.get("type") == "Outcome" and (node.get("metadata") or {}).get("measurement") == "vector"
    }

    def depth(record_id: str, seen: set[str]) -> int:
        if record_id not in parent:
            return 1
        if record_id in seen:
            return 99
        seen.add(record_id)
        return 1 + depth(parent[record_id], seen)

    for record_id in parent:
        if depth(record_id, set()) > 2:
            findings.append(Finding("refines.discipline", "refines nesting is deeper than 2 levels", record_id))
    for rel in refines:
        if rel["from"] in vector_ids or rel["to"] in vector_ids:
            findings.append(
                Finding(
                    "refines.discipline",
                    "Outcome decomposition is distinct from vector measurement",
                    rel.get("id", ""),
                )
            )

    rels = loaded.relationships
    for node in loaded.nodes:
        if node.get("type") != "Model":
            continue
        interaction = set(node.get("interaction") or [])
        involved = []
        for rel in rels:
            if rel.get("type") == "involves" and rel.get("from") == node["id"] and rel.get("to") in by_id:
                involved.append(by_id[rel["to"]])
        actors = [item for item in involved if item["type"] == "Actor"]
        systems = [item for item in involved if item["type"] == "System"]
        involved_ids = {item["id"] for item in involved}
        if "human-system" in interaction and (not actors or not systems):
            findings.append(Finding("model.participants", "human-system needs at least one Actor and one System", node["id"]))
        if "system-system" in interaction and len(systems) < 2:
            findings.append(Finding("model.participants", "system-system needs at least two Systems", node["id"]))
        if not interaction:
            findings.append(Finding("model.participants", "Model is missing interaction", node["id"]))
        for index, step in enumerate(node.get("steps") or []):
            if not str(step.get("message") or "").strip():
                findings.append(Finding("model.steps", f"step {index} is missing message", node["id"]))
            for end in ("from", "to"):
                participant = step.get(end)
                if participant not in involved_ids:
                    findings.append(
                        Finding("model.steps", f"step {index} {end} is not linked with involves", node["id"])
                    )

    intent_reaching = {
        node["id"]
        for node in loaded.nodes
        if node.get("type") == "Model" and _reaches_intent(node["id"], by_id, outgoing)
    }
    for node in loaded.nodes:
        kind = node.get("type")
        if kind in ("Actor", "System"):
            models = incoming_involves.get(node["id"], [])
            if not any(model_id in intent_reaching for model_id in models):
                findings.append(Finding("trace.coverage", "participant is not involved in a model that reaches an Intent", node["id"]))
        if kind in ("Policy", "Decision"):
            linked = [
                rel.get("to")
                for rel in rels
                if rel.get("type") == "constrains" and rel.get("from") == node["id"]
            ]
            if not linked:
                findings.append(Finding("trace.coverage", "policy or decision does not constrain anything", node["id"]))
        if kind == "Project":
            owned = [
                rel.get("from")
                for rel in rels
                if rel.get("type") == "belongs_to" and rel.get("to") == node["id"]
            ]
            if not any(by_id.get(item, {}).get("type") == "Intent" for item in owned):
                findings.append(Finding("trace.coverage", "Project has no Intent", node["id"]))

    known = set(by_id)
    for item in loaded.expect:
        if item not in known:
            findings.append(Finding("expect.missing", f"expected record {item} is absent", str(item)))
    return findings
