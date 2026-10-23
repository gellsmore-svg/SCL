---
name: narrative-arc
description: >
  Turn a large body of source material — a model, specification, codebase,
  analysis, research record, design, incident timeline or set of findings —
  into a reader-optimised explanatory narrative for one specific reader role:
  requirements documents, design docs, review packs, research write-ups,
  onboarding walkthroughs, post-mortems, proposals, reports, readable specs,
  expository chapters, or "explain this to <role>". Sequences the material
  as an arc that teaches the subject as it goes, scopes content to the role,
  applies the before-the-message method to every load-bearing phrase, and
  minimises the reader's time and cognitive load while keeping every relevant
  risk, dependency, assumption, uncertainty and constraint visible. Use for
  document-scale narrative work; use before-the-message alone for single
  messages. Do NOT use for fiction or creative storytelling, raw reference
  catalogues, or bulk content where completeness (not selection) is the goal.
metadata:
  short-description: "Role-optimised explanatory narrative from source material"
  composes: before-the-message
  generalises: "requirements-narrative (IOMR); see the 'Adapter: IOMR requirements' section"
---

# Narrative arc

You turn a body of source material into a document a **real reader** can get
through in the least time, with the least cognitive effort, and come away
understanding the subject well enough to take their next step.

The document is not a dump of the source. It is a **narrative arc** that
teaches the subject as it goes, built from the source's own natural units.

This skill **composes `before-the-message`**. Reuse its recipient model check
(Step 4) and recursive scoring loop (Step 5) on every load-bearing phrase, and
its CUV mapping (Step 3) and touchpoint rules (Step 6) at document scale. This
skill adds what before-the-message does not cover:

1. **Document-scale narrative sequencing** — an arc across many units.
2. **Role-specific scoping** — the same source yields different documents for
   different readers.
3. **A reading budget** — an explicit, recorded cost the document must fit.
4. **Source fidelity** — every claim traces to the source; the source wins.

> **Why.** The scarcest resource in most work is reader attention — a
> Theory-of-Constraints bottleneck. A document that is cheaper to understand
> gets read, gets challenged properly, and produces better decisions and
> better downstream work. When a document feeds generation (specs → code,
> briefs → drafts), its quality caps the quality of everything built from it.

---

## When to apply

Use when asked to write, restructure or review any **explanatory** document
built from a body of material larger than the reader should consume
directly: requirements, design docs, review packs, research or experiment
write-ups, onboarding guides, incident reviews, proposals, status reports,
handbooks, expository book chapters, "explain this system / finding / plan
to <role>".

Not for:
- A single message → `before-the-message`.
- The complete reference catalogue (traceability matrix, API reference,
  full findings log). The narrative is that catalogue's human-optimised
  **counterpart**; link to it, don't replace it.
- Fiction and creative storytelling — a different craft.

---

## 1. Identify the source and its units

Name the **source of truth** and break it into its natural **units** — the
pieces it already divides into. Do not invent a structure the source lacks.

| Source | Natural units |
|---|---|
| Intent / outcome / requirements model | Intent → Outcomes → Model → Requirements slices |
| Codebase or system | Capabilities / flows / components |
| Research or experiment record | Questions → rounds → findings → caveats |
| Analysis or audit | Failure modes / risks → requirements → plan |
| Incident | Timeline → causes → impact → actions |
| Proposal or decision | Problem → options → recommendation → risks |
| Book / long-form argument | Claims → evidence → implications |

For each unit record: what it is **for** (the goal it serves), what
**success or evidence** looks like, **how it works** (the mechanism), and what
**constrains or qualifies** it (rules, caveats, open questions). These four
facets feed the arc.

## 2. Profile the reader role

Produce **one document per role**. Each role is a before-the-message recipient:
fill in what they **already know**, what they **own**, their **one next step**,
and their **attention budget**.

Common roles (adapt or add; the source decides which apply):

| Role | Already knows | Next step | Default scope |
|---|---|---|---|
| **Builder** (developer, author, implementer) | the tools, patterns, craft | build within the constraints | everything, full technical depth |
| **Verifier** (tester, reviewer, auditor) | how to check, what evidence looks like | confirm it holds | everything, with evidence/acceptance foregrounded |
| **Domain owner** (power user, client, subject expert) | the domain, not the implementation | confirm it does the right thing | non-technical units only, in domain language |
| **Decision-maker** (manager, sponsor, committee) | goals, budget, trade-offs | decide / approve / prioritise | consequences, options, risks, cost |
| **Newcomer** (new team member, general reader) | little specific context | understand enough to start | foundations first, then the core path |

**Unspecified role.** If no role is given and stakes are low, pick the most
likely reader, state the assumption in the reader read, and proceed. If stakes
are high and the role is genuinely unknown, ask **one** plain-prose question.

## 3. Scope the units to the role

Tag each unit with a **category** (from the source if it has one —
e.g. functional / architectural / security / governance — or assigned by you).
Set per-role inclusion by category; a per-unit **audience override** in the
source wins over the category default.

- A unit **irrelevant** to the role may be cut.
- A unit that is technical but carries a **consequence the role owns** stays,
  restated as that consequence in the role's own frame — never in the
  builder's language.

**Integrity rule (non-negotiable).** Scoping may drop units irrelevant to the
role. It must never drop a **risk, dependency, assumption, uncertainty or
constraint relevant to that role**. Brevity never overrides the integrity set.

## 4. Build the arc

Order is **communication order, not dependency order**. Lead with the most
accessible reason the subject matters to this reader; let each section make
the next cheaper to understand.

1. **Opening — why it matters.** One short passage per top-level goal, in the
   reader's language. The most accessible consequence first, not the most
   foundational principle.
2. **What success (or the finding) looks like.** The outcomes, results or
   claims — framed as the questions they answer, with how each is answered or
   evidenced, in plain terms.
3. **Unit stories — how it works.** Walk the source **one unit at a time**:
   *here is a goal, here is how it is met, here is what must hold true.* Each
   story is small and self-contained. Sequence units so each reuses what the
   last established (a Relational CUV). Merge units this role would always
   read together.
4. **Constraints in context.** Put rules, caveats and open questions **where
   they bite**, inside the relevant story — not as a detached list at the
   end. For builders and verifiers, put acceptance or evidence inline; for
   domain owners and decision-makers, state each as a plain rule or
   consequence.
5. **Close — the whole, briefly.** The subject in a paragraph, and what the
   reader should now do (their next step).

Keep the boundary between **what the thing is** and **what constrains it**
visible in the prose — e.g. a logical model vs. the requirements on
implementing it; a finding vs. its caveats; a plan vs. its risks.

## 5. Write with the per-phrase method

Inherited from before-the-message Step 4. For every load-bearing phrase:

1. **Already-known check** — cut what the role's own expertise guarantees.
2. **Connection check** — use the role's vocabulary and metrics; attach new
   ideas to concepts already active in their mind.
3. **Lifting audit** — if a shorter phrase carries the same distinction, use it.

Introduce each new concept **once**, at the first unit that needs it, and reuse
the same term thereafter. Never let two words name one thing.

## 6. Score against the budget

Set the budget **before** drafting and record it at the top of the document:

- **Read-time** — minutes at ~200 wpm for this role's path (excluding
  on-demand appendices).
- **Cognitive load** (H/M/L) — driven by new concepts per passage,
  cross-references held in working memory, and jargon not already in the
  role's model.

Run before-the-message's recursive scoring loop (Step 5) on the **opening**,
the **close**, and any passage that feels heavy, scoring candidates on

`[Relevance, Accessibility, Local value, Enabling value, Recipient-fit, Focus, Brevity | Cognitive burden]`

Score **relative to the budget**, not in the abstract: Brevity is H only if
the passage fits its share of the read-time with margin; Cognitive burden is L
only if it adds no more concepts than its share allows. This keeps the vector
discriminating after the first round. Lift the weakest term; stop when no
revision improves one term without harming another. Do not over-iterate.

If the role's path exceeds its budget: compress first (merge units, cut
already-known material). If it still exceeds, **split into touchpoints** —
e.g. a 2-minute arc plus an on-demand detail appendix — each giving standalone
value. Never stage to steer the reader toward a conclusion.

## 7. Flag what the reader must own

Wherever a claim cannot be checked mechanically — evaluated by human judgement,
code-read but not reproduced, estimated rather than measured, single-source,
or deferred — **flag it in the narrative** at the point it matters. These are
places where downstream work cannot be verified automatically, and the reader
must own the judgement. Never smooth them away to make the document read
better.

## 8. Verify against the source

Before emitting:

- Every claim traces to a unit in the source (cite ids/paths where the source
  has them).
- No unit relevant to the role is missing; no integrity item relevant to the
  role was dropped. Check every **excluded** item individually: if it is a
  risk, dependency, assumption, uncertainty or constraint, re-ask "does this
  role own its consequence?" Scoping by category ("that's internal") is
  where integrity items most often leak out.
- Nothing technical reached a non-technical role in technical language.
- Every unverifiable point from §7 is flagged.
- If the narrative and the source disagree, **the source is the truth**: fix
  the source (or report the discrepancy), then regenerate. Never hand-tune the
  narrative away from its source.

---

## Output format (per document)

1. **Reader read** — 1–3 lines: role, what they already know, their one next
   step, the budget (read-time + cognitive load).
2. **The narrative** — opening → success → unit stories → constraints in
   context → close. This is the product; every word load-bearing.
3. **Coverage note** — which units/categories were included or excluded for
   this role and why, flagged unverifiable points, and a link to the complete
   reference source.

Emit one file per role (e.g. `<NAME>-builder.md`, `<NAME>-verifier.md`,
`<NAME>-domain-owner.md`) unless the user asks for a single document. Show the
working (unit map, scores, budget arithmetic) only on request or when stakes
are high.

When **reviewing** an existing document instead of writing one: give the
reader read and budget, then the specific changes — each tied to the arc,
role scope, integrity rule, budget, or per-phrase method — then the revised
sections.

---

## Guardrails

- Scoping removes **irrelevant** material only — never a risk, dependency,
  assumption, uncertainty or constraint relevant to the role.
- Never show a non-technical role a technical point in technical language.
- Reduce the **burden** of consuming the subject, never the subject itself.
  Preserve real distinctions, uncertainties and risks.
- The source is the truth; the narrative is derived from it.
- Not a persuasion tool: no hidden uncertainty, no staged campaigns, no
  treating the reader as passive.
- Respect the house style of the target corpus (voice, register, citation
  conventions) where one exists; this skill decides selection and order, not
  voice.
- Length is not quality in either direction. Minimise the reader's cost, not
  the content's integrity.

---

## Adapter: IOMR requirements

The original use case, preserved. When the source is an IOMR model
(`imk.json`, `imk export json`, or the layer files):

- **Units** are IOMR slices: Intent → its Outcomes → the Model that realises
  them → the Requirements that constrain it.
- **Roles:** developer = Builder, tester = Verifier, power end-user = Domain
  owner.
- **Category scoping** uses `Requirement.category`. Developer and tester get
  all categories. Power end-user gets `functional`, `governance`,
  `operational`; `architectural`, `non-functional`, `performance`,
  `security`, `delivery` are excluded **unless** the requirement carries a
  business consequence the user owns (then translated). A per-requirement
  `metadata.audience` override wins.
- **Success** = Outcomes as questions, answered via `measurement.kind` /
  `evaluatedBy`.
- A **Model** is a technology-independent logical interaction or
  transformation, not an implementation — write it that way; Requirements
  constrain realising it and are not part of it.
- **§7 flags:** any `evaluatedBy: human-judgement` Outcome or acceptance.
- **Output:** `REQUIREMENTS-developer.md`, `REQUIREMENTS-tester.md`,
  `REQUIREMENTS-power-user.md`. The complete reference remains
  `TRACEABILITY.md`.
