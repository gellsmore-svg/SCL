#!/usr/bin/env python3
"""Validate a consumer manifest or a small model from a copied release.

This file ships inside the release kit. It uses only the standard library and
the schema copied beside it. It does not need the framework checkout.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

KNOWN_TYPES = {
    "Intent",
    "Outcome",
    "Model",
    "Requirement",
    "Actor",
    "System",
    "Policy",
    "Decision",
    "Project",
}
INTERACTION = {"human-system", "system-system"}


def _schema_path() -> Path:
    return Path(__file__).resolve().parents[1] / "schemas" / "project-manifest.schema.json"


def _validate_manifest(schema: dict, data: object) -> list[str]:
    errors: list[str] = []
    if schema.get("type") != "object":
        return ["bundled schema is not an object schema"]
    if not isinstance(data, dict):
        return ["manifest must be a JSON object"]
    allowed = set(schema.get("properties") or [])
    if schema.get("additionalProperties") is False:
        extra = sorted(set(data) - allowed)
        if extra:
            errors.append("unknown fields: " + ", ".join(extra))
    for key in schema.get("required") or []:
        if key not in data:
            errors.append(f"missing {key}")
    for key, spec in (schema.get("properties") or {}).items():
        if key not in data or not isinstance(spec, dict):
            continue
        value = data[key]
        if spec.get("type") == "string" and not isinstance(value, str):
            errors.append(f"{key} must be a string")
            continue
        if isinstance(value, str) and "minLength" in spec and len(value) < spec["minLength"]:
            errors.append(f"{key} is too short")
        if isinstance(value, str) and "pattern" in spec and re.fullmatch(spec["pattern"], value) is None:
            errors.append(f"{key} does not match {spec['pattern']}")
        if "enum" in spec and value not in spec["enum"]:
            errors.append(f"{key} must be one of {', '.join(spec['enum'])}")
    return errors


def check_manifest(path: Path) -> list[str]:
    schema_path = _schema_path()
    if not schema_path.is_file():
        return [f"bundled schema is missing: {schema_path.name}"]
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"manifest could not be read: {exc}"]
    return _validate_manifest(schema, data)


def check_model(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"model could not be read: {exc}"]
    if not isinstance(data, dict):
        return ["model must be a JSON object with nodes and relationships"]
    nodes = data.get("nodes")
    relationships = data.get("relationships")
    if not isinstance(nodes, list) or not isinstance(relationships, list):
        return ["model needs nodes and relationships arrays"]
    errors: list[str] = []
    ids: set[str] = set()
    for index, node in enumerate(nodes):
        where = f"nodes[{index}]"
        if not isinstance(node, dict):
            errors.append(f"{where} is not an object")
            continue
        record_id = node.get("id")
        if not isinstance(record_id, str) or not record_id.strip():
            errors.append(f"{where} is missing id")
            continue
        where = record_id
        if record_id in ids:
            errors.append(f"{where} is duplicated")
        ids.add(record_id)
        kind = node.get("type")
        if kind not in KNOWN_TYPES:
            errors.append(f"{where} has unknown type {kind}")
        if kind == "Requirement":
            metadata = node.get("metadata") if isinstance(node.get("metadata"), dict) else {}
            acceptance = metadata.get("acceptance")
            if not isinstance(acceptance, str) or not acceptance.strip():
                errors.append(f"{where} requires metadata.acceptance")
        if kind == "Model" and "interaction" in node:
            interaction = node.get("interaction")
            if not isinstance(interaction, list) or not all(isinstance(item, str) for item in interaction):
                errors.append(f"{where} interaction must be a list of strings")
            else:
                unknown = sorted(set(interaction) - INTERACTION)
                if unknown:
                    errors.append(f"{where} has unsupported interaction {', '.join(unknown)}")
                if not interaction:
                    errors.append(f"{where} is missing interaction")
    for index, rel in enumerate(relationships):
        where = f"relationships[{index}]"
        if not isinstance(rel, dict):
            errors.append(f"{where} is not an object")
            continue
        for end in ("from", "to"):
            endpoint = rel.get(end)
            if not isinstance(endpoint, str) or endpoint not in ids:
                errors.append(f"{where} {end} is not a known record")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="consume")
    sub = parser.add_subparsers(dest="cmd", required=True)
    manifest = sub.add_parser("manifest")
    manifest.add_argument("path", type=Path)
    model = sub.add_parser("model")
    model.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    if args.cmd == "manifest":
        errors = check_manifest(args.path)
    else:
        errors = check_model(args.path)
    if errors:
        for error in errors:
            print(error)
        print(f"errors: {len(errors)}")
        return 1
    print("VALID")
    print("errors: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
