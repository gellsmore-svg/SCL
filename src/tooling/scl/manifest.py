"""A small checker for the project-manifest schema. Stdlib only."""

from __future__ import annotations

import re


def validate_manifest(schema: dict, data: object) -> list[str]:
    errors: list[str] = []
    if schema.get("type") == "object":
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
            if key not in data:
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


def resolved_role(data: dict) -> str:
    """Absent role defaults to development. Scope switching is not implemented."""
    return str(data.get("role") or "development")
