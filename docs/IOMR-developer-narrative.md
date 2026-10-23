# IOMR — how the system works and the constraints you build within, for a developer

> **Reader:** a developer who knows the stack, the patterns and how code is built here.
> **What you already know:** semantic versioning, schema validation, CI, how a CLI and a repo fit
> together — none of that is re-explained below. **Your next step:** understand IOMR well enough to
> *build within its constraints*. **Human-constraint budget:** ~9 min read · cognitive load
> **Medium**. *Generated from the IOMR model (metamodel `iomr-evolved 2.0.0`); all requirement
> categories included, full technical depth. Human-judgement evaluation points are flagged inline
> with ⚖.*

## Why the system exists

IOMR has two reasons to exist, and every requirement below serves one of them.

First, **it governs its own evolution** (`intent-govern-framework`). The framework generates and
maintains other software systems, so it must hold itself to the same bar: evolve without breaking
consumers, ship changes that are reproducible, and make upgrades predictable.

Second, **it externalises the context that normally lives only in people's heads**
(`intent-externalise-context`) — intent, outcomes, rules, assumptions — in a form both a human and
an AI can consume, so that AI-generated work stays aligned with business intent instead of
faithfully implementing a misunderstanding.

A `Model` below is the **technology-independent logical interaction** that produces an outcome, not
an implementation. Requirements are the constraints on realising a Model — they are the boundaries
you build within, not the design itself.

## What success looks like

Success is a set of answerable questions, each tied to an Outcome:

- *Are framework releases consistent, reproducible, and predictable to upgrade?* (automated checks)
- *Is business intent still traceable, and does context survive people leaving and AI sessions
  ending?* ⚖ (the survival question is judged by a human)
- *Do AI-generated solutions stay outcome-aligned, and can a human inspect the AI's understanding
  before anything is built?* ⚖
- *Does the constraint language reliably bound solutions without rejecting novel-but-conformant
  ones?* ⚖ (a vector trade-off, not a yes/no)
- *Does a repo verify against the one authoritative model without forking a second truth?* ⚖

Where an answer is judged by a human rather than a machine, it is marked ⚖ — those are the points
where your CI cannot catch a mistake for you.

---

## Slice 1 — Releases are consistent and reproducible

*Outcomes: `outcome-consistent-frameworks`, `outcome-reproducible-releases` (both automated).*

The **Release Model** (`model-release`, system-system, implemented) is the interaction that turns
source into a consumable release. Its constraints:

- **Releases are versioned** (`requirement-versioned`, delivery) — every release carries a SemVer
  in its `iomr-manifest.json`, matching the folder name `vX.Y.Z`.
- **Releases include change documentation** (`requirement-change-docs`, governance) — `RELEASE.md`
  and `CHANGELOG.md` present in every release folder.
- **Releases are reproducible** (`requirement-reproducible`, delivery) — rebuilding from source at
  the tag yields byte-identical `iomr-kit` content. This is the load-bearing one: it is what makes
  "reproducible" mechanically checkable rather than aspirational.
- **Releases are self-contained** (`requirement-self-contained`, architectural) — a release folder
  copied in isolation is consumable with no external references.

The **Repository Model** (`model-repository`, implemented) constrains the layout itself:
**the repository has the required structure** (`requirement-repository-structure`, architectural) —
`src`, `releases`, `meta/iomr-model`, `changelog`, `docs`, and a root `iomr-manifest.json` all
exist, enforced by `validate-framework.py`.

The **Governance Model** (`model-governance`, implemented) adds the quality gates:
**validation instructions** ship with each release (`requirement-validation-instructions`,
governance — a `VALIDATION_CHECKLIST.md`); each release **passes consistency validation**
(`requirement-consistency-validation`, governance — `validate-framework.py` reports VALID, zero
errors); and **refines discipline is enforced** (`requirement-refines-discipline-enforced`,
governance) — same-kind decomposition uses only the typed `refines` edge across all four layers,
nesting deeper than 2 levels within a layer is flagged, and Outcome decomposition is kept distinct
from vector measurement.

## Slice 2 — Upgrades are predictable

*Outcomes: `outcome-predictable-upgrades` (automated), `outcome-backwards-compatibility` ⚖
(human-judgement).*

The **Upgrade Model** (`model-upgrade`, human-system, implemented): every release after the first
**includes upgrade instructions** (`requirement-upgrade-instructions`, delivery) — an
`UPGRADE_FROM_v<previous>.md` guide. ⚖ Whether backwards compatibility was preserved "where
practical" is a human-judgement Outcome — there is no automated gate for it, so the judgement sits
with the maintainer at release time.

## Slice 3 — A release only happens when consumers are actually affected

*Outcomes: `outcome-predictable-upgrades`, `outcome-releases-mean-consumer-impact` (automated).*

This is the slice that keeps internal churn out of the release stream. The **Release Eligibility
Model** (`model-release-eligibility`, implemented):

- **Release Eligibility Rule** (`requirement-release-eligibility`, governance) — a release may be
  cut only when at least one project-consumable asset changed (`/src/templates`, `/src/prompts`,
  `/src/schemas`, `/src/framework`, `/src/tooling`, `/src/examples`, or project-facing docs/install/
  upgrade processes). Changes touching only internal governance assets (`/meta`, `/internal`,
  `/research`, `/design-work`, `changelog/`) are recorded as framework-development activity, not a
  release.
- **Consumer Impact Test** (`requirement-consumer-impact-test`, governance) — before any release,
  answer: *would a project on the previous release behave differently if upgraded?* NO → no release.
  YES → the release records the specific consumer-visible behavioural difference.

The **Development & Release Lifecycle Model** (`model-development-release-lifecycle`, implemented)
sequences the whole thing:

- **Four-step lifecycle** (`requirement-lifecycle-four-steps`, governance) — (1) evolve the
  meta-model until it is a release candidate; (2) generate downstream artifacts from it; (3) AI-test
  those artifacts; (4) release only on an explicit, documented human green light.
- **The meta-model is the source of truth** (`requirement-model-is-source-of-truth`, governance) —
  artifacts are derived from the model, never the primary authored source. Where an artifact
  disagrees with the model, the model wins and the artifact is regenerated. *(This is why
  `TRACEABILITY.md` and these narrative docs are generated, not hand-edited.)*
- **AI-test emergent artifacts before release** (`requirement-ai-test-before-release`, delivery) —
  `imk validate --strict`, framework self-validation and engine tests must pass before a candidate
  is offered for green light.

## Slice 4 — AI tools can consume the assets

*Outcome: `outcome-ai-consumable` (automated).*

The **AI Consumption Model** (`model-ai-consumption`, system-system, implemented):
**version information is machine-discoverable** (`requirement-version-discovery`, functional) — an
AI tool reads a project manifest and resolves `iomrVersion`, `modelLocation` and upgrade
eligibility with no human input, validating against `project-manifest.schema.json`.

## Slice 5 — The model captures *why*, and keeps it inspectable

*Outcomes: `outcome-intent-visible` (automated), `outcome-context-survives` ⚖,
`outcome-ai-outcome-aligned` ⚖.*

The **Contextual Reasoning Model** (`model-contextual-reasoning`, human-system, implemented) is the
heart of the second intent. Its constraints:

- **Capture why, not only what** (`requirement-capture-why`, governance) — a model holds at least
  one Intent and one Outcome beyond its Requirements, and every Requirement traces up to an Intent.
- **Context is persistent and inspectable** (`requirement-context-persistent-inspectable`,
  non-functional) — from the repository alone, a new person or AI session can reconstruct the full
  contextual network with no reliance on tacit knowledge or session state.
- **Raise a gap challenge rather than invent interactions** (`requirement-raise-gap-challenge`,
  governance) — on a suspected missing interaction the AI emits a `POTENTIAL MODEL GAP` challenge
  (observation / concern / possibilities / question) instead of adding an assumed interaction as
  fact.
- **Models and Requirements hold test context before tests are derived**
  (`requirement-model-holds-test-preconditions`, governance, **planned**) — preconditions, trigger,
  expected (and failure/recovery where they exist) live in the model first; tests are derived from
  it, never patched only in the test.

The **Human-Authored IOMR Mode** (`model-human-authored-iomr`, implemented):
**support Mode 1** (`requirement-support-human-authored-mode`, functional) — a human authors
Intent/Outcomes/Models/Requirements and the AI treats Intent as primary guidance and Requirements
as hard boundaries, inventing none of its own.

⚖ Two of this slice's Outcomes — context surviving personnel/session boundaries, and solutions
staying outcome-aligned — are human-judgement. Validation proves the structure is present; it
cannot prove the captured context is *correct*.

## Slice 6 — The AI's understanding is inspectable before implementation

*Outcomes: `outcome-ai-outcome-aligned` ⚖, `outcome-ai-understanding-inspectable` ⚖.*

The **AI-Inferred IOMR Mode** (`model-ai-inferred-iomr`, implemented):

- **Support Mode 2** (`requirement-support-ai-inferred-mode`, functional) — the AI infers a
  proposed IOMR slice from a high-level request, marked `proposed`/`inferred`, and no implementation
  proceeds until a human approves it.
- **Expose AI understanding before implementation** (`requirement-expose-ai-understanding`,
  governance) — every inferred record states its basis and rationale so a stakeholder can catch a
  misaligned assumption pre-implementation.
- **Material emergent design choices are surfaced as proposed Decisions**
  (`requirement-emergent-design-surfaced`, governance, **planned**) — a design/UX choice no
  Requirement dictated that materially shapes UX becomes a `proposed` Decision (design category) for
  human approval; incidental choices are left free, not forced into the model.

⚖ Both Outcomes here are human-judgement: the whole point is a human judging whether the AI
understood correctly.

## Slice 7 — The reviewer understands the system at minimum cost

*Outcome: `outcome-reviewers-understand-min-constraint` ⚖ (vector).*

The **Requirements Narrative Generation Model** (`model-requirements-narrative`, implemented) is the
Model this very document realises:

- **One narrative per role** (`requirement-narrative-per-role`, functional) — developer, tester,
  power-user, each naming its role, reader-model and next step.
- **Scope requirements to the role** (`requirement-narrative-role-scope`, functional) — developer
  and tester get every requirement; the power-user gets only non-technical ones, with technical
  requirements restated in business terms or cut.
- **Optimise to a human-constraint budget** (`requirement-narrative-human-constraint-budget`,
  non-functional) — each document records and minimises read-time and cognitive load while keeping
  the role-relevant integrity set visible; over-budget paths split into touchpoints.
- **Every narrative claim traces to a record** (`requirement-narrative-traceable`, governance) —
  regenerating from the model reproduces the document's substance.
- **Flag human-judgement evaluation points** (`requirement-narrative-flag-manual-eval`, governance)
  — exactly the ⚖ markers you are reading.

⚖ Whether a reviewer actually reaches their next step within budget without a dropped constraint is
a vector human-judgement Outcome.

## Slice 8 — Unresolved uncertainty is visible, not hidden

*Outcome: `outcome-uncertainty-visible` ⚖.*

The **Open Question Management Model** (`model-open-question-management`, implemented):

- **Single authoritative repository** (`requirement-open-questions-central`, governance) —
  `meta/open-questions.md` is the only independent list; everything else references by ID.
- **Required fields** (`requirement-open-question-fields`, governance) — eleven fields per
  question, Risk Level ∈ {Critical, High, Medium, Low, Informational}.
- **Questions influence decisions and escalate** (`requirement-open-question-influence`, governance)
  — a recommendation depending on an unresolved High/Critical question must name it and its risk and
  state that results may change once resolved.

## Slice 9 — Required skills are verified before significant operations

*Outcome: `outcome-prerequisites-verified` (mixed evaluation).*

The **AI Harness Skill Validation Model** (`model-skill-validation`, implemented):
**a complete skills registry exists** (`requirement-skills-registry`, governance —
`meta/required-skills.md`, five fields per skill), and the harness **verifies skills before
significant operations** (`requirement-verify-skills-before-ops`, governance) — Skill Discovery →
Verification → Execution; a missing *critical* skill halts execution with a FAIL report naming the
skill, impact and action required.

## Slice 10 — The constraint language bounds solutions without restricting them

*Outcome: `outcome-constraints-reliable-not-restrictive` ⚖ (vector).*

This is the interpreter contract — how an engine executes an IOMR model. The **IOMR Interpreter
Contract Model** (`model-interpreter-contract`, system-system, **partial**):

- **Execution honours the layer roles** (`requirement-interpreter-honours-layers`, functional) —
  Intent is the dominant constraint, Outcomes are optimisation targets, Models are the logical shape
  to realise, Requirements are hard boundaries; the engine explores freely within them, and its
  internal method is not prescribed.
- **Never fail a conformant solution for unfamiliarity** (`requirement-no-expressiveness-penalty`,
  governance) — only an actual boundary violation may fail a solution; failing a novel-but-valid
  route is itself a defect.

The **Implementation Conformance Model** (`model-conformance-check`, **planned**):
**conformance is assessed per-Requirement against acceptance**
(`requirement-conformance-per-requirement`, delivery) — each Requirement constraining the relevant
Model is checked against its acceptance; automatable where machine-checkable, otherwise a flagged
human-judgement point.

⚖ This Outcome is a vector: it balances *solutions stay in bounds* against *conformant-but-novel
implementations still pass* — a trade-off, not a single pass/fail.

## Slice 11 — A repo verifies against the authoritative model without forking the truth

*Outcome: `outcome-verification-role-aligned` ⚖ (vector). All requirements below are **planned**.*

This is the largest forward-looking slice. Three Models carry it.

**Repository Verification Role Model** (`model-verification-role`, planned):

- **Declare a verification role; AI auto-adopts it** (`requirement-declare-verification-role`,
  architectural) — a `role` field in the project manifest ∈ {development, solution-test} plus a
  `.kiro/steering` file; absent field defaults to `development` (backwards-compatible).
- **Development role verifies at single-Model (unit) scope** (`requirement-unit-scope-single-model`,
  functional) — checks only the Requirements constraining the one Model an artefact realises.
- **Solution-test role verifies at trace-chain scope** (`requirement-solution-scope-trace-chain`,
  functional) — verifies along Model → realises → Outcome → evidences → Intent, against a read-only
  pinned snapshot of a released model.
- **Re-pin triage** (`requirement-repin-triage`, governance) — advancing the pinned snapshot diffs
  against the old pin and classifies every affected trace-chain unchanged / intentionally-changed /
  regressed; intentionally-changed must be reconfirmed green before the pin advances; a regressed
  chain blocks it.
- **Solution-test coverage is measured against the model** (`requirement-solution-coverage`,
  governance) — every in-scope Outcome evidenced by ≥1 test, every machine-checkable Requirement
  exercised by ≥1 test; gaps are reported against model elements, not lines of code.
- **Cross-System expectations are referenced contracts, never copied**
  (`requirement-cross-system-contract`, integration) — the contract Requirement is owned by the
  providing System's model and referenced by id/version from the consumer, never duplicated.

**Canonical Test Definition & Adapter Model** (`model-canonical-test-definition`, planned):

- **Tests are framework-agnostic; runners are adapters**
  (`requirement-test-definition-framework-agnostic`, architectural) — a test is a Canonical Test
  Definition in IOMR terms; no runner name (Playwright, etc.) appears in the authoritative model.
- **CTDs are declarative** (`requirement-ctd-declarative`, architectural) — state preconditions /
  trigger / expected and the acceptance/measurement evidenced; no selectors, URLs or click
  sequences; any imperative hint is optional and non-binding.
- **Elements are addressed by stable semantic locators**
  (`requirement-semantic-locator-contract`, architectural) — test ids or ARIA role/name, not
  CSS/XPath or position; a fragile fallback is recorded as an application-owned compromise.
- **Canonical, adapter-independent, traceable results** (`requirement-canonical-test-result`,
  audit) — each result links to the acceptance/measurement it evidenced plus the snapshot version
  and run metadata; no adapter report format lives in the model.

**Execution Adapter Model** (`model-execution-adapter`, planned):

- **Deterministic adapter resolution; no inferential execution**
  (`requirement-execution-adapter-deterministic`, architectural) — Level 0 (explicit recipes) for
  v1, Level 1 (compositional) as the growth path; Level 2 (inferential path-finding) is forbidden,
  so the same CTD yields the same actions every run.
- **Provisioning is separate from execution** (`requirement-provisioning-separate`, architectural)
  — provision/teardown is a different adapter with privileged access; the execution adapter holds
  only user-level power; the model names capabilities, not adapters.
- **Secrets are referenced, never embedded** (`requirement-secrets-referenced-not-embedded`,
  security) — no credential appears in the model, CTDs, result records or repo; only references
  (role names, profile ids, secret names), resolved at runtime from an external store (GitLab CI/CD
  for v1).

⚖ This Outcome is a vector human-judgement: it balances *the repo's role drives the correct
conformance scope* against *the solution-test repo verifies only a read-only pinned snapshot — no
second, divergent truth*.

---

## The whole, briefly

IOMR is a self-governing framework: it writes down *why* work exists and *how* each requirement
serves that why, releases only when consumers are genuinely affected, and generates every artifact
(including this document) from one authoritative model so nothing drifts. Today, releases,
governance, context-capture, dual authoring modes and skill-gating are **implemented**; the
interpreter contract is **partial**; and the whole verification/test-adapter layer (Slices 10–11) is
**planned** — that is where your next build work lives, and where the model already states the
boundaries you must build within.

**Your next step:** build within these constraints. For `planned` Models, the Requirements above are
the contract your implementation must satisfy; for the ⚖ points, remember your CI cannot certify
them — a human judgement is required and owned.

---
*Coverage: all requirement categories included — delivery, governance, architectural, functional,
non-functional, audit, integration, security. Human-judgement evaluation points flagged inline with
⚖ (Outcomes: backwards-compatibility, context-survives, ai-outcome-aligned, ai-understanding-
inspectable, reviewers-understand-min-constraint, uncertainty-visible, constraints-reliable-not-
restrictive, verification-role-aligned; plus the mixed-evaluation prerequisites-verified Outcome).*
