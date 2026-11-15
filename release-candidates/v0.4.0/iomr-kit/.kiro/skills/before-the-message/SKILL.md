---
name: before-the-message
description: >
  Draft, tighten or review high-stakes human communication — emails,
  Slack/Teams messages, status updates, risk escalations, review comments,
  PR descriptions, decision requests, stakeholder summaries, or "how do I
  phrase this?" — using the "Before the Message" model. Converges a large
  body of knowledge on the smallest coherent message that serves one
  specific recipient's next step; reads what the recipient already knows so
  no phrase does wasted lifting; recursively scores candidate wordings until
  they converge; never drops an assumption, uncertainty, dependency or risk
  for brevity. Use when the user asks to write, shorten, sharpen or critique
  a message to a named person or role, or invokes /before-the-message.
  Do NOT use for code generation, reference documentation, or bulk content
  where completeness (not selection) is the goal.
metadata:
  short-description: "Minimum sufficient message for a specific recipient"
  source: "Before the Message — Reducing communication noise and building understanding in software teams (working draft, October 2026)"
---

# Before the Message

Effective communication is the deliberate **selection and sequencing** of what
a recipient needs to take a useful next step — not the transfer of everything
the sender knows. Most of the work happens before the message is written.

The goal is **less noise, not a less complex subject**: reduce what the
recipient must process at once while keeping the distinctions, uncertainties
and evidence that matter.

Treat three resources as scarce and linked:

- **Attention** — effort the recipient can spend right now.
- **Opportunity** — credible occasions to raise the subject.
- **Trust** — their expectation that engaging with you will be worthwhile.
  Disciplined messages build it; noisy ones erode it.

## Procedure

Work through these steps in order. For low-stakes messages, run them
mentally and show only the output; for high-stakes ones, keep the working.

### 1. Establish inputs first

Before drafting, pin down:

| Input | Question |
|---|---|
| **Recipient** | Role → what do they already *know*, *own*, *value*, *can decide*? |
| **Attention budget** | How much they can spend now, stated concretely (e.g. "a 30-second Slack read", "2 minutes before standup"). Scoring in Step 5 is measured against it. |
| **Next step** | Exactly one: *understand*, *evaluate*, *decide*, or *act*. |
| **Context** | Why does this matter to *them*, in *this* situation, *now*? |
| **Contrast** | What changes between acting / deciding / investigating / deferring / doing nothing? |
| **Integrity set** | Assumptions, uncertainties, dependencies and risks that must stay visible even in the shortest version. |

The integrity set is a floor. Brevity may never remove an item from it.

If the recipient's role or knowledge is genuinely unknown **and** the stakes
are high, ask **one** clarifying question in plain prose rather than guessing.
Otherwise — including when no recipient is named at all — pick the most likely
recipient, state that assumption in the recipient read, and proceed.

### 2. Converge (context × contrast)

Keep a piece of material only if it:

- passes the **contrast test** — omitting it would change the recipient's
  conclusion or next step; **or**
- is in the **integrity set**.

Two-way stopping rule:

- **Stop removing** when further compression would drop a necessary item.
- **Stop adding** when more material no longer justifies the recipient's
  effort.

The result is the **minimum sufficient conceptual basis**.

### 3. Map Conceptual Units of Value (CUVs)

Break the basis into CUVs — small concepts, distinctions or relationships
that each do real intellectual work for the recipient. Tag each:

- **Local** — usable now.
- **Enabling** — unlocks later understanding.
- **Foundational** — other units depend on it.
- **Relational** — a *bridge* connecting things the recipient already holds.

Track two orders separately:

- **Structural order** — how the units depend on each other.
- **Communication order** — what to say first for *this* recipient.

Lead with the most **accessible consequence**, not the most foundational
principle. The facts stay constant; the entry point changes with the role.

### 4. Recipient model check — no wasted lifting

For every load-bearing phrase:

1. **Cut or compress** anything the recipient's role already guarantees they
   know.
2. **Use their vocabulary** — their metrics, accountabilities and terms — so
   the phrase attaches to a concept already active in their mind.
3. **Audit each word** — if a shorter phrase carries the same distinction,
   use it.

Every surviving phrase is either *new and load-bearing* or a *minimal bridge*
to what they already know.

### 5. Recursive scoring loop

1. Generate **2–4 candidate wordings** of the message (or of its lead CUV).
2. Score each on the vector, qualitatively H / M / L:

   `[Relevance, Accessibility, Local value, Enabling value, Recipient-fit, Focus, Brevity | Cognitive burden]`

   The first seven are benefits (higher is better). **Cognitive burden** is
   the cost term (lower is better).

   Score **relative to the attention budget**, not in the abstract: Brevity
   is H only if the message fits the budget with margin; Cognitive burden is
   L only if every new concept is one the budget can absorb. Absolute scoring
   saturates after one round (everything reads H); budget-relative scoring
   keeps the vector discriminating.
3. Take the leader. Lift its **single weakest term** — without dropping an
   integrity-set item and without exceeding the recipient's available
   attention. Re-score.
4. Repeat until the vector **converges**: no revision improves one term
   without harming another. Usually 1–3 rounds. Do not over-iterate.
5. Record the final scores so the choice is auditable.

### 6. Sequence across touchpoints — only if needed

Split into several messages only when one message would exceed the
recipient's attention or the integrity set cannot fit responsibly.

- Each touchpoint must give a **legitimate standalone benefit**.
- Never a concealed campaign toward a predetermined answer.
- If the matter is urgent or the decision is imminent, **do not stage** —
  send what they need now.

### 7. Adaptation note

State which recipient responses signal that you should **explain** further,
**stop**, **expand** to the next CUV, or **change course**. The cycle is
select → communicate → observe → adapt. Success means the recipient can
reason with, challenge and build on the idea — not echo your words.

## Output format

Lead with the message unless the user asked to see reasoning first.

1. **Recipient read** — 1–3 lines: who they are, what they know, the one
   next step, the attention budget (and any assumption made about them).
2. **Message** — the converged, ready-to-send text.
3. **Working** *(on request, or by default when high-stakes)* — integrity set,
   CUV map (type + structural vs. communication order), candidate scores and
   final vector.
4. **Adaptation note** — one line.

When **reviewing** an existing draft instead of writing one, give the same
recipient read, then the specific cuts/additions (each tied to the contrast
test, integrity set, or wasted-lifting check), then the revised message.

## Guardrails

- It reduces **consumption burden**, not subject complexity. Simplifying the
  system itself is design work, not communication work.
- **Integrity wins over brevity.** If an integrity item will not fit, add a
  touchpoint or lengthen the message — never drop it.
- It is **not a persuasion or manipulation tool.** Never hide uncertainty,
  never stage messages to steer someone to a predetermined answer, never
  treat the recipient as passive.
- **Length is not a proxy for quality** in either direction.
- Some subjects require full documentation, auditability or immediate
  comprehensive disclosure. A small message is useful only when it preserves
  the recipient's ability to judge responsibly; otherwise say so and write
  the complete version.

## Checklist

Outcome · Recipient · Context · Contrast · CUV · Dependencies · Integrity ·
Bandwidth · Adaptation.

## Worked illustration

**Situation.** An engineer has found that a third-party payments SDK the team
depends on reaches end-of-support in six weeks. They have pages of notes:
migration options, API diffs, a spike branch, test coverage gaps.

**Recipient read.** Engineering manager; owns the Q4 delivery plan and
headcount; knows the payments flow exists but not the SDK's internals.
Budget: a ~2-minute Slack read. Next step: **decide** whether to pull work into this
sprint.

**Integrity set.** Effort estimate is from a 1-day spike (±50%); the vendor
date is published but has slipped before; no security patches after
end-of-support.

**Unfocused version.**

> Hey — I've been looking into the PaySDK situation. v3 is going EOL and the
> v4 API changes the tokenisation model and the webhook signature scheme, and
> there are also some differences in how retries are handled. I did a spike
> and it looks doable but there are a lot of moving parts, and our test
> coverage on refunds is thin. We could also look at switching vendors.
> Thoughts?

No clear ask, internals the manager doesn't need, the decision is buried,
uncertainty is implicit.

**Candidates for the lead CUV (scored).**

| | Rel | Acc | Local | Enab | Fit | Focus | Brev | Burden |
|---|---|---|---|---|---|---|---|---|
| A: "PaySDK v3 EOL in 6 wks; v4 changes tokenisation + webhooks" | M | M | L | M | L | M | H | M |
| B: "Payments stop getting security patches on 4 Dec unless we migrate; ~2 sprint-weeks" | H | H | H | M | H | H | M | L |
| C: B + vendor-switch option | H | M | M | H | M | L | L | M |

B leads. Weakest term: Enabling (doesn't say what the decision unlocks).
Lift: add the decision and its deadline. Re-scored → Enab H, nothing else
drops. Converged.

**Converged message.**

> Decision needed by Friday: payments stop getting security patches on
> 4 Dec unless we migrate off PaySDK v3. Migration is ~2 sprint-weeks (from
> a 1-day spike, so ±50%). Pulling it into this sprint keeps a 2-week buffer;
> deferring a sprint leaves none. The vendor date has slipped before, but we
> shouldn't plan on it. Want me to bring options to Thursday's planning?

**Adaptation note.** If they ask "why so long?" → expand to the API-change
CUV; if they ask about alternatives → raise vendor switching; if they say
"go" → stop and send the plan.
