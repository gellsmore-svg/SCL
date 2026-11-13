"""Read-only verifier for independently trusted CI. NEVER import candidate code.

Run this module from a pinned, protected checkout, supplying the untrusted tree
only as data. Policy/allowed_signers must come from protected configuration.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from scl.approval import SSHApproval, UnavailableApproval
from scl.contracts import ServiceError, result
from scl.domain import apply_changes, candidate_findings, digest
from scl.export import generated_findings
from scl.findings import Finding
from scl.storage import JsonStorage


def verify_transition(base: Path, candidate: Path, verifier) -> list[Finding]:
    try:
        old, new = JsonStorage(base), JsonStorage(candidate)
        before, after = old.snapshot(), new.snapshot()
        # No branch-controlled flags can disable the signed transition check.
        if before == after:
            return []
        current = digest(before)
        destination = digest(after)
        seen = set()
        chain = []
        receipts = []
        for path in sorted(new.path(".scl/receipts").glob("*.json")):
            relative = path.relative_to(new.root).as_posix()
            data = new.path(relative).read_bytes()
            if len(data) > 4_000_000:
                raise ServiceError("governance.receipt", "Receipt exceeds size limit.")
            receipts.append(json.loads(data))
        while current != destination:
            choices = [r for r in receipts if r.get("payload", {}).get("base_revision") == current]
            if len(choices) != 1 or current in seen:
                return [Finding("governance.unsigned", "Canonical/configuration/evidence/generated changes lack one continuous signed transition from the protected base. Rebase, review and commit through the service.")]
            seen.add(current)
            receipt = choices[0]
            payload = receipt["payload"]
            if payload.get("protocol") != "scl-iomr-v1" or digest(payload["before"]) != current or digest(payload["after"]) != payload.get("candidate_revision"):
                raise ServiceError("governance.receipt", "Receipt revisions do not match their signed file maps.")
            verifier.verify(payload, receipt["approval"])
            # Preserve and verify the coherent proposal itself, not only a marker.
            proposal = new.read_proposal(payload["proposal_id"])
            unsigned = {k: v for k, v in proposal.items() if k not in {"state", "approval", "committed_revision"}}
            if digest(unsigned) != payload["proposal_digest"] or proposal.get("state") != "committed":
                raise ServiceError("governance.proposal", "Committed proposal does not match the signed review.")
            chain.append((proposal, receipt))
            current = payload["candidate_revision"]
        replay_findings = replay_chain(old, new, chain)
        if replay_findings:
            return replay_findings
        loaded = new.load()
        return candidate_findings(loaded) + generated_findings(candidate, loaded)
    except ServiceError as exc:
        return exc.findings
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError) as exc:
        return [Finding("governance.invalid", f"Cannot verify the candidate: {exc}")]


def replay_chain(old: JsonStorage, new: JsonStorage, chain) -> list[Finding]:
    """Reproduce signed changes with trusted domain code in a fresh data-only tree."""
    with tempfile.TemporaryDirectory(prefix="scl-replay-") as directory:
        root = Path(directory)
        # Only model inputs/outputs are copied. Never import candidate code or
        # copy its .scl journal, .git configuration, hooks or executable tooling.
        for name in old.protected_paths():
            path = old.path(name)
            if path.is_file():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
        for proposal, receipt in chain:
            store = JsonStorage(root)
            payload = receipt["payload"]
            for change in proposal["changes"]:
                if change["op"] == "declare_source":
                    source = change["source"]
                    target = store.source_path(source)
                    supplied = new.source_path(source)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(supplied.read_bytes())
            with store.locked():
                if store.snapshot() != payload["before"]:
                    return [Finding("governance.replay", "Proposal inputs differ from the reviewed base.")]
                candidate, _impact = apply_changes(store.load(), proposal, payload["reviewer"])
                findings = candidate_findings(candidate)
                if findings:
                    return findings
                writes = store.candidate_files(candidate)
                if store.after_snapshot(writes) != payload["after"]:
                    return [Finding("governance.replay", "Reviewed operations do not reproduce the signed model and documents. Use the trusted service version and obtain fresh review.")]
                store.transaction(writes)
    return []


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--allowed-signers", type=Path)
    args = parser.parse_args(argv)
    verifier = SSHApproval(args.allowed_signers) if args.allowed_signers else UnavailableApproval()
    findings = verify_transition(args.base, args.candidate, verifier)
    print(json.dumps(result(findings=findings), indent=2))
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
