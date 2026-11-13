# API-driven IOMR modelling

The model is a semantic graph governed through `ModelService`. JSON remains its
storage format. CLI and MCP call the same `execute(operation, **parameters)` boundary.
The stdlib service supports Python 3.11+. MCP is an optional official Python SDK dependency.
HTTP, databases, remote identity providers and an execution runtime are not implemented.

## Architecture

- `domain.py`: isolated candidate changes, semantic helpers, impact traversal and
  complete structural validation using the existing IOMR validator.
- `service.py`: discovery, proposal lifecycle, validation, approval and integration.
- `storage.py`: `Storage` protocol and `JsonStorage`; project paths, stable file
  ownership, revisions, proposals, receipts, locking and recoverable writes.
- `approval.py`: detached SSH signature verification. The service never signs.
- `cli.py` and `mcp_server.py`: interface adapters without independent mutation rules.
- `governance.py`: read-only trusted CI verifier for signed canonical transitions.

The existing metamodel remains `iomr-evolved` 2.0.0. This is not a generic arbitrary
metamodel interpreter. Record types, legality, refinement, traceability, participants,
evidence and status rules retain their existing meanings.

## Install and discover

```sh
python3 -m pip install -e .
scl --root /path/to/project api get_context --json '{"query":"override","limit":5}'
# Repository launcher and historical alias are retained:
./imk api get_model_revision
```

Install MCP separately:

```sh
python3 -m pip install -e '.[mcp]'
scl-mcp --root /path/to/project
# Equivalent startup:
python3 -m scl.mcp_server --root /path/to/project
```

MCP SDK 2.3.x is the verified baseline (`mcp>=2.3,<3`). Server transport is local stdio.
For Claude Desktop or another host using `mcpServers`:

```json
{"mcpServers":{"scl":{"command":"/path/to/venv/bin/scl-mcp","args":["--root","/path/to/project"]}}}
```

For Kiro, use the same entry under `mcpServers` in its MCP configuration. For Codex:

```toml
[mcp_servers.scl]
command = "/path/to/venv/bin/scl-mcp"
args = ["--root", "/path/to/project"]
```

For CLI parameter schemas, call `imk api get_api_schema --json '{"operation":"add_requirement"}'`.

Use the absolute executable in the installed environment. MCP discovery supplies named
tools, descriptions, input and output schemas and read/write annotations. Without MCP,
`imk api OPERATION --json '{...}'` exposes identical service contracts. Use `--json -`
for stdin, or `--json @request.json` for a coherent request stored outside canonical arrays.

## Project configuration and compatibility

Existing `imk.json` files continue to work. The `model` location may be project-specific;
metamodel validation now respects it. Canonical `nodes/*.json` and `relationships/*.json`
retain their existing owners and order. New records go to the first sorted canonical file,
or to an explicit destination. Default filenames are used only when a directory is empty.

```json
{
  "metamodel":"iomr-evolved", "metamodelVersion":"2.0.0", "model":"knowledge",
  "sources":[{"alias":"brief","ref":"2026-11-13","path":"docs/brief.md"}],
  "storage":{"nodes":"knowledge/nodes/domain.json","relationships":"knowledge/relationships/graph.json"},
  "expect":[]
}
```

All managed paths must be inside the project and free of symlinks. No SCL project id is
assumed. A source must exist locally; `declare_source` adds its declaration as a reviewed
change. Once sources exist, all chain records require evidence, as before. Changing
already-declared source content changes the revision. Use a new source version/alias
in a proposal instead of editing evidence behind previously reviewed records.

The root project must already contain a valid model and metamodel; this release does
not invent a project's initial intent. Existing consumer `consume.py` kits, version
discovery, exports, Cairn checking, skills and strict framework checks remain supported.
A project declaring a skills registry must pass it. Framework checkouts also retain
framework and behaviour gates on candidate integration; consumers need no release folders.

## Common operation: add a Requirement

Discover the parent and revision with `get_context`, `find_records`, `get_record` or
`get_trace`. With a known Model and revision, one authoring operation suffices:

```json
{
  "parent_id":"model-plan-override",
  "expected_revision":"REVISION_FROM_CONTEXT",
  "record":{
    "name":"Preserve override reason",
    "description":"The system SHALL retain the reason entered for each override.",
    "metadata":{
      "basis":"inferred",
      "inference":"Reason retention appears necessary to explain the recorded override.",
      "acceptance":"Given an override with reason R, when retrieved, then its reason equals R.",
      "evidence":["brief:docs/brief.md#Override reasons"]
    }
  }
}
```

Send this to `scl_add_requirement` or `imk api add_requirement`. The response includes
`proposal_id`, `proposal_revision`, `validation_status`, findings, affected identities,
impact, generated filenames and a review payload. The generated id is
`requirement-preserve-override-reason`; a `specifies` link is created automatically.
Duplicate names/ids produce a reuse diagnostic rather than silently creating alternatives.

## Complete interaction in one proposal

Use existing Intent/Outcome/participant identities when they fit. `related_changes`
allows required coverage to be added in the same transaction:

```json
{
  "parent_id":"outcome-overrides-explained",
  "expected_revision":"REVISION_FROM_CONTEXT",
  "participants":["actor-dispatcher","system-planning-ui"],
  "record":{
    "name":"Explain override", "description":"A dispatcher records the reason for an override.",
    "interaction":["human-system"],
    "steps":[{"from":"actor-dispatcher","to":"system-planning-ui","message":"override reason"}],
    "metadata":{"basis":"inferred","inference":"Proposed interaction for review.","evidence":["brief:docs/brief.md#Override reasons"]}
  },
  "related_changes":[
    {"op":"add_record","record":{
      "id":"requirement-override-reason","type":"Requirement","name":"Override reason",
      "description":"The system SHALL store the reason.",
      "metadata":{"basis":"inferred","inference":"Constraint inferred from the interaction.",
        "acceptance":"Given R, when stored, then R can be retrieved.","evidence":["brief:docs/brief.md#Override reasons"]}
    }},
    {"op":"add_relationship","relationship":{
      "type":"specifies","from":"requirement-override-reason","to":"model-explain-override",
      "rationale":"The reason constraint specifies the override explanation interaction."
    }}
  ]
}
```

Send this to `scl_add_model`. New participants can also be `add_record` entries in
`related_changes`. A general `propose_change` takes `title`, `changes`, `expected_revision`,
optional `origin` (`ai-inferred` by default) and an `author` claim. Names are claims, not
credentials. All changes require review, including those labelled human-authored.

Other operations: `add_intent`, `add_outcome`, `link_records`, `update_requirement`.
General updates use `{"op":"update_record","id":"...","patch":{...}}`. Metadata is
merged one level; lists and other fields are replaced. Id and type are immutable.
`remove_relationship` requires `id` and a reason of at least 20 characters.
`retire_record` requires `id`, `superseded_by` and a meaningful reason; it preserves
both records and adds a same-type `supersedes` link. Retired records cannot be edited.

## Validation, lifecycle and errors

Lifecycle: proposed → approved → committed, or proposed/approved → rejected.
Validation is computed each time, independently of lifecycle. `get_proposal` reads the
stored content; `preview_change`/`validate_proposal` evaluate the full candidate graph.
A proposed record's `status` represents its intended integrated lifecycle status;
proposal state is separate. Inferred records are projected as `derived` for candidate
validation, without giving them approval. Proposed record status integrates as `planned`.

Provenance records original basis/status, inference, evidence, author claim, origin,
previous record digest, proposal/change identities and verified reviewer. Existing
history is retained on later modification. The detached signature and exact file maps
live in the immutable committed proposal's receipt. A human-authored label never grants
permission by itself.

Every response has `status`, `model_revision`, `findings`, `retryable`, `data`.
Successful draft storage can have `status: ok` with `data.validation_status: invalid`;
read `data.validation_findings` before seeking approval. Commit and approval failures
use top-level findings and CLI exit 1. Error rule identifiers reuse structural rules
such as `rel.legality`, `trace.reach-intent`, `ref.evidence`, `model.participants`.
New rules include `revision.conflict`, `proposal.conflict`, `approval.required`,
`approval.invalid`, `approval.unavailable`, `storage.busy`, `governance.unsigned`.

`update_proposal` replaces the change list and requires `expected_proposal_revision`
and current `expected_revision`. It removes approval. Use it to rebase after another
transaction commits, revalidate and request fresh review. Material changes invalidate
old signatures even if somebody manually restores the approved flag.

Proposal IDs are content-derived: repeated identical creation returns the same proposal.
Repeated commit verifies its receipt and reports `already_committed`; it does not reapply.
Rejected/committed proposals cannot be reopened. `reject_proposal` records a caller
withdrawal, not an authenticated human review decision. Signed approval is the only
human authority asserted by this implementation.

## Trusted approval

Default operation is proposal-only. An administrator supplies an OpenSSH allowed-signers
file outside the checkout via `SCL_ALLOWED_SIGNERS`. The private key must remain with the
reviewer, outside the agent's accessible environment. Example allowed-signers entry:

```text
reviewer@example.org ssh-ed25519 AAAA_REVIEWERS_REAL_PUBLIC_KEY
```

1. Call `preview_change` with `proposal_id` and `reviewer: reviewer@example.org`.
2. Review the proposed records, complete findings, evidence and affected dependencies.
3. Save `data.approval_payload` in canonical form: JSON keys sorted, compact separators,
   UTF-8 with unescaped Unicode, followed by one newline. `scl.domain.canonical` implements it.
   A reviewer can extract it from a JSON response without executing branch code:

   ```sh
   python3 -c 'import json,sys; p=json.load(sys.stdin)["data"]["approval_payload"]; sys.stdout.write(json.dumps(p,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n")' < preview.json > approval.json
   ssh-keygen -Y sign -f /private/reviewer_key -n scl-iomr-v1 approval.json
   ```

4. Call `approve_change` with `proposal_id`, `identity`, the text of `approval.json.sig`
   as `signature`, and `expected_revision`. The service verifies the exact payload.
5. Call `commit_change` with `proposal_id` and `expected_revision`.

The signature binds reviewer identity, proposal content digest, prior revision and
complete before/after file-hash maps, including canonical files, metamodel/configuration,
declared source bytes and generated documents. Approval is not transferable to a
modified proposal or another model revision. No secret or signing operation is exposed
through MCP. An administrator may inject another verifier in a trusted embedding, but
must retain independent publication verification.

## Authoritative boundary and hosting setup

MCP is not a security boundary. A process with unrestricted checkout access can edit
files, replace service code or change its environment. Local locks do not stop it.
For real isolation, run an installed/pinned service under a separate OS identity,
restrict canonical paths to that writer, and keep reviewer private keys inaccessible.

For Git acceptance, require `IOMR authoritative boundary / signed-model-transition` on
the protected branch. The included GitHub `pull_request_target` workflow executes only
base-branch code against candidate files as data. It never imports or executes candidate
Python. Configure repository variable `SCL_REVIEW_SIGNERS` with independently administered
public signers. Protect workflow/service/policy changes with human review, dismiss stale
approvals, require the branch to be current, and prevent bypass/direct pushes.

This first PR installs the checker. It cannot validate itself using code absent from its
base. A maintainer must review this bootstrap, merge it, configure signers and activate
the required check. No branch-protection settings are silently changed by installation.
Without these hosting controls, the checker is available but not a mandatory acceptance
boundary. It detects bypass; it does not make local direct writes impossible.

The ordinary GitHub/GitLab test jobs are regression checks, not independent trust.
GitLab needs a protected CI-policy project or external required check that pins SCL and
supplies base/candidate trees and allowed signers. `docs/ci/gitlab-trusted-model.yml`
is the verifier job template; including an editable MR copy is insufficient. GitLab
hosting policy is not configured by this implementation.

Trusted CI verifies a continuous signature chain from the protected base to the candidate
snapshot, checks proposal digests, replays the reviewed operations using trusted domain code
in a fresh data-only workspace, and validates the full final graph and generated docs.
Use the same trusted service version for authoring and verification; change trusted rendering
code through a separately reviewed code update before relying on changed outputs.
Forged receipt JSON, changed canonical files, changed evidence and changed generated docs
cannot pass this check without a valid review signature. Non-model code changes still
need normal protected human review because they can affect future trusted behaviour.

## Transactions and recovery

Revisions hash managed file paths and bytes, including relevant configuration/evidence
and generated artifacts. They are not Git commit SHAs. Different filesystems preserving
the same bytes yield the same revision. Optimistic revision checking and an OS lock
serialize cooperative service writers. POSIX read operations share a read lock; Windows uses an exclusive lock. Separate callers cannot silently overwrite updates.

The JSON adapter prepares records and documents in memory, writes an undo journal, then
atomically replaces individual files. If any replacement fails, it restores the prior
files, proposal state and documents. After process interruption, the next service operation
rolls back a remaining journal before reading. Recovery failure is reported, never ignored.
Do not delete a pending journal. Use a service read, such as `get_model_revision`, to trigger
recovery after restoring disk space/permissions; if recovery still fails, keep the checkout
out of publication and restore a known-good Git commit into a clean worktree.

This is **recoverable multi-file persistence, not filesystem-wide atomicity**. Legacy
readers that ignore the lock can observe files during replacement. Filesystem durability
and network filesystem lock semantics are platform-dependent. Use local filesystems and
publish the complete model/proposal/receipt/docs in one Git commit, then a normal guarded
ref update. The service does not auto-commit unrelated repository work or push to Git.

For exceptional migration/recovery, use a clean trusted checkout and `import_slice` or
explicit proposal changes, validate, obtain review and integrate. Do not forge receipts
for hand edits. Source replacement or arbitrary storage-layout migration is not exposed
as a normal mutation operation; establish a reviewed new baseline with hosting administrators
when it cannot be expressed as supported changes. That is an explicit trust-root migration.

## Legacy and generated artefacts

`integrate_slice()` now raises `approval.required`; this intentional incompatibility closes
an unsafe writer. Cairn proposal generation and legacy slice reading remain available.
`import_slice` brings a legacy slice into the service; incomplete traceability/participants
must be completed before approval. Slice files remain as legacy draft history, excluded
from canonical loading. Do not include duplicate integrated legacy slices in exports.

Every successful commit regenerates traceability and all role narratives, removes obsolete
appendices, and stores them with the model transaction. Standalone exports remain read-only;
`regenerate` remains a repair command for existing workflows. Trusted CI rejects unsigned
changes to generated artifacts even if normal local commands can write them.
