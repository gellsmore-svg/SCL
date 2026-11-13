---
name: intent-modelling
description: Create, review, extend and validate Intent → Outcome → Model → Requirement models through the SCL semantic API. Use for traceability, impact analysis, modelling interactions, reverse engineering, proposal review and governed integration.
---

# Intent modelling

Maintain why work exists, its observable outcomes, the interactions that produce them,
and the requirements constraining those interactions. Use the model service for authoring.
Direct modification of canonical JSON arrays is unsupported for ordinary agents.

## Start with existing meaning

1. Call `scl_get_context` with a short query. Without MCP, use
   `imk api get_context --json '{"query":"reason"}'` (or the installed `scl` command).
   Use the returned model revision, sources, constraints and operation names.
2. Use `scl_find_records`, `scl_get_record` and `scl_get_trace` to find reusable identities.
   Use `record_id` for `get_record` and `get_trace`. For exact CLI parameters, call
   `get_api_schema` with `operation` (for example `get_record`).
   Keep queries focused; use `offset` and `limit` (maximum 100). Avoid exporting the whole model.
3. Read relevant source evidence. Keep stated facts, direct derivations and AI inferences distinct.
   Query `scl_get_metamodel` for the supported `iomr-evolved` 2.0.0 contract.

## Model the chain

| Layer | Question | Required detail |
|---|---|---|
| Intent | Why does the work exist? | A purpose that survives a change of solution |
| Outcome | What observable change fulfils it? | `metadata.measure` |
| Model | Which interaction produces it? | Participants, interaction kind and any ordered steps |
| Requirement | What constrains that interaction? | SHALL statement and `metadata.acceptance` |

`delivers` connects Outcome to Intent; `serves` connects Model to Outcome;
`specifies` connects Requirement to Model. Every chain must reach an Intent and
higher layers must have lower-layer coverage. A Model needs `involves` links to
at least one Actor and one System for `human-system`, or two Systems for `system-system`.
Step endpoints must be participants. `refines` remains same-type with the existing depth limit.

## Propose, validate, review, commit

- For one Requirement under a known Model, call `scl_add_requirement` with
  `parent_id`, `expected_revision` and `record`. Omit the id to generate it from the name.
  Supply a description, acceptance, evidence and an inference explanation when inferred.
  The service creates the link, detects duplicates, validates the whole candidate and returns a preview.
- Use `scl_add_model` with `participants` and `related_changes` for a complete interaction.
  Related records and links form one transaction; intermediate states need not validate.
- Use `scl_propose_change` for other coherent transactions. Supported changes:
  `add_record`, `update_record`, `add_relationship`, `remove_relationship`,
  `retire_record`, `declare_source`. No record deletion is exposed.
- Read `validation_status` and `validation_findings` inside `data`, even when the
  operation status is `ok`: storing a draft does not mean its candidate is valid.
- Fix findings with `scl_update_proposal`. Pass both `expected_revision` and
  `expected_proposal_revision`. Refresh/rebase on conflict; never silently overwrite.
- Present the proposed meaning, reused records, inferences and destructive impact for review.
  Call `scl_preview_change` with the reviewer's identity to obtain the exact signable payload.
  Review is distinct from validation. Do not claim an inference was human-authored.
- A trusted reviewer signs externally. Pass their detached signature to `scl_approve_change`.
  A typed name, `approved: true`, or a human-authored origin does not grant authority.
  If approval is unavailable, leave the valid proposal pending and report that state.
- Call `scl_commit_change` only after verified approval. It rechecks the revision and
  candidate and writes canonical records, relationships, provenance and generated documents.
  Confirm `committed_revision`; no separate regeneration is needed.
- Use `scl_reject_proposal` to withdraw an open proposal. This is a caller withdrawal,
  not an authenticated human rejection. Do not delete the audit record.

CLI operations have the same names without `scl_`:
`imk api add_requirement --json '{...}'`. Supply JSON inline, via stdin (`--json -`),
or from a request file (`--json @request.json`). The file is an API request, not canonical storage.
See `docs/api-modelling.md` for complete examples and configuration.

## Evidence and lifecycle discipline

Use `metadata.basis`: `stated` for a source's statement, `derived` for a direct
consequence, `inferred` for judgement. Record `metadata.inference` for inferred records.
Cite evidence as `alias:path#anchor` only after checking it. New source declarations
can be proposed with `declare_source`; its file bytes are covered by review.

Use `implemented` only with evidence, `partial` with `metadata.gaps`, and `planned`
for agreed future work. Proposal lifecycle and a record's intended status are separate.
On integration, inferred basis becomes `derived` and proposed record status becomes
`planned`; original basis, inference, evidence and review identity remain in provenance.
Retire through `retire_record` with a same-type successor. Never remove historical records.

Do not hand-edit generated traceability or role narratives. Read-only exports remain available.
Legacy Cairn slices can be imported with `scl_import_slice`, then completed and reviewed.
Do not call the removed `integrate_slice` writer. For recovery, follow the administrator
procedure in `docs/api-modelling.md`; do not improvise changes to canonical files or receipts.
