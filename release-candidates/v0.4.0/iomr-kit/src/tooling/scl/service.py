"""The single application boundary used by CLI, MCP and future transports."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scl.approval import ApprovalVerifier, UnavailableApproval, verifier_from_environment
from scl.contracts import ServiceError, result
from scl.domain import apply_changes, candidate_findings, dependants, digest, normalize, relationship
from scl.model import UP
from scl.skills import verify_skills
from scl.storage import JsonStorage, Storage

OPERATIONS = {
    "get_context": "Discover scoped project context, governance and operations.",
    "get_api_schema": "Discover exact parameters for an API operation without MCP.",
    "get_metamodel": "Read record and relationship constraints.",
    "find_records": "Find reusable records, with bounded pagination.",
    "get_record": "Read a record by stable identity.",
    "get_trace": "Read the upstream trace to Intent.",
    "get_dependants": "Inspect records affected by a dependency change.",
    "get_model_revision": "Read the current optimistic concurrency token.",
    "propose_change": "Store a coherent change set and validate its complete candidate.",
    "update_proposal": "Replace or rebase a proposal; invalidate earlier approval.",
    "get_proposal": "Read proposal state and its content revision.",
    "preview_change": "Preview affected records and the exact signable approval payload.",
    "validate_proposal": "Validate the entire candidate graph without committing it.",
    "reject_proposal": "Close a proposal without changing canonical content.",
    "approve_change": "Verify a trusted reviewer's detached signature; never self-approve.",
    "commit_change": "Integrate an approved candidate and derived documents in one recoverable transaction.",
    "add_intent": "Propose an Intent; complete lower-layer coverage in the same proposal.",
    "add_outcome": "Propose an Outcome and automatically link it to its Intent.",
    "add_model": "Propose a Model and automatically link it to its Outcome and participants.",
    "add_requirement": "Propose a Requirement and automatically link it to its Model.",
    "link_records": "Propose a legal semantic relationship between existing records.",
    "update_requirement": "Propose changes to an existing Requirement.",
    "import_slice": "Import a legacy slice as a governed proposal; never integrate directly.",
}
READ_OPERATIONS = {"get_api_schema", "get_context", "get_metamodel", "find_records", "get_record", "get_trace",
                   "get_dependants", "get_model_revision", "get_proposal", "preview_change", "validate_proposal"}


def proposal_revision(proposal):
    return digest(proposal)


class ModelService:
    def __init__(self, root: Path, *, storage: Storage | None = None, approval: ApprovalVerifier | None = None):
        self.storage = storage or JsonStorage(root)
        self.root = self.storage.root
        self.approval = approval if approval is not None else verifier_from_environment(self.root)
        self.revision = None

    def execute(self, operation_name: str, **params) -> dict:
        """Public JSON contract: all errors are findings, all state access is locked."""
        operation = operation_name
        try:
            if operation.startswith("scl_"):
                operation = operation[4:]
            if operation not in OPERATIONS:
                raise ServiceError("request.operation", "Unknown operation; use get_context for discovery.")
            if len(json.dumps(params)) > 1_000_000:
                raise ServiceError("request.size", "Request exceeds 1 MB; split it into coherent proposals.")
            with self.storage.locked(readonly=operation in READ_OPERATIONS):
                # Do not bypass an existing project's significant-operation skill gates.
                if (self.root / "meta/required-skills.md").exists() or (self.root / "validate-framework.py").is_file():
                    findings, halt = verify_skills(self.root)
                    if findings or halt:
                        return result(findings=findings)
                self.revision = digest(self.storage.snapshot())
                data = getattr(self, "_" + operation)(**params)
                return result(data, revision=self.revision)
        except ServiceError as exc:
            return result(revision=self.revision, findings=exc.findings, retryable=exc.retryable)
        except (KeyError, TypeError, ValueError, AttributeError, RecursionError) as exc:
            return result(revision=self.revision, findings=[self._finding("request.shape", f"Invalid request or stored model shape: {exc}. Query get_api_schema with this operation name and correct the indicated fields.")])
        except OSError as exc:
            return result(revision=self.revision, findings=[self._finding("storage.failure", f"Storage operation failed ({type(exc).__name__}); retry after checking permissions and recovery.")], retryable=True)

    @staticmethod
    def _finding(rule, message):
        from scl.findings import Finding
        return Finding(rule, message)

    def _check_revision(self, expected_revision):
        if expected_revision != self.revision:
            raise ServiceError("revision.conflict", "Model changed. Read current context, then update_proposal against this revision and review again.", retryable=True)

    def _get_model_revision(self):
        return {"revision": self.revision}

    def _get_context(self, query: str = "", limit: int = 10):
        loaded = self.storage.load()
        return {"projects": [{"id": n["id"], "name": n.get("name")} for n in loaded.nodes if n["type"] == "Project"],
                "model_location": self.storage.model_location, "metamodel": self._get_metamodel(),
                "related_records": self._find_records(query=query, limit=limit),
                "sources": loaded.sources, "approval_available": not isinstance(self.approval, UnavailableApproval),
                "governance": ["All changes require a trusted reviewer signature, including human-authored claims.",
                               "Validation is not approval. Inferred basis is retained in provenance and approved as derived.",
                               "No record deletion. Retirement requires supersession. Complete candidate graphs are validated.",
                               "Direct canonical editing is unsupported. Required trusted CI verifies signed transitions."],
                "operations": OPERATIONS, "parameter_discovery": "get_api_schema(operation)"}

    def _get_api_schema(self, operation: str):
        from scl.contracts import input_schema
        operation = operation.removeprefix("scl_")
        if operation not in OPERATIONS:
            raise ServiceError("request.operation", "Unknown operation; use get_context.")
        return {"operation": operation, "description": OPERATIONS[operation],
                "input_schema": input_schema(getattr(type(self), "_" + operation))}

    def _get_metamodel(self):
        meta = deepcopy(self.storage.load().metamodel)
        meta["record_conventions"] = {"Requirement": "metadata.acceptance", "Outcome": "metadata.measure",
                                      "Model": "interaction, involves participants, steps with from/to/message"}
        meta["change_operations"] = ["add_record", "update_record", "add_relationship", "remove_relationship", "retire_record", "declare_source"]
        return meta

    @staticmethod
    def _page(items, offset=0, limit=20):
        if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 100:
            raise ServiceError("query.page", "offset must be nonnegative; limit must be between 1 and 100.")
        return {"items": items[offset:offset+limit], "total": len(items),
                "next_offset": offset+limit if offset+limit < len(items) else None}

    def _find_records(self, query: str = "", type: str | None = None, offset: int = 0, limit: int = 20):
        loaded = self.storage.load()
        matches = [n for n in loaded.nodes if (type is None or n["type"] == type) and
                   query.casefold() in " ".join(str(n.get(k, "")) for k in ("id", "name", "description")).casefold()]
        return self._page([{k: n.get(k) for k in ("id", "type", "name", "status", "description")} for n in matches], offset, limit)

    def _get_record(self, record_id: str):
        loaded = self.storage.load()
        if record_id not in loaded.by_id:
            raise ServiceError("record.missing", "No record with that id; use find_records.", record_id)
        return {"record": loaded.by_id[record_id]}

    def _get_trace(self, record_id: str, offset: int = 0, limit: int = 50):
        loaded = self.storage.load()
        if record_id not in loaded.by_id:
            raise ServiceError("record.missing", "No record with that id.", record_id)
        seen, pending, edges = {record_id}, [record_id], []
        while pending:
            current = pending.pop()
            for rel in loaded.relationships:
                if rel["from"] == current and rel["type"] in UP:
                    edges.append(rel)
                    if rel["to"] not in seen:
                        pending.append(rel["to"])
                        seen.add(rel["to"])
        return {"records": self._page([loaded.by_id[rid] for rid in sorted(seen)], offset, limit),
                "relationships": self._page(edges, offset, limit)}

    def _get_dependants(self, record_id: str, offset: int = 0, limit: int = 50):
        self._get_record(record_id)
        return self._page(dependants(self.storage.load(), [record_id]), offset, limit)

    def _save(self, proposal):
        self.storage.save_proposal(proposal)

    def _get_proposal(self, proposal_id: str):
        proposal = self.storage.read_proposal(proposal_id)
        return {"proposal": proposal, "proposal_id": proposal_id, "proposal_revision": proposal_revision(proposal)}

    def _propose_change(self, title: str, changes: list[dict], expected_revision: str,
                        origin: str = "ai-inferred", author: str = "agent"):
        self._check_revision(expected_revision)
        if not isinstance(title, str) or not title.strip() or not isinstance(author, str) or not author.strip():
            raise ServiceError("proposal.identity", "Supply a non-empty title and author claim.")
        proposal = {"title": title, "changes": normalize(changes, origin), "base_revision": self.revision,
                    "origin": origin, "author": author, "state": "proposed"}
        proposal["id"] = "proposal-" + digest(proposal)[:24]
        if self.storage.proposal_exists(proposal["id"]):
            existing = self.storage.read_proposal(proposal["id"])
            if existing["state"] in {"rejected", "committed"}:
                return self._get_proposal(existing["id"])
            proposal = existing
        else:
            self._save(proposal)
        return self._proposal_report(proposal)

    def _update_proposal(self, proposal_id: str, changes: list[dict], expected_revision: str,
                         expected_proposal_revision: str):
        self._check_revision(expected_revision)
        proposal = self.storage.read_proposal(proposal_id)
        self._editable(proposal, expected_proposal_revision)
        proposal.update(changes=normalize(changes, proposal["origin"]), base_revision=self.revision, state="proposed")
        proposal.pop("approval", None)
        self._save(proposal)
        return self._proposal_report(proposal)

    @staticmethod
    def _editable(proposal, expected_proposal_revision):
        if proposal_revision(proposal) != expected_proposal_revision:
            raise ServiceError("proposal.conflict", "Proposal changed; read it and retry with its current proposal_revision.", retryable=True)
        if proposal["state"] in {"committed", "rejected"}:
            raise ServiceError("proposal.state", "Closed proposals cannot be changed; propose a new change set.")

    def _evaluate(self, proposal, reviewer="pending-review"):
        self._check_revision(proposal["base_revision"])
        candidate, impact = apply_changes(self.storage.load(), proposal, reviewer)
        findings = candidate_findings(candidate)
        # Framework-specific gates remain opt-in for consumers, automatic for SCL.
        if (self.root / "validate-framework.py").is_file():
            from scl.framework import framework_findings
            from scl.gates import behavior_findings
            findings += framework_findings(self.root) + behavior_findings(self.root, candidate)
        if findings:
            return candidate, impact, findings, {}, None
        writes = self.storage.candidate_files(candidate)
        before = self.storage.snapshot()
        after = self.storage.after_snapshot(writes)
        payload = {"protocol": "scl-iomr-v1", "proposal_id": proposal["id"],
                   "proposal_digest": digest({k: v for k, v in proposal.items() if k not in {"state", "approval", "committed_revision"}}),
                   "reviewer": reviewer, "before": before, "after": after,
                   "base_revision": digest(before), "candidate_revision": digest(after)}
        return candidate, impact, [], writes, payload

    def _proposal_report(self, proposal, reviewer="pending-review", offset=0, limit=20):
        from dataclasses import asdict
        data = {"proposal_id": proposal["id"], "proposal_revision": proposal_revision(proposal),
                "state": proposal["state"], "required_approvals": ["trusted-reviewer-signature"],
                "approval_verified": False, "validation_status": "invalid"}
        try:
            candidate, impact, findings, writes, payload = self._evaluate(proposal, reviewer)
            data.update(impact)
            data["dependants"] = self._page(impact["dependants"], offset, limit)
            data["validation_findings"] = [asdict(f) for f in findings]
            data["validation_status"] = "valid" if not findings else "invalid"
            data["records"] = self._page([n for n in candidate.nodes if n["id"] in impact["affected_records"]], offset, limit)
            data["relationship_ids"] = self._page([r["id"] for r in candidate.relationships if r["from"] in impact["affected_records"] or r["to"] in impact["affected_records"]], offset, limit)
            data["generated_files"] = [p for p in writes if p.endswith(".md")]
            data["approval_payload"] = payload
            data["recommended_actions"] = ["Correct findings with update_proposal."] if findings else ["Review this payload, sign it externally, then approve_change and commit_change."]
        except ServiceError as exc:
            data["validation_findings"] = [asdict(f) for f in exc.findings]
            data["retryable"] = exc.retryable
            data["recommended_actions"] = ["Refresh context and correct/rebase with update_proposal."]
        return data

    def _preview_change(self, proposal_id: str, reviewer: str = "pending-review", offset: int = 0, limit: int = 20):
        return self._proposal_report(self.storage.read_proposal(proposal_id), reviewer, offset, limit)

    _validate_proposal = _preview_change

    def _reject_proposal(self, proposal_id: str, reason: str, expected_proposal_revision: str):
        proposal = self.storage.read_proposal(proposal_id)
        self._editable(proposal, expected_proposal_revision)
        if not reason.strip():
            raise ServiceError("proposal.reason", "Record why the proposal is being withdrawn.")
        proposal.update(state="rejected", rejection={"reason": reason, "authority": "caller-withdrawal; not a human review attestation"})
        proposal.pop("approval", None)
        self._save(proposal)
        return self._get_proposal(proposal_id)

    def _approve_change(self, proposal_id: str, identity: str, signature: str, expected_revision: str):
        self._check_revision(expected_revision)
        proposal = self.storage.read_proposal(proposal_id)
        if proposal["state"] not in {"proposed", "approved"}:
            raise ServiceError("proposal.state", "Only open proposals can be approved.")
        _, _, findings, _, payload = self._evaluate(proposal, identity)
        if findings:
            error = ServiceError("proposal.invalid", "Correct candidate validation findings before approval.")
            error.findings = findings
            raise error
        approval = {"identity": identity, "signature": signature}
        self.approval.verify(payload, approval)
        proposal.update(state="approved", approval=approval)
        self._save(proposal)
        return {**self._get_proposal(proposal_id), "approval_verified": True}

    def _commit_change(self, proposal_id: str, expected_revision: str):
        proposal = self.storage.read_proposal(proposal_id)
        if proposal["state"] == "committed":
            receipt = self.storage.read_receipt(proposal_id)
            self.approval.verify(receipt["payload"], receipt["approval"])
            unsigned = {k: v for k, v in proposal.items() if k not in {"state", "approval", "committed_revision"}}
            if digest(unsigned) != receipt["payload"]["proposal_digest"] or proposal["committed_revision"] != receipt["payload"]["candidate_revision"]:
                raise ServiceError("approval.invalid", "Committed proposal differs from its receipt.")
            return {"proposal_id": proposal_id, "state": "committed", "already_committed": True,
                    "committed_revision": proposal["committed_revision"]}
        self._check_revision(expected_revision)
        if proposal["state"] != "approved" or not proposal.get("approval"):
            raise ServiceError("approval.required", "Validate and obtain a trusted reviewer signature using approve_change before commit.", proposal_id)
        approval = proposal["approval"]
        _, impact, findings, writes, payload = self._evaluate(proposal, approval["identity"])
        if findings:
            error = ServiceError("proposal.invalid", "Candidate no longer validates.")
            error.findings = findings
            raise error
        self.approval.verify(payload, approval)
        # A last compare detects non-service changes during rendering. Filesystem
        # permissions/required CI are still necessary against hostile writers.
        if digest(self.storage.snapshot()) != self.revision or self.storage.after_snapshot(writes) != payload["after"]:
            raise ServiceError("revision.conflict", "Model changed during preparation; retry.", retryable=True)
        proposal.update(state="committed", committed_revision=payload["candidate_revision"])
        self.storage.commit(writes, proposal, {"payload": payload, "approval": approval})
        self.revision = payload["candidate_revision"]
        impact["dependants"] = self._page(impact["dependants"])
        return {"proposal_id": proposal_id, "state": "committed", "committed_revision": self.revision, **impact}

    def _add(self, kind, record, expected_revision, parent_id=None, participants=None, related_changes=None,
             origin="ai-inferred", author="agent"):
        record = deepcopy(record)
        record["type"] = kind
        changes = normalize([{"op": "add_record", "record": record}], origin)
        rid = changes[0]["record"]["id"]
        if kind != "Intent":
            if not parent_id:
                raise ServiceError("trace.reach-intent", "Supply parent_id to reuse the existing upstream chain.")
            reltype = {"Outcome": "delivers", "Model": "serves", "Requirement": "specifies"}[kind]
            changes.append({"op": "add_relationship", "relationship": relationship(reltype, rid, parent_id)})
        for participant in participants or []:
            changes.append({"op": "add_relationship", "relationship": relationship("involves", rid, participant)})
        changes.extend(related_changes or [])
        return self._propose_change(f"Add {kind}: {record['name']}", changes, expected_revision, origin, author)

    def _add_intent(self, record: dict, expected_revision: str, related_changes: list | None = None, origin: str = "ai-inferred", author: str = "agent"):
        return self._add("Intent", record, expected_revision, related_changes=related_changes, origin=origin, author=author)

    def _add_outcome(self, record: dict, parent_id: str, expected_revision: str, related_changes: list | None = None, origin: str = "ai-inferred", author: str = "agent"):
        return self._add("Outcome", record, expected_revision, parent_id, related_changes=related_changes, origin=origin, author=author)

    def _add_model(self, record: dict, parent_id: str, participants: list[str], expected_revision: str, related_changes: list | None = None, origin: str = "ai-inferred", author: str = "agent"):
        return self._add("Model", record, expected_revision, parent_id, participants, related_changes, origin, author)

    def _add_requirement(self, record: dict, parent_id: str, expected_revision: str, origin: str = "ai-inferred", author: str = "agent"):
        return self._add("Requirement", record, expected_revision, parent_id, origin=origin, author=author)

    def _link_records(self, type: str, source: str, target: str, rationale: str, expected_revision: str,
                      origin: str = "ai-inferred", author: str = "agent"):
        return self._propose_change("Link existing records", [{"op": "add_relationship", "relationship": relationship(type, source, target, rationale)}], expected_revision, origin, author)

    def _update_requirement(self, record_id: str, patch: dict, expected_revision: str, origin: str = "ai-inferred", author: str = "agent"):
        if self._get_record(record_id)["record"]["type"] != "Requirement":
            raise ServiceError("record.type", "update_requirement requires a Requirement id.")
        return self._propose_change("Update requirement", [{"op": "update_record", "id": record_id, "patch": patch}], expected_revision, origin, author)

    def _import_slice(self, slug: str, expected_revision: str):
        changes = self.storage.legacy_changes(slug)
        return self._propose_change("Import legacy slice " + slug, changes, expected_revision)



def execute(root: Path, operation_name: str, **params) -> dict:
    """Construction errors share the same interface contract as operation errors."""
    try:
        return ModelService(root).execute(operation_name, **params)
    except ServiceError as exc:
        return result(findings=exc.findings, retryable=exc.retryable)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        from scl.findings import Finding
        return result(findings=[Finding("storage.load", f"Cannot load project: {exc}")])
