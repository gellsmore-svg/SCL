# Open questions

This is the only independent list. Refer to a question by its ID.

## OQ-001

- ID: OQ-001
- Question: Where is the line between a constraint that blocks a real violation and a constraint that rejects a novel conforming solution?
- Context: outcome-constraints-reliable-not-restrictive is a vector judgement. The interpreter checks explicit boundaries only. No numeric threshold is stated.
- Raised by: maintainer
- Date raised: 2026-10-23
- Status: open
- Risk Level: High
- Owner: maintainer
- Blocks: model-interpreter-contract
- Resolution: unresolved
- Evidence: spec:docs/IOMR-developer-narrative.md#Slice 10 — The constraint language bounds solutions without restricting them

## OQ-002

- ID: OQ-002
- Question: What are the level-1 composition rules for an execution adapter, given that level-2 path finding is forbidden?
- Context: requirement-execution-adapter-deterministic names level 0 for v1 and level 1 as the growth path. The composition rules are not specified.
- Raised by: maintainer
- Date raised: 2026-10-23
- Status: open
- Risk Level: Medium
- Owner: maintainer
- Blocks: model-execution-adapter
- Resolution: unresolved
- Evidence: spec:docs/IOMR-developer-narrative.md#Slice 11 — A repo verifies against the authoritative model without forking the truth
