"""AST nodes for Cairn structural grammar (GRAMMAR.md EBNF)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RenderProfileDirective:
    profile: str
    lineno: int = 0


@dataclass
class ContextBlock:
    lines: list[str] = field(default_factory=list)
    lineno: int = 0


@dataclass
class OutcomesBlock:
    lines: list[str] = field(default_factory=list)
    emergent_blocks: list[EmergentBlock] = field(default_factory=list)
    lineno: int = 0


@dataclass
class EmergentBlock:
    satisfies: str
    lines: list[str] = field(default_factory=list)
    lineno: int = 0
    # Enhanced for domain/feedback support (e.g. [TYPE: psychological; FROM: regulation; VIA: feedback])
    attrs: dict[str, str] = field(default_factory=dict)


@dataclass
class Requirement:
    req_id: str
    text: str
    priority: str | None = None
    acceptance: str | None = None
    lineno: int = 0


@dataclass
class RequirementsBlock:
    requirements: list[Requirement] = field(default_factory=list)
    lineno: int = 0


@dataclass
class StateDecl:
    name: str
    scope: str
    direction: str
    ref: str | None = None
    comment: str | None = None
    lineno: int = 0


@dataclass
class StateBlock:
    declarations: list[StateDecl] = field(default_factory=list)
    lineno: int = 0


@dataclass
class ConstraintsBlock:
    keyword: str  # CONSTRAINTS | BOUNDARIES
    inline_text: str | None = None
    lines: list[str] = field(default_factory=list)
    lineno: int = 0


@dataclass
class Annotation:
    keyword: str
    text: str
    lineno: int = 0


@dataclass
class ConstructLine:
    construct: str
    modifiers: list[str] = field(default_factory=list)
    parsed_modifiers: dict[str, str] = field(default_factory=dict)
    arrow_target: str | None = None
    text: str = ""
    lineno: int = 0


@dataclass
class Step:
    step_id: str
    # Stable token (`receive-invoice`). Optional. Numbers stay the reading order.
    name: str | None = None
    construct: str | None = None
    text: str = ""
    tags: list[str] = field(default_factory=list)
    annotations: list[Annotation] = field(default_factory=list)
    construct_lines: list[ConstructLine] = field(default_factory=list)
    children: list[Step] = field(default_factory=list)
    lineno: int = 0
    # For steps that are themselves domain constructs (e.g. "2. REGULATION [...]")
    modifiers: list[str] = field(default_factory=list)
    parsed_modifiers: dict[str, str] = field(default_factory=dict)


@dataclass
class ProcessSignature:
    inputs: str
    outputs: str


@dataclass
class Process:
    name: str
    signature: ProcessSignature | None = None
    description: str | None = None
    state: StateBlock | None = None
    constraints: ConstraintsBlock | None = None
    context: ContextBlock | None = None
    elements: list[Any] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    lineno: int = 0


@dataclass
class Plan:
    plan_id: str
    revision: int
    status: str
    parent: str | None = None
    request: str = ""
    trigger: str = ""
    # Cross-LLM framing fields (SPEC v0.10) — optional, additive.
    intent: str = ""
    outcomes: list[str] = field(default_factory=list)
    assumes: list[str] = field(default_factory=list)  # capability@version pins
    on_uncertainty: str = ""  # record | escalate | abort
    reevaluate_when: list[str] = field(default_factory=list)
    exploration_budget: int | None = None  # Phase F: opt-in re-entry bound
    reflective_pass: bool = False  # Phase F: flag low-confidence infer/evaluate
    process: Process | None = None
    lineno: int = 0


@dataclass
class CairnDocument:
    directives: list[RenderProfileDirective] = field(default_factory=list)
    context_blocks: list[ContextBlock] = field(default_factory=list)
    requirements_blocks: list[RequirementsBlock] = field(default_factory=list)
    outcomes_blocks: list[OutcomesBlock] = field(default_factory=list)
    processes: list[Process] = field(default_factory=list)
    plans: list[Plan] = field(default_factory=list)
    source_kind: str = "cairn"
    parse_errors: list[str] = field(default_factory=list)