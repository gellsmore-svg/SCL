"""Machine-readable conformance contract for Cairn PLANs.

Cairn is primarily a spec (SPEC.md / GRAMMAR.md). This module is the small,
reusable surface a runtime can validate its plans against, so a producer (e.g.
Tirzah's recursive planner) cannot silently drift into a local dialect.

It is intentionally minimal and additive: it checks the *core* plan/step contract
(required fields, allowed constructs, allowed statuses), not the full prose grammar.
``CANONICAL_PLAN`` is the executable fixture — a known-conformant plan.
"""

from __future__ import annotations

from typing import Any

from cairn_core.metamodel import DEFAULT_METAMODEL, ValidationMetamodel

# The sets live on the versioned metamodel. These names are the default contract.
CONFORMANCE_VERSION = DEFAULT_METAMODEL.conformance_version
CORE_CONSTRUCTS = DEFAULT_METAMODEL.core_constructs
EXTENSION_CONSTRUCTS = DEFAULT_METAMODEL.extension_constructs
PLAN_CONSTRUCTS = DEFAULT_METAMODEL.plan_constructs
PLAN_STATUSES = DEFAULT_METAMODEL.plan_statuses
REVISION_DECISIONS = DEFAULT_METAMODEL.revision_decisions
STEP_STATUSES = DEFAULT_METAMODEL.step_statuses
ON_UNCERTAINTY_POLICIES = DEFAULT_METAMODEL.on_uncertainty
COGNITION_VALUES = DEFAULT_METAMODEL.cognition_values
COGNITION_MVP = frozenset({"observe", "infer", "evaluate", "decide"}) & COGNITION_VALUES
COGNITION_EXTENDED = COGNITION_VALUES - COGNITION_MVP
COGNITION_RESERVED = frozenset()
REQUIRED_PLAN_FIELDS = DEFAULT_METAMODEL.required_plan_fields
OPTIONAL_PLAN_FIELDS = DEFAULT_METAMODEL.optional_plan_fields
REQUIRED_STEP_FIELDS = DEFAULT_METAMODEL.required_step_fields
VALIDATE_PROFILES = DEFAULT_METAMODEL.validate_profiles
_STEP_NAME = DEFAULT_METAMODEL.step_token


def _validate_step(step: Any, index: int, model: ValidationMetamodel) -> list[str]:
    if not isinstance(step, dict):
        return [f"step[{index}] must be an object"]
    errors = [f"step[{index}] missing field: {f}" for f in model.required_step_fields if f not in step]
    construct = step.get("construct")
    if construct is not None and construct not in model.plan_constructs:
        errors.append(
            f"step[{index}] invalid construct: {construct!r} (allowed: {sorted(model.plan_constructs)})"
        )
    status = step.get("status")
    if status is not None and status not in model.step_statuses:
        errors.append(f"step[{index}] invalid status: {status!r} (allowed: {sorted(model.step_statuses)})")
    name = step.get("name")
    if name is not None:
        if not isinstance(name, str) or model.step_token.fullmatch(name) is None:
            errors.append(f"step[{index}] name must be a token such as receive-invoice")
        elif name.upper() in model.plan_constructs:
            errors.append(f"step[{index}] name {name!r} is a construct keyword")
    return errors


def _capability_stem(ref: str) -> str:
    """``milcah.critique@1`` → ``milcah.critique``."""
    return ref.strip().split("@", 1)[0].strip().lower()


def _tools_from_step(step: dict[str, Any]) -> list[str]:
    """Collect capability-like tool names from allowed_tools and CALL actions.

    Prefer ``allowed_tools`` when present so prose actions like
    ``Synthesise an answer…`` are not treated as tool names (review F5/M5).
    """
    tools: list[str] = []
    allowed = step.get("allowed_tools")
    if isinstance(allowed, list):
        tools.extend(str(t).strip() for t in allowed if str(t).strip())
        if tools:
            return tools
    action = str(step.get("action") or "")
    # "milcah.critique — …" or "Invoke milcah.critique" patterns after CALL construct
    if str(step.get("construct") or "").upper() == "CALL":
        # action may be "milcah.critique — Pressure-test…" or full phrase with tags
        head = action.split("[", 1)[0].strip()
        head = head.split("—", 1)[0].split("–", 1)[0].strip()
        parts = head.split()
        if parts:
            candidate = parts[0] if parts[0].lower() != "invoke" else (parts[1] if len(parts) > 1 else "")
            if candidate and ("." in candidate or candidate.replace("_", "").isalnum()):
                tools.append(candidate.rstrip("."))
    return tools


def validate_plan(
    plan: Any,
    *,
    profile: str = "full",
    model: ValidationMetamodel | None = None,
) -> list[str]:
    """Return a list of conformance errors for ``plan`` (empty list = conformant).

    Profiles (Phase B):

    - ``full`` — default structural contract (constructs, statuses, cognition MVP).
    - ``core`` — as full, plus reject **extension** constructs (core profile only).
    - ``strict`` — as full, plus COGNITION requires output/success_criteria;
      when ``assumes`` is set, CALL/allowed_tools should reference assumed stems.
    """
    model = model or DEFAULT_METAMODEL
    if profile not in model.validate_profiles:
        return [f"unknown validate profile {profile!r} (allowed: {sorted(model.validate_profiles)})"]

    if not isinstance(plan, dict):
        return ["plan must be an object"]

    errors = [f"missing plan field: {f}" for f in model.required_plan_fields if f not in plan]

    status = plan.get("status")
    if status is not None and status not in model.plan_statuses:
        errors.append(f"invalid plan status: {status!r} (allowed: {sorted(model.plan_statuses)})")

    decision = plan.get("revision_decision")
    if decision is not None and decision not in model.revision_decisions:
        errors.append(
            f"invalid revision_decision: {decision!r} (allowed: {sorted(model.revision_decisions)})"
        )

    policy = plan.get("on_uncertainty")
    if policy is not None and policy != "" and policy not in model.on_uncertainty:
        errors.append(
            f"invalid on_uncertainty: {policy!r} (allowed: {sorted(model.on_uncertainty)})"
        )

    assumes = plan.get("assumes")
    assume_stems: set[str] = set()
    if assumes is not None:
        if not isinstance(assumes, list):
            errors.append("assumes must be a list of capability refs (name or name@version)")
        else:
            for index, ref in enumerate(assumes):
                if not isinstance(ref, str) or not ref.strip():
                    errors.append(f"assumes[{index}] must be a non-empty string")
                else:
                    assume_stems.add(_capability_stem(ref))

    for list_field in ("outcomes", "stopping_conditions", "reevaluate_when"):
        value = plan.get(list_field)
        if value is not None and not isinstance(value, list):
            errors.append(f"{list_field} must be a list")

    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("plan must have at least one step")
    else:
        seen_names: set[str] = set()
        for index, step in enumerate(steps):
            errors.extend(_validate_step(step, index, model))
            if not isinstance(step, dict):
                continue
            name = step.get("name")
            if isinstance(name, str) and name in seen_names:
                errors.append(f"step[{index}] duplicate name {name!r}")
            if isinstance(name, str):
                seen_names.add(name)
            construct = step.get("construct")
            if profile == "core" and construct in model.extension_constructs:
                errors.append(
                    f"step[{index}] construct {construct!r} is not in the core profile "
                    f"(use full profile or a CORE construct)"
                )
            cognition = step.get("cognition")
            if cognition is not None and cognition != "":
                value = str(cognition).strip().lower()
                if value not in model.cognition_values:
                    errors.append(
                        f"step[{index}] unknown cognition {value!r} "
                        f"(allowed: {sorted(model.cognition_values)})"
                    )
                elif profile == "strict":
                    has_output = bool(step.get("success_criteria")) or bool(
                        str(step.get("output") or "").strip()
                    )
                    # Also accept OUTPUT folded into action prose is too weak; require criteria.
                    if not has_output:
                        errors.append(
                            f"step[{index}] strict: COGNITION {value!r} requires "
                            f"success_criteria or output"
                        )
                    # Human-owned decide should use DECISION (not bare STEP) —
                    # roadmap Part VI #3; GATED lives on DECISION.
                    if value == "decide" and str(construct or "").upper() != "DECISION":
                        errors.append(
                            f"step[{index}] strict: COGNITION decide should use "
                            f"construct DECISION (got {construct!r})"
                        )
            execution = step.get("execution")
            if execution is not None and execution != "":
                if str(execution).strip().lower() not in {"deterministic", "stochastic"}:
                    errors.append(
                        f"step[{index}] invalid execution {execution!r} "
                        f"(allowed: deterministic|stochastic)"
                    )

            if profile == "strict" and assume_stems and construct == "CALL":
                tools = _tools_from_step(step)
                if not tools:
                    errors.append(
                        f"step[{index}] strict: CALL step should name a capability "
                        f"in action or allowed_tools when assumes is set"
                    )
                else:
                    for tool in tools:
                        stem = _capability_stem(tool)
                        # Exact stem or namespace child of an assumed capability.
                        if stem not in assume_stems and not any(
                            stem == a or stem.startswith(a + ".")
                            for a in assume_stems
                        ):
                            errors.append(
                                f"step[{index}] strict: CALL tool {tool!r} not in "
                                f"assumes {sorted(assume_stems)}"
                            )

        # Graph integrity (review H4) — always, all profiles.
        errors.extend(_validate_step_graph(steps))

    # Scalar plan fields that must be well-typed.
    revision = plan.get("revision")
    if revision is not None and not isinstance(revision, int):
        errors.append(f"revision must be an int (got {type(revision).__name__})")
    max_steps = plan.get("max_steps")
    if max_steps is not None:
        try:
            if int(max_steps) < 0:
                errors.append("max_steps must be >= 0")
        except (TypeError, ValueError):
            errors.append(f"max_steps must be an int (got {max_steps!r})")

    return errors


def _validate_step_graph(steps: list[Any]) -> list[str]:
    """Id uniqueness, dangling/self depends_on, and cycles (review H4)."""
    errors: list[str] = []
    ids: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        sid = step.get("id")
        if sid is None or str(sid).strip() == "":
            errors.append(f"step[{index}] missing id")
            continue
        sid = str(sid)
        if sid in by_id:
            errors.append(f"duplicate step id {sid!r}")
        by_id[sid] = step
        ids.append(sid)

    # depends_on integrity
    for sid, step in by_id.items():
        deps = step.get("depends_on") or []
        if not isinstance(deps, list):
            errors.append(f"step {sid!r} depends_on must be a list")
            continue
        for dep in deps:
            dep_s = str(dep)
            if dep_s == sid:
                errors.append(f"step {sid!r} has a self-dependency")
            elif dep_s not in by_id:
                errors.append(f"step {sid!r} depends_on missing step {dep_s!r}")

    # Cycle detection (DFS)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {sid: WHITE for sid in by_id}
    cycle_nodes: list[str] = []

    def visit(u: str) -> bool:
        color[u] = GRAY
        deps = by_id[u].get("depends_on") or []
        if not isinstance(deps, list):
            deps = []
        for dep in deps:
            v = str(dep)
            if v not in by_id:
                continue
            if color[v] == GRAY:
                cycle_nodes.append(v)
                return True
            if color[v] == WHITE and visit(v):
                return True
        color[u] = BLACK
        return False

    for sid in by_id:
        if color[sid] == WHITE and visit(sid):
            errors.append(
                f"dependency cycle involving step {cycle_nodes[0]!r}"
                if cycle_nodes
                else "dependency cycle in plan steps"
            )
            break

    return errors


def is_core_construct(construct: str | None, model: ValidationMetamodel | None = None) -> bool:
    """True if ``construct`` is in the execution-normative core profile."""
    chosen = model or DEFAULT_METAMODEL
    return construct is not None and construct in chosen.core_constructs


def is_conformant(plan: Any) -> bool:
    return not validate_plan(plan)


# Executable fixture: a known-conformant minimal plan. Producers can diff against
# this and consumers can use it as a stable example in tests.
CANONICAL_PLAN: dict[str, Any] = {
    "plan_id": "plan_canonical_0001",
    "revision": 1,
    "parent_revision": None,
    "request": "Summarise the retrieved context and answer the question.",
    "intent": "Produce a grounded answer to the user's question.",
    "objective": "Produce a grounded answer to the user's question.",
    "status": "active",
    "steps": [
        {
            "id": "s1",
            "action": "Retrieve relevant context for the question.",
            "construct": "STEP",
            "status": "pending",
            "depends_on": [],
            "success_criteria": ["relevant chunks gathered"],
            "allowed_tools": ["retrieval"],
        },
        {
            "id": "s2",
            "action": "Synthesise an answer from the gathered context.",
            "construct": "CALL",
            "status": "pending",
            "depends_on": ["s1"],
            "success_criteria": ["answer cites gathered context"],
            "allowed_tools": ["answer_adapter"],
        },
    ],
    "stopping_conditions": ["answer produced", "no further context improves sufficiency"],
    "outcomes": ["answer produced", "no further context improves sufficiency"],
    "assumes": ["retrieval@1", "answer_adapter@1"],
    "on_uncertainty": "record",
    "reevaluate_when": [],
    "unresolved_questions": [],
    "revision_decision": "revise",
    "revision_reason": "",
}
