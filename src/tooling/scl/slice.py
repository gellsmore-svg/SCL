"""Proposed slices stay out of the layer files until a human approves them."""

from __future__ import annotations

import json
from pathlib import Path


def inferred_node(record_id: str, type_name: str, name: str, description: str, inference: str, slug: str) -> dict:
    return {
        "id": record_id,
        "type": type_name,
        "name": name,
        "description": description,
        "status": "proposed",
        "metadata": {
            "project": "project-scl",
            "basis": "inferred",
            "inference": inference,
            "slice": slug,
            "evidence": [],
        },
    }


def propose_slice(root: Path, slug: str, nodes: list[dict], relationships: list[dict]) -> tuple[Path, Path]:
    config = json.loads((root / "imk.json").read_text(encoding="utf-8"))
    model = root / config["model"]
    node_path = model / "nodes" / f"slice-{slug}.json"
    rel_path = model / "relationships" / f"slice-{slug}.json"
    node_path.parent.mkdir(parents=True, exist_ok=True)
    rel_path.parent.mkdir(parents=True, exist_ok=True)
    node_path.write_text(json.dumps(nodes, indent=2) + "\n", encoding="utf-8")
    rel_path.write_text(json.dumps(relationships, indent=2) + "\n", encoding="utf-8")
    return node_path, rel_path


def integrate_slice(root: Path, slug: str) -> None:
    """Move an approved slice into the layer files and delete the slice files."""
    config = json.loads((root / "imk.json").read_text(encoding="utf-8"))
    model = root / config["model"]
    node_path = model / "nodes" / f"slice-{slug}.json"
    rel_path = model / "relationships" / f"slice-{slug}.json"
    nodes = json.loads(node_path.read_text(encoding="utf-8"))
    relationships = json.loads(rel_path.read_text(encoding="utf-8"))
    for node in nodes:
        metadata = node.setdefault("metadata", {})
        metadata.pop("slice", None)
    layer_nodes = model / "nodes" / "records.json"
    layer_rels = model / "relationships" / "links.json"
    existing_nodes = json.loads(layer_nodes.read_text(encoding="utf-8"))
    existing_rels = json.loads(layer_rels.read_text(encoding="utf-8"))
    existing_nodes.extend(nodes)
    existing_rels.extend(relationships)
    layer_nodes.write_text(json.dumps(existing_nodes, indent=2) + "\n", encoding="utf-8")
    layer_rels.write_text(json.dumps(existing_rels, indent=2) + "\n", encoding="utf-8")
    node_path.unlink()
    rel_path.unlink()
