"""SPEC §12 well-formedness validation for parsed Cairn documents."""

from __future__ import annotations

import re

from cairn_core.metamodel import DEFAULT_METAMODEL, ValidationMetamodel
from cairn_core.ast import (
    Annotation,
    CairnDocument,
    ConstructLine,
    Plan,
    Process,
    Step,
)
from cairn_core.tags import has_llm_actor, modifier_keys, tag_dimensions

_STATE_REF = re.compile(r"^(\w+)")
_CALL_TARGET = re.compile(r"(?:^|[\s→])CALL\s+(\w+)\b")
_LOOP_CONSTRUCTS = frozenset({"ITERATE", "RECURSE", "QUEUE"})
_BOUND_CONSTRUCTS = frozenset({"ITERATE", "RECURSE"})
_BOUND_KEYS = frozenset({"MAX", "MAX_DEPTH", "UNTIL", "OVER"})

# Domain-specific constructs from proposals (for validation and awareness)
_PSYCH_CONSTRUCTS = frozenset(
    {
        "REGULATION",
        "APPRAISAL",
        "DUAL_PROCESS",
        "METACOGNITION",
        "FEEDBACK",
        "AVOIDANCE",
        "HABIT",
        "ATTENTION",
        "INTERPERSONAL",
    }
)
_ORG_CONSTRUCTS = frozenset({"ALIGN", "COALITION", "RESISTANCE", "REINFORCEMENT", "CASCADE", "VISION"})
_SOCIO_CONSTRUCTS = frozenset({"SOCIALIZE", "INSTITUTIONALIZE", "SYMBOLIC_INTERACTION", "CONFLICT", "ACCOMMODATE", "ASSIMILATE", "ROLE"})
_BE_CONSTRUCTS = frozenset({"FRAME", "NUDGE", "ACCOUNT", "DISCOUNT"})
_GT_CONSTRUCTS = frozenset({"GAME", "PLAY", "EQUILIBRIUM", "SIGNAL"})
_HCI_CONSTRUCTS = frozenset({"CHOICE", "GULF", "AFFORDANCE", "FORAGE"})
_ALL_DOMAIN_CONSTRUCTS = (
    _PSYCH_CONSTRUCTS
    | _ORG_CONSTRUCTS
    | _SOCIO_CONSTRUCTS
    | _BE_CONSTRUCTS
    | _GT_CONSTRUCTS
    | _HCI_CONSTRUCTS
    | {"MACRO"}
)
_SHOULD_ANY = {
    "AVOIDANCE": ("MODE",),
    "HABIT": ("PHASE",),
    "ATTENTION": ("MODE",),
    "INTERPERSONAL": ("PATTERN",),
    "FRAME": ("VALENCE",),
    "NUDGE": ("TOOL",),
    "ACCOUNT": ("KIND",),
    "DISCOUNT": ("SHAPE",),
    "PLAY": ("MOVE",),
    "EQUILIBRIUM": ("CONCEPT",),
    "SIGNAL": ("COST",),
    "GULF": ("KIND",),
    "AFFORDANCE": ("MAP",),
    "FORAGE": ("SCENT",),
}
_SHOULD_OR = {
    "GAME": ("STRUCTURE", "KIND"),
    "CHOICE": ("SET", "ARCHITECTURE"),
}
_SAMPLE_BOUND_KEYS = frozenset({"N", "MAX"})
_MERGE_RULES = frozenset({"winner", "vote", "synthesis", "admissibility", "none"})
_STEP_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
_BIND_TOKEN = _STEP_NAME


def validate_document(
    doc: CairnDocument,
    *,
    require_step_names: bool = False,
    model: ValidationMetamodel | None = None,
) -> list[str]:
    """Return well-formedness errors (empty list = well-formed per SPEC §12)."""
    model = model or DEFAULT_METAMODEL
    require_step_names = require_step_names or model.require_step_names
    errors: list[str] = list(doc.parse_errors)

    if not (
        doc.context_blocks
        or doc.requirements_blocks
        or doc.outcomes_blocks
        or doc.processes
        or doc.plans
    ):
        errors.append("document must contain at least one CONTEXT, REQUIREMENTS/OUTCOMES, or PROCESS block")

    all_states = _collect_state_names(doc)
    context_keys = _collect_context_keys(doc)
    loop_call_targets = _collect_loop_call_targets(doc)

    for proc in doc.processes:
        in_loop = proc.name in loop_call_targets
        errors.extend(
            _validate_process(
                proc,
                declared_states=all_states | context_keys,
                loop_call_target=in_loop,
                require_step_names=require_step_names,
                model=model,
            )
        )

    for plan in doc.plans:
        errors.extend(
            _validate_plan(
                plan,
                declared_states=all_states | context_keys,
                loop_call_targets=loop_call_targets,
                require_step_names=require_step_names,
                model=model,
            )
        )

    return errors


def _collect_state_names(doc: CairnDocument) -> set[str]:
    names: set[str] = set()
    for proc in doc.processes:
        if proc.state:
            names.update(d.name for d in proc.state.declarations)
    for plan in doc.plans:
        if plan.process and plan.process.state:
            names.update(d.name for d in plan.process.state.declarations)
    return names


def _collect_context_keys(doc: CairnDocument) -> set[str]:
    keys: set[str] = set()
    for block in doc.context_blocks:
        for line in block.lines:
            if " — " in line:
                keys.add(line.split(" — ", 1)[0].strip())
            elif " - " in line:
                keys.add(line.split(" - ", 1)[0].strip())
    for proc in doc.processes:
        if proc.context:
            for line in proc.context.lines:
                if " — " in line:
                    keys.add(line.split(" — ", 1)[0].strip())
    return keys


def _collect_loop_call_targets(doc: CairnDocument) -> set[str]:
    targets: set[str] = set()
    for proc in doc.processes:
        _walk_loop_calls(proc, targets)
    for plan in doc.plans:
        if plan.process:
            _walk_loop_calls(plan.process, targets)
    return targets


def _walk_loop_calls(proc: Process, targets: set[str], *, loop_depth: int = 0) -> None:
    proc_loop = loop_depth
    for element in proc.elements:
        if not isinstance(element, ConstructLine):
            continue
        blob = f"{element.text} {element.arrow_target or ''}"
        if element.construct in _LOOP_CONSTRUCTS or re.search(r"\bITERATE\b", blob):
            proc_loop = max(proc_loop, loop_depth + 1)
        if proc_loop > 0:
            for name in _calls_from_construct_line(element):
                targets.add(name)

    for step in proc.steps:
        _walk_step_loop_calls(step, targets, loop_depth=proc_loop)


def _walk_step_loop_calls(step: Step, targets: set[str], *, loop_depth: int) -> None:
    active_loop = loop_depth

    if step.construct in _LOOP_CONSTRUCTS:
        active_loop = max(active_loop, loop_depth + 1)

    if active_loop > 0:
        for name in _calls_from_text(step.text):
            targets.add(name)

    for cline in step.construct_lines:
        blob = f"{cline.text} {cline.arrow_target or ''}"
        if cline.construct in _LOOP_CONSTRUCTS or re.search(r"\bITERATE\b", blob):
            active_loop = max(active_loop, loop_depth + 1)
        if active_loop > 0:
            for name in _calls_from_construct_line(cline):
                targets.add(name)

    child_loop = active_loop if step.construct in _LOOP_CONSTRUCTS else loop_depth
    if step.construct in _LOOP_CONSTRUCTS:
        child_loop = loop_depth + 1

    for child in step.children:
        _walk_step_loop_calls(child, targets, loop_depth=child_loop)


def _calls_from_construct_line(cline: ConstructLine) -> list[str]:
    names: list[str] = []
    for blob in (cline.text, cline.arrow_target or ""):
        names.extend(_calls_from_text(blob))
    if cline.construct == "CALL":
        match = re.match(r"^(\w+)", cline.text.strip())
        if match:
            names.append(match.group(1))
    return names


def _calls_from_text(text: str) -> list[str]:
    names = [m.group(1) for m in _CALL_TARGET.finditer(text)]
    for segment in text.split("→"):
        names.extend(m.group(1) for m in _CALL_TARGET.finditer(segment))
    return names


_ON_UNCERTAINTY = frozenset({"record", "escalate", "abort"})
_PLAN_STATUSES = frozenset(
    {"draft", "active", "stable", "complete", "blocked", "open", "refused"}
)
# capability name, optional @version (e.g. milcah.critique@1, tirzah.retrieve)
_CAPABILITY_REF = re.compile(r"^[A-Za-z_][\w.-]*(?:@[\w.-]+)?$")


def _validate_plan(
    plan: Plan,
    *,
    declared_states: set[str],
    loop_call_targets: set[str],
    require_step_names: bool = False,
    model: ValidationMetamodel,
) -> list[str]:
    errors: list[str] = []
    if not plan.request.strip():
        errors.append(f"PLAN {plan.plan_id!r} at line {plan.lineno}: REQUEST is required")
    if not plan.trigger.strip():
        errors.append(f"PLAN {plan.plan_id!r} at line {plan.lineno}: TRIGGER is required")
    if plan.status and plan.status not in model.plan_statuses:
        errors.append(
            f"PLAN {plan.plan_id!r} at line {plan.lineno}: invalid STATUS {plan.status!r} "
            f"(allowed: {sorted(model.plan_statuses)})"
        )
    if plan.on_uncertainty and plan.on_uncertainty not in model.on_uncertainty:
        errors.append(
            f"PLAN {plan.plan_id!r} at line {plan.lineno}: ON_UNCERTAINTY must be "
            f"{'|'.join(sorted(model.on_uncertainty))}, got {plan.on_uncertainty!r}"
        )
    for ref in plan.assumes:
        if not _CAPABILITY_REF.match(ref):
            errors.append(
                f"PLAN {plan.plan_id!r} at line {plan.lineno}: "
                f"invalid ASSUMES capability ref {ref!r} (want name or name@version)"
            )
    if plan.process:
        errors.extend(
            _validate_process(
                plan.process,
                declared_states=declared_states,
                loop_call_target=plan.process.name in loop_call_targets,
                require_step_names=require_step_names,
                model=model,
            )
        )
    else:
        errors.append(f"PLAN {plan.plan_id!r} at line {plan.lineno}: must contain a PROCESS backbone")
    return errors


def _validate_process(
    proc: Process,
    *,
    declared_states: set[str],
    loop_call_target: bool = False,
    require_step_names: bool = False,
    model: ValidationMetamodel,
) -> list[str]:
    errors: list[str] = []
    if not proc.name or proc.name == "unnamed":
        errors.append(f"PROCESS at line {proc.lineno} must have a name")
    proc_states = set(declared_states)
    if proc.signature:
        for blob in (proc.signature.inputs, proc.signature.outputs):
            for token in re.split(r"[,;]\s*", blob):
                token = token.strip()
                if token and token != "—":
                    proc_states.add(token)
        if proc.signature.outputs.strip() not in ("", "—"):
            proc_states.add("result")
    proc_states |= _ephemeral_state_names(proc)
    declared_states = proc_states

    loop_depth = 1 if loop_call_target else 0
    for element in proc.elements:
        if isinstance(element, ConstructLine) and element.construct in _LOOP_CONSTRUCTS:
            loop_depth = max(loop_depth, 1)
            errors.extend(_validate_construct_line(element, loop_depth=loop_depth, require_llm_bound=False))

    seen_names: set[str] = set()
    for step in proc.steps:
        errors.extend(
            _validate_step_tree(
                step,
                declared_states,
                loop_depth=loop_depth,
                seen_names=seen_names,
                require_step_names=require_step_names,
                model=model,
            )
        )

    # Domain tag/construct consistency (core improvement for human systems)
    all_step_tags = []
    for step in proc.steps:
        all_step_tags.extend(step.tags)
    for element in proc.elements:
        if isinstance(element, ConstructLine):
            all_step_tags.extend(element.modifiers)  # rough
    tag_set = set(t.upper() for t in all_step_tags)
    used_constructs = set()
    for step in proc.steps:
        if step.construct:
            used_constructs.add(step.construct)
        for cline in step.construct_lines:
            used_constructs.add(cline.construct)
    for el in proc.elements:
        if isinstance(el, ConstructLine):
            used_constructs.add(el.construct)

    psych_tag_set = {
        "EMOTIONAL",
        "COGNITIVE",
        "APPRAISAL",
        "REGULATION",
        "MOTIVATIONAL",
        "METACOGNITIVE",
        "BEHAVIORAL",
        "TRANSDIAGNOSTIC",
        "INTERPERSONAL",
        "AVOIDANT",
    }
    org_tag_set = {"LEADERSHIP", "STRATEGIC", "CULTURAL", "POWER", "STAKEHOLDER", "STRUCTURAL", "ALIGNMENT", "RESISTANCE"}
    socio_tag_set = {"SOCIAL", "GROUP", "NORM", "ROLE", "SYMBOLIC"}
    be_tag_set = {"HEURISTIC", "FRAMED", "NUDGED"}
    gt_tag_set = {"INCENTIVE", "COMMON_KNOWLEDGE", "RECIPROCAL"}
    hci_tag_set = {"INTERACTIVE", "OVERLOAD", "DISCOVERABLE"}
    used_upper = {c.upper() for c in used_constructs}

    if psych_tag_set & tag_set and not _PSYCH_CONSTRUCTS & used_upper:
        errors.append(f"PROCESS {proc.name}: has psychological tags but no corresponding constructs (REGULATION, APPRAISAL, etc.) — use them for clarity in human systems")
    if org_tag_set & tag_set and not _ORG_CONSTRUCTS & used_upper:
        errors.append(f"PROCESS {proc.name}: has organisational tags but no corresponding constructs (COALITION, ALIGN, etc.)")
    if socio_tag_set & tag_set and not _SOCIO_CONSTRUCTS & used_upper:
        errors.append(f"PROCESS {proc.name}: has sociological tags but no corresponding constructs (SOCIALIZE, SYMBOLIC_INTERACTION, etc.)")
    if be_tag_set & tag_set and not _BE_CONSTRUCTS & used_upper:
        errors.append(
            f"PROCESS {proc.name}: behavioural-economic tags require a FRAME, NUDGE, ACCOUNT, or DISCOUNT construct"
        )
    if gt_tag_set & tag_set and not _GT_CONSTRUCTS & used_upper:
        errors.append(
            f"PROCESS {proc.name}: game-theoretic tags require a GAME, PLAY, EQUILIBRIUM, or SIGNAL construct"
        )
    if hci_tag_set & tag_set and not _HCI_CONSTRUCTS & used_upper:
        errors.append(
            f"PROCESS {proc.name}: hci tags require a CHOICE, GULF, AFFORDANCE, or FORAGE construct"
        )

    return errors


def _validate_step_name(
    step: Step,
    seen: set[str],
    *,
    require_step_names: bool,
    model: ValidationMetamodel,
) -> list[str]:
    """A name is optional unless the caller asked for one. It is unique in the process."""
    if not step.name:
        if require_step_names:
            return [f"line {step.lineno}: step {step.step_id} is missing a name"]
        return []
    if model.step_token.fullmatch(step.name) is None:
        return [f"line {step.lineno}: step name {step.name!r} must be a single token"]
    if step.name.upper() in model.reserved_step_names:
        return [f"line {step.lineno}: step name {step.name!r} is a construct keyword"]
    if step.name in seen:
        return [f"line {step.lineno}: duplicate step name {step.name!r}"]
    seen.add(step.name)
    return []


def _validate_step_tree(
    step: Step,
    declared_states: set[str],
    *,
    loop_depth: int,
    parent_number: str | None = None,
    seen_names: set[str] | None = None,
    require_step_names: bool = False,
    model: ValidationMetamodel,
) -> list[str]:
    errors: list[str] = []
    names = seen_names if seen_names is not None else set()

    if parent_number is not None:
        errors.extend(_check_nesting(parent_number, step.step_id, step.lineno))

    errors.extend(
        _validate_step_name(step, names, require_step_names=require_step_names, model=model)
    )

    errors.extend(_validate_tags(step.tags, step.lineno))
    errors.extend(_validate_annotations(step.annotations, declared_states, step.lineno, model))

    construct = step.construct
    if construct in {"BREAK", "CONTINUE"} and loop_depth == 0:
        errors.append(
            f"line {step.lineno}: {construct} must appear inside ITERATE, RECURSE, or QUEUE"
        )
    if construct == "AWAIT":
        errors.extend(_check_await_timeout(step, step.lineno))

    # Domain checks also for steps that are constructs
    if construct in _ALL_DOMAIN_CONSTRUCTS:
        parsed = getattr(step, "parsed_modifiers", {}) or {}
        keys = set(getattr(step, "modifiers", [])) | set(parsed.keys()) | set(_bound_keys_from([], step.text, step.tags))
        if construct == "REGULATION":
            if "STRATEGY" not in keys and "TARGET" not in keys:
                errors.append(f"line {step.lineno}: REGULATION should declare STRATEGY or TARGET (per psychological process model)")
        if construct == "APPRAISAL":
            if "TYPE" not in keys:
                errors.append(f"line {step.lineno}: APPRAISAL should declare TYPE (primary|secondary)")
        if construct == "FEEDBACK":
            if not keys and not step.text:
                errors.append(f"line {step.lineno}: FEEDBACK should specify what is fed back (e.g. [FROM: emotion] or text)")
        errors.extend(_check_should_modifiers(construct, keys, step.lineno))

    if construct == "SAMPLE":
        parsed = getattr(step, "parsed_modifiers", {}) or {}
        keys = _bound_keys_from(
            list(getattr(step, "modifiers", None) or []),
            step.text,
            list(getattr(step, "tags", None) or []),
            parsed,
        )
        if not (keys & _SAMPLE_BOUND_KEYS):
            errors.append(f"line {step.lineno}: SAMPLE must declare N or MAX")
    if construct == "VIEW":
        parsed = getattr(step, "parsed_modifiers", {}) or {}
        keys = _bound_keys_from(
            list(getattr(step, "modifiers", None) or []),
            step.text,
            list(getattr(step, "tags", None) or []),
            parsed,
        )
        if not keys & {"ROLE", "EXPOSE", "WITHHOLD"}:
            errors.append(f"line {step.lineno}: VIEW must declare ROLE, EXPOSE, or WITHHOLD")
    if construct == "MERGE":
        parsed = getattr(step, "parsed_modifiers", {}) or {}
        rule = str(parsed.get("RULE") or parsed.get("rule") or "").strip().lower()
        if rule and rule not in _MERGE_RULES:
            errors.append(
                f"line {step.lineno}: MERGE RULE {rule!r} is unknown; "
                f"use one of {sorted(_MERGE_RULES)} or omit RULE"
            )

    new_loop_depth = loop_depth
    if construct in _LOOP_CONSTRUCTS:
        new_loop_depth = loop_depth + 1
        if has_llm_actor(step.tags) or _step_has_llm_descendant(step):
            errors.extend(_check_iteration_bound(step, step.lineno))

    for cline in step.construct_lines:
        cline_loop = new_loop_depth
        if cline.construct in _LOOP_CONSTRUCTS:
            cline_loop = loop_depth + 1
        errors.extend(
            _validate_construct_line(
                cline,
                loop_depth=cline_loop,
                require_llm_bound=has_llm_actor(step.tags),
            )
        )

    for child in step.children:
        errors.extend(
            _validate_step_tree(
                child,
                declared_states,
                loop_depth=new_loop_depth,
                parent_number=step.step_id if step.step_id != "0" else parent_number,
                seen_names=names,
                require_step_names=require_step_names,
                model=model,
            )
        )

    for check in model.extra_step_checks:
        errors.extend(check(step, model))

    return errors


def _check_should_modifiers(construct: str | None, modifiers: set[str], lineno: int) -> list[str]:
    """Key-presence 'should' checks for four-area EXTENSION constructs.

    Values are not closed-enum: mapping docs name the inventory.
    DECISION RULE is optional and is not checked here.
    """
    if not construct:
        return []
    errors: list[str] = []
    keys = {k.upper() for k in modifiers}
    if construct in _SHOULD_ANY:
        need = _SHOULD_ANY[construct]
        if not any(n in keys for n in need):
            errors.append(f"line {lineno}: {construct} should declare {need[0]}")
    if construct in _SHOULD_OR:
        a, b = _SHOULD_OR[construct]
        if a not in keys and b not in keys:
            errors.append(f"line {lineno}: {construct} should declare {a} or {b}")
    return errors


def _step_has_llm_descendant(step: Step) -> bool:
    if has_llm_actor(step.tags):
        return True
    for child in step.children:
        if _step_has_llm_descendant(child):
            return True
    return False


def _validate_construct_line(
    cline: ConstructLine,
    *,
    loop_depth: int,
    require_llm_bound: bool,
) -> list[str]:
    errors: list[str] = []
    if cline.construct in {"BREAK", "CONTINUE"} and loop_depth == 0:
        errors.append(
            f"line {cline.lineno}: {cline.construct} must appear inside ITERATE, RECURSE, or QUEUE"
        )
    if cline.construct == "AWAIT":
        parsed = getattr(cline, "parsed_modifiers", {}) or {}
        keys = _bound_keys_from(cline.modifiers, cline.text, [], parsed)
        if "TIMEOUT" not in keys and not re.search(r"\bTIMEOUT\s*:", cline.text, re.I):
            errors.append(f"line {cline.lineno}: AWAIT must declare TIMEOUT")
    if cline.construct in _BOUND_CONSTRUCTS and require_llm_bound:
        parsed = getattr(cline, "parsed_modifiers", {}) or {}
        if not _has_iteration_bound(cline.modifiers, cline.text, [], parsed):
            key_name = "MAX_DEPTH" if cline.construct == "RECURSE" else "MAX"
            errors.append(f"line {cline.lineno}: {cline.construct} should declare {key_name} or UNTIL")
    # Domain construct awareness (non-blocking guidance for now, to stay human-first)
    if cline.construct in _ALL_DOMAIN_CONSTRUCTS:
        # Future: could add stricter rules per domain
        pass
    if cline.construct == "FEEDBACK":
        parsed = getattr(cline, "parsed_modifiers", {}) or {}
        keys = _bound_keys_from(cline.modifiers, cline.text, [], parsed)
        if not keys and not parsed and not cline.text:
            errors.append(f"line {cline.lineno}: FEEDBACK should specify what is fed back (e.g. [FROM: emotion] or text)")
    if cline.construct == "SAMPLE":
        parsed = getattr(cline, "parsed_modifiers", {}) or {}
        keys = _bound_keys_from(cline.modifiers, cline.text, [], parsed)
        if not (keys & _SAMPLE_BOUND_KEYS) and "N" not in parsed:
            errors.append(f"line {cline.lineno}: SAMPLE must declare N or MAX")
    if cline.construct == "VIEW":
        parsed = getattr(cline, "parsed_modifiers", {}) or {}
        keys = {k.upper() for k in parsed} | _bound_keys_from(cline.modifiers, cline.text, [], parsed)
        if not keys & {"ROLE", "EXPOSE", "WITHHOLD"} and "ROLE" not in parsed:
            errors.append(
                f"line {cline.lineno}: VIEW must declare ROLE, EXPOSE, or WITHHOLD"
            )
    if cline.construct == "MERGE":
        parsed = getattr(cline, "parsed_modifiers", {}) or {}
        rule = str(parsed.get("RULE") or parsed.get("rule") or "").strip().lower()
        if rule and rule not in _MERGE_RULES:
            errors.append(
                f"line {cline.lineno}: MERGE RULE {rule!r} is unknown; "
                f"use one of {sorted(_MERGE_RULES)} or omit RULE"
            )

    # Domain-specific modifier validation for new constructs (core grammar improvement)
    parsed = getattr(cline, "parsed_modifiers", {}) or {}
    keys = _bound_keys_from(cline.modifiers, cline.text, [], parsed) | set(parsed.keys())
    if cline.construct == "REGULATION":
        if "STRATEGY" not in keys and "TARGET" not in keys:
            errors.append(f"line {cline.lineno}: REGULATION should declare STRATEGY or TARGET (per psychological process model)")
    if cline.construct == "APPRAISAL":
        if "TYPE" not in keys:
            errors.append(f"line {cline.lineno}: APPRAISAL should declare TYPE (primary|secondary)")
    if cline.construct == "ALIGN":
        if "ELEMENTS" not in keys:
            errors.append(f"line {cline.lineno}: ALIGN should declare ELEMENTS (e.g. strategy|culture)")
    if cline.construct == "COALITION":
        if not keys and not cline.text:
            errors.append(f"line {cline.lineno}: COALITION should specify BUILD or SUSTAIN or participants")
    if cline.construct == "VISION":
        if not keys and not cline.text:
            errors.append(f"line {cline.lineno}: VISION should specify FORM|COMMUNICATE|ANCHOR or details")
    if cline.construct == "SOCIALIZE":
        if "TYPE" not in keys:
            errors.append(f"line {cline.lineno}: SOCIALIZE should declare TYPE (primary|secondary)")
    if cline.construct == "SYMBOLIC_INTERACTION":
        if "MEANING" not in keys and not cline.text:
            errors.append(f"line {cline.lineno}: SYMBOLIC_INTERACTION should declare MEANING or describe the interaction")
    if cline.construct == "MACRO":
        if not keys and not cline.text:
            errors.append(f"line {cline.lineno}: MACRO should name a higher-level pattern or sub-process")
    errors.extend(_check_should_modifiers(cline.construct, keys, cline.lineno))
    return errors


# Cognitive product contracts (SPEC process-semantic axes). Progressive.
# Core MVP + Phase F extended (negotiate|learn|optimize).
_COGNITION_VALUES = frozenset(
    {"observe", "infer", "evaluate", "decide", "negotiate", "learn", "optimize"}
)


def _validate_annotations(
    annotations: list[Annotation],
    declared_states: set[str],
    lineno: int,
    model: ValidationMetamodel,
) -> list[str]:
    errors: list[str] = []
    cognition_seen = 0
    rules = model.rules_by_keyword()
    for ann in annotations:
        if ann.keyword == "STATE_UPDATE":
            ref = _STATE_REF.match(ann.text.strip())
            if ref and ref.group(1) not in declared_states:
                errors.append(
                    f"line {ann.lineno}: STATE UPDATE references undeclared state {ref.group(1)!r}"
                )
        elif ann.keyword == "COGNITION":
            cognition_seen += 1
        rule = rules.get(ann.keyword)
        if rule is not None:
            errors.extend(rule.check(ann.text, ann.lineno, model))
    if cognition_seen > 1:
        errors.append(f"line {lineno}: at most one COGNITION annotation per step")
    return errors


def _validate_tags(tags: list[str], lineno: int) -> list[str]:
    errors: list[str] = []
    dims = tag_dimensions(tags)
    flat = " ".join(tags).upper()

    effects = dims.get("effect", [])
    if len(effects) > 1:
        normalized = {e.split("[", 1)[0].strip().upper() for e in effects}
        if not (normalized <= {"SIDE-EFFECT", "IDEMPOTENT"}):
            errors.append(f"line {lineno}: multiple effect tags: {effects!r}")

    actors = dims.get("actor", [])
    if len(actors) > 1:
        actor_roots = {a.split(":", 1)[0].strip().upper() for a in actors}
        if not ("GATED" in flat and actor_roots <= {"CODE", "HUMAN"}):
            errors.append(f"line {lineno}: multiple actor tags: {actors!r}")

    for dim in ("determinism", "timing", "control"):
        values = dims.get(dim, [])
        if len(values) > 1:
            errors.append(f"line {lineno}: multiple {dim} tags: {values!r}")

    # domain tags (new for psych/org/socio) can be multiple by design
    domain_values = dims.get("domain", [])
    if len(domain_values) > 4:  # arbitrary reasonable limit
        errors.append(f"line {lineno}: too many domain tags: {domain_values!r}")

    for custom in dims.get("custom", []):
        if not re.match(r"^[a-z][\w-]*:\S+", custom):
            errors.append(f"line {lineno}: custom tag must be namespaced (ns:word): {custom!r}")
    return errors


def _check_nesting(parent: str, child: str, lineno: int) -> list[str]:
    if child == "0":
        return []
    parent_parts = parent.split(".")
    child_parts = child.rstrip("abcdefghijklmnopqrstuvwxyz").split(".")
    if child and child[-1].isalpha():
        child_parts = child[:-1].split(".")

    if len(child_parts) == len(parent_parts):
        if child_parts[:-1] != parent_parts[:-1]:
            return [f"line {lineno}: step {child} is not nested under {parent}"]
        try:
            if int(child_parts[-1]) != int(parent_parts[-1]):
                return [f"line {lineno}: step {child} sibling index mismatch under {parent}"]
        except ValueError:
            pass
    elif len(child_parts) == len(parent_parts) + 1:
        if child_parts[:-1] != parent_parts:
            return [f"line {lineno}: step {child} is not a child of {parent}"]
    elif len(child_parts) < len(parent_parts):
        return []
    return []


def _bound_keys_from(modifiers: list[str], text: str, tags: list[str], parsed_modifiers: dict = None) -> set[str]:
    keys = set(modifier_keys(modifiers))
    if parsed_modifiers:
        keys.update(k.upper() for k in parsed_modifiers.keys())
    for bracket in tags:
        for part in re.split(r"[;|]", bracket):
            part = part.strip()
            if ":" in part:
                keys.add(part.split(":", 1)[0].strip().upper())
    for token in re.findall(r"\b(MAX|MAX_DEPTH|UNTIL|OVER|TIMEOUT|N|ROLE|EXPOSE|WITHHOLD|RULE)\s*:", text, re.I):
        keys.add(token.upper())
    return keys


def _has_iteration_bound(modifiers: list[str], text: str, tags: list[str], parsed_modifiers: dict = None) -> bool:
    keys = _bound_keys_from(modifiers, text, tags, parsed_modifiers)
    return bool(keys & _BOUND_KEYS)


def _check_iteration_bound(step: Step, lineno: int) -> list[str]:
    for cline in step.construct_lines:
        parsed = getattr(cline, "parsed_modifiers", {}) or {}
        if _has_iteration_bound(cline.modifiers, cline.text, [], parsed):
            return []
    # Thread the step's own modifiers (SPEC: ITERATE [UNTIL: …; MAX: …] → …)
    # — previously discarded, causing false positives on documented form (H3/F2).
    parsed_step = getattr(step, "parsed_modifiers", {}) or {}
    if _has_iteration_bound(
        list(getattr(step, "modifiers", None) or []),
        step.text,
        list(getattr(step, "tags", None) or []),
        parsed_step,
    ):
        return []
    need = "MAX_DEPTH" if step.construct == "RECURSE" else "MAX"
    return [f"line {lineno}: {step.construct} with LLM involvement must declare {need} or UNTIL"]


def _check_await_timeout(step: Step, lineno: int) -> list[str]:
    # Check for TIMEOUT in annotations or construct lines for AWAIT
    has_timeout = False
    if "TIMEOUT" in step.annotations:
        has_timeout = True
    parsed_step = getattr(step, "parsed_modifiers", {}) or {}
    if "TIMEOUT" in getattr(step, "modifiers", []) or "TIMEOUT" in parsed_step:
        has_timeout = True
    for cline in step.construct_lines:
        parsed = getattr(cline, "parsed_modifiers", {}) or {}
        if "TIMEOUT" in cline.modifiers or "TIMEOUT" in str(cline.text).upper() or "TIMEOUT" in parsed:
            has_timeout = True
    if not has_timeout and "TIMEOUT" not in str(step.text).upper():
        # Allow "never" or context-dependent as in examples
        text = str(step.text).lower() + " " + str(step.annotations)
        if "never" not in text and "context" not in text and "variable" not in text:
            return [f"line {lineno}: AWAIT must declare TIMEOUT or use 'never'/'context-dependent'"]
    return []


def _ephemeral_state_names(proc: Process) -> set[str]:
    names: set[str] = set()

    def walk(step: Step) -> None:
        for blob in (step.text,):
            for match in re.finditer(r"\(([^)]*)\)", blob):
                for arg in match.group(1).split(","):
                    token = arg.strip().split("=")[0].strip()
                    if token.isidentifier():
                        names.add(token)
        for cline in step.construct_lines:
            for blob in (cline.text, cline.arrow_target or ""):
                for match in re.finditer(r"\(([^)]*)\)", blob):
                    for arg in match.group(1).split(","):
                        token = arg.strip().split("=")[0].strip()
                        if token.isidentifier():
                            names.add(token)
        for child in step.children:
            walk(child)

    for step in proc.steps:
        walk(step)
    return names
