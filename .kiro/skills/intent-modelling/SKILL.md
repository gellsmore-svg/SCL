---
name: intent-modelling
description: Create, review, extend or validate an Intent → Outcome → Model → Requirement (IOMR) model with intent-model-kit. Use for traceability, impact analysis, modelling system↔system and human↔system interactions, reverse-engineering an existing system or document into IOMR, or regenerating the Mermaid traceability document.
metadata:
  tool: intent-model-kit
---

# Intent modelling (IOMR)

You maintain a traceable model of **why** work exists and **how** each requirement serves that
purpose. The model is plain JSON, validated and exported by `intent-model-kit` (`imk`).

## The chain

**Intent → Outcome → Model → Requirement.** Relationships point *up* the chain.

| Layer | Question it answers | Good example | Bad example |
|---|---|---|---|
| Intent | Why does this work exist? | "Meet repair SLAs" | "Build a scheduling app" (a solution) |
| Outcome | What observable change shows the intent is met? | "Every plan override has a recorded reason" | "Override feature" (a feature) |
| Model | Which interaction process produces the outcome? | "Dispatcher plan override: dispatcher → planning UI" | "Planning module" (a component) |
| Requirement | What verifiable statement specifies the model? | "SHALL refuse release of an overridden plan with no reason" | "Should be user-friendly" (not testable) |

| Relationship | From → To | Meaning |
|---|---|---|
| `delivers` | Outcome → Intent | the change realises the intent |
| `serves` | Model → Outcome | the interaction produces or enables the outcome |
| `specifies` | Requirement → Model | the requirement defines or constrains the interaction |
| `refines` | same type → same type | finer decomposition of a broader record |
| `involves` | Model → Actor / System | a participant in the interaction |
| `constrains` | Policy / Decision / Requirement → … | a bounding rule (not part of the trace) |
| `depends_on`, `supersedes`, `belongs_to` | various | context only |

A **Model** has `interaction`: `["system-system"]`, `["human-system"]` or both. HCI needs at least
one Actor and one System; S2S needs at least two Systems. Where the flow matters, add ordered
`steps` (`from`, `to`, `message`, optional `kind`: `sync` | `async` | `return`, optional `note`).
Every step participant must also be linked with `involves`.

Run `imk metamodel` for the exact types and fields of the project you're in. A project may use a
custom metamodel.

## Workflow

1. **Scope.** Read `imk.json`. Identify the sources (code, documents, spreadsheets, interviews).
   Declare each one under `sources` with a pinned `ref` (commit, issue, date) and a local `path`.
2. **Intents.** Write 2–5 business purposes. Each should still be true if the solution changed.
3. **Outcomes.** For each intent, write observable changes. Give each a `metadata.measure`.
4. **Models.** For each outcome, write the interaction process that produces it, with its
   participants and steps. Record a `status` and the gaps for anything `partial`.
5. **Requirements.** Write SHALL statements per model. Each needs `metadata.acceptance` with a
   concrete, checkable example, using real numbers where possible.
6. **Context.** Add Actors, Systems, Policies (rules) and Decisions (ADRs), and link them with
   `involves`, `constrains` and `depends_on`.
7. **Relationships.** Link every record up the chain. Each `rationale` explains *why* the link
   holds, in at least 20 characters.
8. **Validate and export.** Run `imk validate --strict` and fix everything. Then run
   `imk export markdown -o TRACEABILITY.md`.
9. **Report.** Say what the model shows, what is inferred, and which gaps and findings remain.

## Record templates

```json
{"id": "intent-<slug>", "type": "Intent", "name": "…", "description": "…",
"metadata": {"project": "project-<slug>", "basis": "stated", "evidence": ["src:path#L10-L20"]}}

{"id": "outcome-<slug>", "type": "Outcome", "name": "…", "description": "…",
"metadata": {"project": "project-<slug>", "basis": "derived", "measure": "…", "evidence": ["…"]}}

{"id": "model-<slug>", "type": "Model", "name": "…", "description": "…",
"interaction": ["human-system"], "status": "partial",
"steps": [
   {"from": "actor-<slug>", "to": "system-<slug>", "message": "…"},
   {"from": "system-<slug>", "to": "actor-<slug>", "message": "…", "kind": "return"}
],
"metadata": {"project": "project-<slug>", "basis": "derived", "gaps": "…", "evidence": ["…"]}}

{"id": "requirement-<slug>", "type": "Requirement", "name": "…",
"description": "The <system> SHALL …", "status": "planned",
"metadata": {"project": "project-<slug>", "basis": "derived",
   "acceptance": "Given …, when …, then …", "evidence": ["…"]}}

{"id": "<from-slug>-<verb>-<to-slug>", "type": "serves",
"from": "model-<slug>", "to": "outcome-<slug>", "rationale": "Why this link holds …"}
```

Ids are lowercase kebab-case, prefixed with the type slug (`intent-`, `outcome-`, `model-`,
`requirement-`, `actor-`, `system-`, `policy-`, `decision-`, `project-`).

## Slice workflow (default for new requirements)

When the user gives you a new or changed requirement in general terms, don't edit the layer files
directly. Produce a **model slice**:

1. **Understand the statement.** Restate who needs what and why. If the purpose is unclear, ask
   one question.
2. **Generate an inferred slice.**
   - Read the existing model first (`imk export json`, or the layer files) and **reuse** matching
     Intents, Outcomes, Models, Actors and Systems.
   - Create only what's missing. Put new nodes in `model/nodes/slice-<slug>.json` and new
     relationships in `model/relationships/slice-<slug>.json`.
   - Mark every new record with `metadata.slice: "<slug>"`, `status: "proposed"` and
     `metadata.basis: "inferred"`, unless a cited source states it (`stated`) or it follows
     directly from one (`derived`).
   - Run `imk validate --strict` and fix every finding.
3. **Present it for review.** List each record and link as *new* or *reused*, with the inference
   behind it, plus a diagram (`imk export mermaid --view trace:<intent-id>` or
   `--view sequence:<model-id>`). Ask the user to confirm or correct: intent fit, outcome
   measurability, participants and step order, testability of each acceptance criterion, honesty of
   evidence and basis, and anything out of scope. Don't integrate until the user approves.
4. **Integrate on approval.** Set `basis` and `status` as the review confirmed. Move the records
   into the layer files and the relationships into the relationship files, remove
   `metadata.slice`, and delete the slice files. Then run `imk validate --strict` and
   `imk export markdown -o TRACEABILITY.md`.

If the user rejects the slice, delete its two slice files.

## Rules

1. Use only the types and relationships the metamodel declares.
2. **Evidence discipline.** Never present an inference as a fact. Cite sources in
   `metadata.evidence` as `alias:path#anchor`, after opening the file and checking the cited lines.
   Set `metadata.basis` to `stated` (the source says it), `derived` (follows directly from the
   source) or `inferred` (your judgement).
3. **Status discipline.** Use `implemented` only with code or primary evidence. Use `partial`
   with `metadata.gaps`. Use `planned` for agreed work and `proposed` for suggestions. Use
   `retired` for superseded records, and add a `supersedes` link.
4. Keep the layers separate. Don't let a Requirement describe *why* (that belongs to the Intent),
   and don't let an Outcome name a component.
5. Every record above Requirement must be covered by the layer below. Every record must trace
   up to an Intent.
6. Show the proposed records and relationships before you edit model files, unless the user has
   asked you to proceed.
7. After any change, validate with `--strict` and regenerate the document.
8. Don't hand-edit `TRACEABILITY.md`. It's generated.

## Fixing common validation findings

| Rule | Usual fix |
|---|---|
| `record.id-prefix` | rename the id so it starts with its type slug |
| `rel.legality` | the relationship type doesn't allow these endpoint types (check the table above) |
| `rel.rationale` | write a real reason of at least 20 characters |
| `trace.reach-intent` | add the missing `delivers` / `serves` / `specifies` link |
| `trace.coverage` | add a lower-layer record (for example a Requirement for an uncovered Model) |
| `model.participants` | add `involves` for each participant; check HCI/S2S participant types |
| `model.steps` | a step references a participant that isn't involved, or is missing `message` |
| `ref.evidence` | declare the source alias, or fix the cited path |
| `ref.unevidenced` | add evidence to the chain record (required once `sources` are declared) |
| `expect.*` | satisfy the project's own obligations in `imk.json` |
