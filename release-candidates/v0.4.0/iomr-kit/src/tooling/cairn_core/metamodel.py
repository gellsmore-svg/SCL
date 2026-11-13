"""Overridable validation metamodel for the Cairn process description.

The default model is the SPEC v0.15 / conformance 1.7 contract. A consumer
builds another model with ``extend`` (add) or ``override`` (replace) and passes
it to ``parse_document``, ``validate_document``, and ``validate_plan``. This
module does not import the Deborah package.
"""

from __future__ import annotations

import functools
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

CORE_VERSION = "1.0.0"
SPEC_VERSION = "0.15"
CONFORMANCE_VERSION = "1.7"

STEP_TOKEN_PATTERN = r"[A-Za-z][A-Za-z0-9_-]*"

Check = Callable[[str, int, "ValidationMetamodel"], list[str]]
StepCheck = Callable[[Any, "ValidationMetamodel"], list[str]]

CORE_CONSTRUCTS: frozenset[str] = frozenset(
    {
        "STEP",
        "CALL",
        "ITERATE",
        "DECISION",
        "RECURSE",
        "QUEUE",
        "PARALLEL",
        "MERGE",
        "SERVICE",
        "RETRY",
        "AWAIT",
        "BREAK",
        "CONTINUE",
        "MILESTONE",
        "ERROR",
    }
)

EXTENSION_CONSTRUCTS: frozenset[str] = frozenset(
    {
        "REGULATION",
        "APPRAISAL",
        "DUAL_PROCESS",
        "METACOGNITION",
        "ALIGN",
        "COALITION",
        "RESISTANCE",
        "REINFORCEMENT",
        "CASCADE",
        "VISION",
        "SOCIALIZE",
        "INSTITUTIONALIZE",
        "SYMBOLIC_INTERACTION",
        "CONFLICT",
        "ACCOMMODATE",
        "ASSIMILATE",
        "ROLE",
        "FEEDBACK",
        "MACRO",
        "SAMPLE",
        "VIEW",
        "AVOIDANCE",
        "HABIT",
        "ATTENTION",
        "INTERPERSONAL",
        "FRAME",
        "NUDGE",
        "ACCOUNT",
        "DISCOUNT",
        "GAME",
        "PLAY",
        "EQUILIBRIUM",
        "SIGNAL",
        "CHOICE",
        "GULF",
        "AFFORDANCE",
        "FORAGE",
    }
)

# These parse as construct lines. They are not step-body constructs.
LINE_ONLY_CONSTRUCTS: frozenset[str] = frozenset({"ATOMIC", "CONCURRENT"})
# A numbered step whose first word is one of these stays prose.
STEP_EXCLUDED: frozenset[str] = frozenset({"BREAK", "CONTINUE"})

ANNOTATION_SURFACES: tuple[str, ...] = (
    "STATE UPDATE",
    "OUTPUT",
    "RISKS",
    "PURPOSE",
    "COGNITION",
    "CONSTRAINTS",
    "BOUNDARIES",
    "CONTEXT",
    "HUMAN_DEMAND",
    "HUMAN SIMULATION",
    "HUMAN_SIMULATION",
    "HUMAN_LOAD",
    "HUMAN_FACTORS",
    "HUMAN_RISK",
    "TRUST",
    "SUPPORT",
    "FAILURE_MODE",
    "SIMULATION_FINDINGS",
    "IMPROVEMENT",
    "CHANGE_IMPACT",
    "CONDITION_MAP",
    "BIAS",
    "PAYOFF",
    "INFORMATION",
    "CHOICE_COMPLEXITY",
    "HCI_TOUCHPOINT",
    "BINDS",
)

ALIASES: tuple[tuple[str, str], ...] = (("DECIDE", "DECISION"), ("CONCURRENT", "PARALLEL"))

PLAN_STATUSES: frozenset[str] = frozenset(
    {"draft", "active", "stable", "complete", "blocked", "open", "refused"}
)
REVISION_DECISIONS: frozenset[str] = frozenset(
    {"revise", "stable", "complete", "blocked", "open", "refused"}
)
STEP_STATUSES: frozenset[str] = frozenset({"pending", "active", "completed", "blocked", "skipped"})
ON_UNCERTAINTY_POLICIES: frozenset[str] = frozenset({"record", "escalate", "abort"})
COGNITION_MVP: frozenset[str] = frozenset({"observe", "infer", "evaluate", "decide"})
COGNITION_EXTENDED: frozenset[str] = frozenset({"negotiate", "learn", "optimize"})
COGNITION_VALUES: frozenset[str] = COGNITION_MVP | COGNITION_EXTENDED
VALIDATE_PROFILES: frozenset[str] = frozenset({"full", "core", "strict"})
REQUIRED_PLAN_FIELDS: tuple[str, ...] = (
    "plan_id",
    "revision",
    "objective",
    "status",
    "steps",
    "stopping_conditions",
    "revision_decision",
)
OPTIONAL_PLAN_FIELDS: tuple[str, ...] = (
    "intent",
    "outcomes",
    "assumes",
    "on_uncertainty",
    "reevaluate_when",
    "request",
    "exploration_budget",
    "reflective_pass",
)
REQUIRED_STEP_FIELDS: tuple[str, ...] = ("id", "action", "construct", "status")


@dataclass(frozen=True)
class AnnotationRule:
    """A check for one annotation keyword. A later rule for the same keyword wins."""

    keyword: str
    check: Check


def _check_binds(text: str, lineno: int, model: ValidationMetamodel) -> list[str]:
    tokens = [part.strip() for part in text.split(",")]
    if not text.strip() or any(model.step_token.fullmatch(part) is None for part in tokens):
        return [
            f"line {lineno}: BINDS requires comma-separated tokens "
            "(for example requirement-record-reason)"
        ]
    return []


def _check_cognition(text: str, lineno: int, model: ValidationMetamodel) -> list[str]:
    value = text.strip().lower().split()[0] if text.strip() else ""
    allowed = "|".join(sorted(model.cognition_values))
    if not value:
        return [f"line {lineno}: COGNITION requires a value ({allowed})"]
    if value not in model.cognition_values:
        return [f"line {lineno}: unknown COGNITION {value!r} (allowed: {sorted(model.cognition_values)})"]
    return []


def _compile_words(names: tuple[str, ...]) -> re.Pattern[str]:
    ordered = sorted(set(names), key=lambda item: (-len(item), item))
    body = "|".join(re.escape(item) for item in ordered)
    return re.compile(rf"^({body})\b(.*)$")


def _compile_annotations(names: tuple[str, ...]) -> re.Pattern[str]:
    ordered = sorted(set(names), key=lambda item: (-len(item), item))
    body = "|".join(re.escape(item) for item in ordered)
    return re.compile(rf"^({body}):\s*(.*)$", re.IGNORECASE)


@functools.lru_cache(maxsize=128)
def _cached_words(names: tuple[str, ...]) -> re.Pattern[str]:
    return _compile_words(names)


@functools.lru_cache(maxsize=128)
def _cached_annotations(names: tuple[str, ...]) -> re.Pattern[str]:
    return _compile_annotations(names)


@functools.lru_cache(maxsize=128)
def _cached_token(pattern: str) -> re.Pattern[str]:
    return re.compile(rf"^{pattern}$")


@functools.lru_cache(maxsize=128)
def _cached_step_name(pattern: str) -> re.Pattern[str]:
    return re.compile(rf"^<({pattern})>\s*(.*)$")


@dataclass(frozen=True)
class ValidationMetamodel:
    """Closed sets and hooks the parser and validators consult.

    ``extend`` unions sets and appends rules. ``override`` swaps fields.
    Patterns are derived from the sets, so a consumer does not edit the parser.
    """

    version: str = CORE_VERSION
    spec_version: str = SPEC_VERSION
    conformance_version: str = CONFORMANCE_VERSION
    core_constructs: frozenset[str] = CORE_CONSTRUCTS
    extension_constructs: frozenset[str] = EXTENSION_CONSTRUCTS
    line_only_constructs: frozenset[str] = LINE_ONLY_CONSTRUCTS
    step_excluded: frozenset[str] = STEP_EXCLUDED
    dropped_constructs: frozenset[str] = frozenset()
    extra_reserved_names: frozenset[str] = LINE_ONLY_CONSTRUCTS
    aliases: tuple[tuple[str, str], ...] = ALIASES
    annotation_surfaces: tuple[str, ...] = ANNOTATION_SURFACES
    annotation_rules: tuple[AnnotationRule, ...] = (
        AnnotationRule("BINDS", _check_binds),
        AnnotationRule("COGNITION", _check_cognition),
    )
    extra_step_checks: tuple[StepCheck, ...] = ()
    cognition_values: frozenset[str] = COGNITION_VALUES
    plan_statuses: frozenset[str] = PLAN_STATUSES
    revision_decisions: frozenset[str] = REVISION_DECISIONS
    step_statuses: frozenset[str] = STEP_STATUSES
    on_uncertainty: frozenset[str] = ON_UNCERTAINTY_POLICIES
    validate_profiles: frozenset[str] = VALIDATE_PROFILES
    required_plan_fields: tuple[str, ...] = REQUIRED_PLAN_FIELDS
    optional_plan_fields: tuple[str, ...] = OPTIONAL_PLAN_FIELDS
    required_step_fields: tuple[str, ...] = REQUIRED_STEP_FIELDS
    step_token_pattern: str = STEP_TOKEN_PATTERN
    require_step_names: bool = False

    @property
    def plan_constructs(self) -> frozenset[str]:
        return (self.core_constructs | self.extension_constructs) - self.dropped_constructs

    @property
    def step_constructs(self) -> frozenset[str]:
        return self.plan_constructs - self.step_excluded

    @property
    def line_constructs(self) -> frozenset[str]:
        return self.step_constructs | (self.plan_constructs - self.dropped_constructs) | (
            self.line_only_constructs - self.dropped_constructs
        )

    @property
    def reserved_step_names(self) -> frozenset[str]:
        return self.plan_constructs | (self.extra_reserved_names - self.dropped_constructs)

    @property
    def step_token(self) -> re.Pattern[str]:
        return _cached_token(self.step_token_pattern)

    @property
    def step_name_pattern(self) -> re.Pattern[str]:
        return _cached_step_name(self.step_token_pattern)

    @property
    def construct_step_pattern(self) -> re.Pattern[str]:
        return _cached_words(tuple(sorted(self.step_constructs)))

    @property
    def construct_line_pattern(self) -> re.Pattern[str]:
        return _cached_words(tuple(sorted(self.line_constructs)))

    @property
    def annotation_pattern(self) -> re.Pattern[str]:
        return _cached_annotations(tuple(self.annotation_surfaces))

    def alias(self, name: str) -> str:
        found = dict(self.aliases)
        return found.get(name, name)

    def rules_by_keyword(self) -> dict[str, AnnotationRule]:
        found: dict[str, AnnotationRule] = {}
        for rule in self.annotation_rules:
            found[rule.keyword.upper().replace(" ", "_")] = rule
        return found

    def extend(
        self,
        *,
        core_constructs: frozenset[str] = frozenset(),
        extension_constructs: frozenset[str] = frozenset(),
        line_only_constructs: frozenset[str] = frozenset(),
        dropped_constructs: frozenset[str] = frozenset(),
        extra_reserved_names: frozenset[str] = frozenset(),
        cognition_values: frozenset[str] = frozenset(),
        plan_statuses: frozenset[str] = frozenset(),
        revision_decisions: frozenset[str] = frozenset(),
        step_statuses: frozenset[str] = frozenset(),
        on_uncertainty: frozenset[str] = frozenset(),
        validate_profiles: frozenset[str] = frozenset(),
        annotation_surfaces: tuple[str, ...] = (),
        annotation_rules: tuple[AnnotationRule, ...] = (),
        extra_step_checks: tuple[StepCheck, ...] = (),
        aliases: tuple[tuple[str, str], ...] = (),
    ) -> ValidationMetamodel:
        """Add vocabulary and checks. This does not remove a default rule or field."""
        return replace(
            self,
            core_constructs=self.core_constructs | frozenset(core_constructs),
            extension_constructs=self.extension_constructs | frozenset(extension_constructs),
            line_only_constructs=self.line_only_constructs | frozenset(line_only_constructs),
            dropped_constructs=self.dropped_constructs | frozenset(dropped_constructs),
            extra_reserved_names=self.extra_reserved_names | frozenset(extra_reserved_names),
            cognition_values=self.cognition_values | frozenset(cognition_values),
            plan_statuses=self.plan_statuses | frozenset(plan_statuses),
            revision_decisions=self.revision_decisions | frozenset(revision_decisions),
            step_statuses=self.step_statuses | frozenset(step_statuses),
            on_uncertainty=self.on_uncertainty | frozenset(on_uncertainty),
            validate_profiles=self.validate_profiles | frozenset(validate_profiles),
            annotation_surfaces=self.annotation_surfaces + tuple(annotation_surfaces),
            annotation_rules=self.annotation_rules + tuple(annotation_rules),
            extra_step_checks=self.extra_step_checks + tuple(extra_step_checks),
            aliases=self.aliases + tuple(aliases),
        )

    def override(self, **changes: Any) -> ValidationMetamodel:
        """Swap fields. A replaced ``annotation_rules`` tuple drops the default checks."""
        return replace(self, **changes)


DEFAULT_METAMODEL = ValidationMetamodel()
