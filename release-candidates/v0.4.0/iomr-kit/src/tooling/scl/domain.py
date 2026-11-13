"""Isolated graph changes. Canonical files are never written by domain operations."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re

from scl.contracts import ServiceError
from scl.findings import Finding
from scl.model import BASIS, STATUS, TYPE_PREFIX, Loaded, structural_findings


def canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def identifier(kind: str, name: str) -> str:
    if kind not in TYPE_PREFIX:
        raise ServiceError("record.id-prefix", f"Unknown record type {kind}; query get_metamodel.")
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug:
        raise ServiceError("record.shape", "Supply a meaningful name or explicit id.")
    return TYPE_PREFIX[kind] + slug


def relationship(kind: str, source: str, target: str, rationale: str | None = None) -> dict:
    return {"id": f"{source}-{kind}-{target}", "type": kind, "from": source, "to": target,
            "rationale": rationale or f"{source} {kind} {target} in the proposed IOMR interaction."}


def normalize(changes: list[dict], origin: str) -> list[dict]:
    if origin not in {"human-authored", "ai-inferred"}:
        raise ServiceError("proposal.origin", "Origin must be human-authored or ai-inferred; neither grants approval.")
    if not isinstance(changes, list) or not changes or len(changes) > 200:
        raise ServiceError("request.shape", "Supply between 1 and 200 changes.")
    output = deepcopy(changes)
    for change in output:
        op = change.get("op")
        if op == "add_record":
            record = change["record"]
            if "id" not in record:
                record["id"] = identifier(record["type"], record["name"])
            record.setdefault("status", "planned")
            metadata = record.setdefault("metadata", {})
            metadata.setdefault("basis", "inferred" if origin == "ai-inferred" else "stated")
        elif op == "add_relationship":
            rel = change["relationship"]
            rel.setdefault("id", f"{rel['from']}-{rel['type']}-{rel['to']}")
        elif op not in {"update_record", "remove_relationship", "retire_record", "declare_source"}:
            raise ServiceError("change.operation", "Use add_record, update_record, add_relationship, remove_relationship, retire_record or declare_source.")
    return output


def _provenance(record: dict, proposal: dict, reviewer: str, original: dict | None) -> None:
    metadata = record.setdefault("metadata", {})
    original_basis = metadata.get("basis")
    entry = {"proposal_id": proposal["id"], "change_digest": digest(proposal["changes"]),
             "origin": proposal["origin"], "author_claim": proposal["author"],
             "original_basis": original_basis, "original_status": record.get("status"),
             "inference": metadata.get("inference"), "evidence": deepcopy(metadata.get("evidence", [])),
             "reviewer": reviewer, "previous_record_digest": digest(original) if original else None}
    # Never trust caller-supplied provenance, or erase historical changes on update.
    history = deepcopy((original or {}).get("metadata", {}).get("provenance", []))
    metadata["provenance"] = history + [entry]
    if original_basis == "inferred":
        metadata["basis"] = "derived"
    if record.get("status") == "proposed":
        record["status"] = "planned"
    if metadata.get("slice"):
        entry["slice"] = metadata.pop("slice")


def apply_changes(loaded: Loaded, proposal: dict, reviewer: str = "pending-review") -> tuple[Loaded, dict]:
    candidate = deepcopy(loaded)
    nodes = candidate.by_id
    links = {r["id"]: r for r in candidate.relationships}
    affected, removed, destructive = set(), [], []
    for change in proposal["changes"]:
        op = change["op"]
        if op == "declare_source":
            from scl.model import contained_path
            source = deepcopy(change["source"])
            if not all(isinstance(source.get(k), str) and source[k].strip() for k in ("alias", "path", "ref")):
                raise ServiceError("ref.evidence", "Source needs alias, repository-relative path and immutable reference.")
            if any(s["alias"] == source["alias"] for s in candidate.sources):
                raise ServiceError("ref.evidence", "Source alias already exists; reuse it.")
            path = contained_path(loaded.root, source["path"])
            if path is None or not path.is_file():
                raise ServiceError("ref.evidence", "Source must be an existing file inside the project.")
            candidate.sources.append(source)
        elif op == "add_record":
            node = deepcopy(change["record"])
            rid = node["id"]
            if rid in nodes:
                raise ServiceError("record.id-prefix", "Record already exists; reuse its id or update it.", rid)
            if any(n.get("type") == node["type"] and n.get("name", "").casefold() == node["name"].casefold() for n in nodes.values()):
                raise ServiceError("record.duplicate", "Same-type record with this name exists; find and reuse it.", rid)
            _check_record(node)
            if node.get("status") == "retired":
                raise ServiceError("status.transition", "New records cannot start retired; use retire_record with a successor.", rid)
            _provenance(node, proposal, reviewer, None)
            nodes[rid] = node
            candidate.nodes.append(node)
            affected.add(rid)
        elif op in {"update_record", "retire_record"}:
            rid = change["id"]
            if rid not in nodes:
                raise ServiceError("record.missing", "Find an existing record before updating it.", rid)
            old = deepcopy(nodes[rid])
            patch = deepcopy(change.get("patch", {}))
            if any(key in patch for key in ("id", "type")):
                raise ServiceError("record.identity", "Record id and type are immutable; retire/supersede instead.", rid)
            if op == "retire_record":
                if not isinstance(change.get("reason"), str) or len(change["reason"].strip()) < 20:
                    raise ServiceError("change.destructive", "Retirement requires a reason of at least 20 characters.", rid)
                patch["status"] = "retired"
                replacement = change.get("superseded_by")
                if not replacement:
                    raise ServiceError("status.discipline", "Retirement requires superseded_by and a same-type replacement.", rid)
                rel = relationship("supersedes", replacement, rid, change.get("reason"))
                links[rel["id"]] = rel
                destructive.append(rid)
            if old.get("status") == "retired":
                raise ServiceError("status.transition", "Retired records are immutable; add a replacement.", rid)
            if patch.get("status") == "retired" and op != "retire_record":
                raise ServiceError("status.transition", "Use retire_record to preserve supersession history.", rid)
            if "metadata" in patch:
                patch["metadata"] = {**old.get("metadata", {}), **patch["metadata"]}
            nodes[rid].update(patch)
            _check_record(nodes[rid])
            _provenance(nodes[rid], proposal, reviewer, old)
            affected.add(rid)
        elif op == "add_relationship":
            rel = deepcopy(change["relationship"])
            if rel["id"] in links or any((r["from"], r["type"], r["to"]) == (rel["from"], rel["type"], rel["to"]) for r in links.values()):
                raise ServiceError("rel.identity", "Relationship already exists; reuse it.", rel["id"])
            links[rel["id"]] = rel
            affected.update((rel["from"], rel["to"]))
        elif op == "remove_relationship":
            rid = change["id"]
            if not isinstance(change.get("reason"), str) or len(change["reason"].strip()) < 20:
                raise ServiceError("change.destructive", "Removing a link requires a reason of at least 20 characters.", rid)
            if rid not in links:
                raise ServiceError("rel.missing", "Relationship is absent; refresh the model.", rid)
            rel = links.pop(rid)
            removed.append(rid)
            destructive.append(rid)
            affected.update((rel["from"], rel["to"]))
    candidate.relationships = list(links.values())
    return candidate, {"affected_records": sorted(affected), "removed_relationships": removed,
                       "destructive_changes": destructive,
                       "dependants": dependants(candidate, affected)}


def _check_record(node):
    metadata = node.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ServiceError("record.shape", "metadata must be an object.")
    for key in ("name", "description"):
        if not isinstance(node.get(key), str) or not node[key].strip():
            raise ServiceError("record.shape", f"Record needs a non-empty {key}.", node.get("id", ""))
    if (node.get("status") is not None and node.get("status") not in STATUS) or metadata.get("basis") not in BASIS:
        raise ServiceError("status.discipline", "Supply a supported status and basis.", node["id"])
    if metadata.get("basis") == "inferred" and not str(metadata.get("inference", "")).strip():
        raise ServiceError("slice.inference", "Explain the original inference in metadata.inference.", node["id"])


def candidate_findings(candidate: Loaded) -> list[Finding]:
    findings = structural_findings(candidate)
    findings.extend(Finding("author.invented", "Integrated records cannot retain inferred basis.", n["id"])
                    for n in candidate.nodes if n.get("metadata", {}).get("basis") == "inferred")
    return findings


def dependants(loaded: Loaded, ids) -> list[str]:
    seen, pending = set(ids), list(ids)
    while pending:
        current = pending.pop()
        neighbours = [r["from"] for r in loaded.relationships if r["to"] == current]
        neighbours += [n["id"] for n in loaded.nodes if any(current in s.get("binds", []) or current in (s.get("from"), s.get("to")) for s in n.get("steps", []))]
        for rid in neighbours:
            if rid not in seen:
                seen.add(rid)
                pending.append(rid)
    return sorted(seen - set(ids))
