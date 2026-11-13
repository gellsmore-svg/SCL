"""Proposed slices stay out of the layer files until a human approves them."""

from __future__ import annotations

import json
from pathlib import Path

from scl.findings import Finding


def inferred_node(record_id: str, type_name: str, name: str, description: str, inference: str, slug: str) -> dict:
    return {
        "id": record_id,
        "type": type_name,
        "name": name,
        "description": description,
        "status": "proposed",
        "metadata": {
            "basis": "inferred",
            "inference": inference,
            "slice": slug,
            "evidence": [],
        },
    }


def propose_slice(root: Path, slug: str, nodes: list[dict], relationships: list[dict]) -> tuple[Path, Path]:
    import re
    from scl.contracts import ServiceError
    from scl.model import contained_path
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ServiceError("slice.identity", "Invalid slice slug.")
    config = json.loads((root / "imk.json").read_text(encoding="utf-8"))
    model = contained_path(root, config["model"])
    if model is None:
        raise ServiceError("storage.path", "Model path escapes the project.")
    node_path = model / "nodes" / f"slice-{slug}.json"
    rel_path = model / "relationships" / f"slice-{slug}.json"
    node_path.parent.mkdir(parents=True, exist_ok=True)
    rel_path.parent.mkdir(parents=True, exist_ok=True)
    node_path.write_text(json.dumps(nodes, indent=2) + "\n", encoding="utf-8")
    rel_path.write_text(json.dumps(relationships, indent=2) + "\n", encoding="utf-8")
    return node_path, rel_path


def integrate_slice(root: Path, slug: str) -> None:
    """Removed unsafe mutation path. Import the slice through ModelService instead."""
    from scl.contracts import ServiceError
    raise ServiceError("approval.required", "Direct slice integration is disabled. Use import_slice, correct candidate findings, approve_change and commit_change.", slug)


def _load_array(path: Path) -> tuple[list, Finding | None]:
    if not path.is_file():
        return [], Finding("slice.shape", f"missing proposal file {path.name}", path.name)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [], Finding("slice.shape", f"{path.name} is not valid JSON", path.name)
    if not isinstance(data, list):
        return [], Finding("slice.shape", f"{path.name} must be a JSON array", path.name)
    return data, None


def proposal_findings(root: Path) -> list[Finding]:
    """Check stored slice files against the integrated model without merging them."""
    from scl.model import LEGAL, TYPE_PREFIX, _pairs, load_model

    config_path = root / "imk.json"
    if not config_path.is_file():
        return []
    config = json.loads(config_path.read_text(encoding="utf-8"))
    model = root / config["model"]
    node_dir = model / "nodes"
    rel_dir = model / "relationships"
    if not node_dir.is_dir():
        return []
    integrated = load_model(root, include_slices=False)
    findings: list[Finding] = []
    for node_path in sorted(node_dir.glob("slice-*.json")):
        slug = node_path.name[len("slice-") : -len(".json")]
        relative = node_path.relative_to(root).as_posix()
        nodes, error = _load_array(node_path)
        if error:
            findings.append(error)
            nodes = []
        rel_path = rel_dir / node_path.name
        relationships, rel_error = _load_array(rel_path)
        if rel_error:
            findings.append(rel_error)
            relationships = []
        slice_ids: set[str] = set()
        for node in nodes:
            if not isinstance(node, dict):
                findings.append(Finding("slice.shape", f"{relative}: record is not an object", slug))
                continue
            record_id = node.get("id")
            if not isinstance(record_id, str) or not record_id.strip():
                findings.append(Finding("slice.shape", f"{relative}: record is missing id", slug))
                continue
            slice_ids.add(record_id)
            kind = node.get("type")
            prefix = TYPE_PREFIX.get(kind)
            if prefix is None:
                findings.append(Finding("slice.shape", f"{relative}: unknown type {kind}", record_id))
            elif not record_id.startswith(prefix):
                findings.append(Finding("slice.shape", f"{relative}: id must start with {prefix}", record_id))
            if node.get("status") != "proposed":
                findings.append(Finding("slice.status", f"{relative}: proposal status must be proposed", record_id))
            metadata = node.get("metadata") if isinstance(node.get("metadata"), dict) else {}
            if metadata.get("basis") != "inferred":
                findings.append(Finding("slice.basis", f"{relative}: proposal basis must be inferred", record_id))
            inference = metadata.get("inference")
            if not isinstance(inference, str) or not inference.strip():
                findings.append(Finding("slice.inference", f"{relative}: inference is missing", record_id))
            if metadata.get("slice") != slug:
                findings.append(Finding("slice.identity", f"{relative}: metadata.slice must be {slug}", record_id))
        known = set(integrated.by_id) | slice_ids
        for rel in relationships:
            if not isinstance(rel, dict):
                findings.append(Finding("slice.shape", f"{relative}: relationship is not an object", slug))
                continue
            rel_id = str(rel.get("id") or slug)
            source_id = rel.get("from")
            target_id = rel.get("to")
            if source_id not in known or target_id not in known:
                findings.append(Finding("slice.endpoint", f"{relative}: relationship endpoint is missing", rel_id))
                continue
            source = integrated.by_id.get(source_id) or next(item for item in nodes if isinstance(item, dict) and item.get("id") == source_id)
            target = integrated.by_id.get(target_id) or next(item for item in nodes if isinstance(item, dict) and item.get("id") == target_id)
            rule = LEGAL.get(rel.get("type"))
            if rule is None or not _pairs(rule, source.get("type"), target.get("type")):
                findings.append(Finding("slice.endpoint", f"{relative}: relationship is not legal", rel_id))
    return findings
