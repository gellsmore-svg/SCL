"""Transport-independent JSON contracts; no optional runtime dependencies."""
from __future__ import annotations

from dataclasses import asdict
from typing import TypedDict

from scl.findings import Finding


class Result(TypedDict):
    status: str
    model_revision: str | None
    findings: list[dict]
    retryable: bool
    data: dict


class ServiceError(Exception):
    def __init__(self, rule: str, message: str, record_id: str = "", *, retryable=False):
        self.findings = [Finding(rule, message, record_id)]
        self.retryable = retryable
        super().__init__(message)


def result(data=None, *, revision=None, findings=(), retryable=False, status=None) -> Result:
    items = [asdict(f) for f in findings]
    return {"status": status or ("error" if items else "ok"), "model_revision": revision,
            "findings": items, "retryable": retryable, "data": data or {}}


RECORD_SCHEMA = {
    "type": "object", "required": ["name", "description"],
    "properties": {
        "id": {"type": "string", "description": "Optional for semantic additions; generated from the name."},
        "type": {"type": "string", "enum": ["Intent", "Outcome", "Model", "Requirement", "Actor", "System", "Policy", "Decision", "Project"]},
        "name": {"type": "string", "minLength": 1}, "description": {"type": "string", "minLength": 1},
        "status": {"type": "string", "enum": ["planned", "proposed", "implemented", "partial", "retired"]},
        "metadata": {"type": "object", "properties": {
            "basis": {"enum": ["stated", "derived", "inferred"]}, "inference": {"type": "string"},
            "evidence": {"type": "array", "items": {"type": "string"}},
            "acceptance": {"type": "string"}, "measure": {"type": "string"}, "gaps": {"type": "string"}}},
        "interaction": {"type": "array", "items": {"enum": ["human-system", "system-system"]}},
        "steps": {"type": "array", "items": {"type": "object", "required": ["from", "to", "message"],
            "properties": {"from": {"type": "string"}, "to": {"type": "string"}, "message": {"type": "string"},
                           "name": {"type": "string"}, "binds": {"type": "array", "items": {"type": "string"}}}}},
    },
}
RELATIONSHIP_SCHEMA = {"type": "object", "required": ["type", "from", "to", "rationale"], "properties": {
    k: {"type": "string"} for k in ("id", "type", "from", "to", "rationale")}}
CHANGE_SCHEMA = {"oneOf": [
    {"type": "object", "required": ["op", "record"], "properties": {"op": {"const": "add_record"}, "record": RECORD_SCHEMA}},
    {"type": "object", "required": ["op", "id", "patch"], "properties": {"op": {"const": "update_record"}, "id": {"type": "string"}, "patch": {"type": "object"}}},
    {"type": "object", "required": ["op", "relationship"], "properties": {"op": {"const": "add_relationship"}, "relationship": RELATIONSHIP_SCHEMA}},
    {"type": "object", "required": ["op", "id", "reason"], "properties": {"op": {"const": "remove_relationship"}, "id": {"type": "string"}, "reason": {"type": "string", "minLength": 20}}},
    {"type": "object", "required": ["op", "id", "superseded_by", "reason"], "properties": {"op": {"const": "retire_record"}, "id": {"type": "string"}, "superseded_by": {"type": "string"}, "reason": {"type": "string", "minLength": 20}}},
    {"type": "object", "required": ["op", "source"], "properties": {"op": {"const": "declare_source"}, "source": {"type": "object", "required": ["alias", "path", "ref"], "properties": {k: {"type": "string"} for k in ("alias", "path", "ref")}}}},
]}


def input_schema(method) -> dict:
    """Publish the Python application signature without requiring MCP/Pydantic."""
    import inspect
    import types
    import typing
    hints = typing.get_type_hints(method)

    def schema(annotation):
        origin = typing.get_origin(annotation)
        args = typing.get_args(annotation)
        if annotation in (str, int, bool, float):
            return {"type": {str: "string", int: "integer", bool: "boolean", float: "number"}[annotation]}
        if annotation is type(None):
            return {"type": "null"}
        if origin in (types.UnionType, typing.Union):
            return {"anyOf": [schema(a) for a in args]}
        if origin is list or annotation is list:
            return {"type": "array", "items": schema(args[0]) if args else {}}
        return {"type": "object"}

    properties, required = {}, []
    for name, parameter in inspect.signature(method).parameters.items():
        if name == "self":
            continue
        field = schema(hints.get(name, dict))
        if name == "record":
            field = RECORD_SCHEMA
        elif name in {"changes", "related_changes"}:
            field = {"type": "array", "items": CHANGE_SCHEMA, "maxItems": 200}
            if name == "related_changes":
                field = {"anyOf": [field, {"type": "null"}]}
        field = dict(field)
        if parameter.default is inspect.Parameter.empty:
            required.append(name)
        else:
            field["default"] = parameter.default
        properties[name] = field
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}
