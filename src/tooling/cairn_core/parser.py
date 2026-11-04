"""Recursive-descent parser for Cairn structural grammar."""

from __future__ import annotations

import re

from cairn_core.ast import (
    Annotation,
    CairnDocument,
    ConstraintsBlock,
    ConstructLine,
    ContextBlock,
    EmergentBlock,
    OutcomesBlock,
    Plan,
    Process,
    ProcessSignature,
    RenderProfileDirective,
    Requirement,
    RequirementsBlock,
    StateBlock,
    StateDecl,
    Step,
)
from cairn_core.extract import extract_cairn_source
from cairn_core.lexer import Line, is_render_profile, tokenize_lines
from cairn_core.metamodel import DEFAULT_METAMODEL, ValidationMetamodel
from cairn_core.tags import extract_bracket_tags, split_tag_list

_STEP_ID = re.compile(r"^(\d+(?:\.\d+)*)([a-z])?\.\s*(.*)$", re.I)
_REQ_ID = re.compile(r"^(R\d+)\.\s*(.*)$", re.I)
_PRIORITY = re.compile(r"\[(MUST|SHOULD|MAY)\]\s*$", re.I)
_PROCESS_HDR = re.compile(
    r"^PROCESS\s+(?:(.+?)\s+\(INPUT:\s*(.+?)\s*;\s*OUTPUT:\s*(.+?)\)|(?:[—–-]\s*)?(.+?))\s*$",
    re.I,
)
_PROCESS_NARRATIVE = re.compile(r"^PROCESS\s+[—–-]\s*(.+?):\s*(.+)$", re.I)
_PLAN_HDR = re.compile(
    r"^PLAN\s+(\S+)\s+REVISION\s+(\d+)\s+\[STATUS:\s*(\w+)\]\s*$",
    re.I,
)
_SIGNATURE = re.compile(r"^\(INPUT:\s*(.+?)\s*;\s*OUTPUT:\s*(.+?)\)\s*$", re.I)
_STATE_DECL = re.compile(
    r"^(\S+)\s+\[scope:\s*([\w./]+)\s*;\s*dir:\s*([\w/]+)\](?:\s+ref:\s*(\S+))?(?:\s+#(.*))?$",
    re.I,
)
# Patterns come from the validation metamodel so a consumer can add a construct
# or an annotation without editing this parser. The module-level names are the
# default model, which the drift test reads.
_ANNOTATION = DEFAULT_METAMODEL.annotation_pattern
_EMERGENT = re.compile(r"^EMERGENT\s+(\[.*?\])\s*$", re.I)
_CONSTRUCT_LINE = DEFAULT_METAMODEL.construct_line_pattern
_CONSTRUCT_STEP = DEFAULT_METAMODEL.construct_step_pattern
_CONSTRUCT_NORMALIZE = dict(DEFAULT_METAMODEL.aliases)
_STEP_NAME = DEFAULT_METAMODEL.step_name_pattern

def _is_section_header(text: str) -> bool:
    return text.upper() in {"CONTEXT", "OUTCOMES", "REQUIREMENTS"}


def _is_block_start(text: str) -> bool:
    """True for real top-level Cairn blocks — not CONTEXT glossary prose.

    CONTEXT often defines terms as ``PLAN — …`` / ``PROCESS — …`` lines. Those
    must not be treated as block headers (they are not ``PLAN id REVISION …`` or
    formal ``PROCESS Name (INPUT:…; OUTPUT:…)`` / narrative ``PROCESS — Name:``).
    """
    if _is_section_header(text):
        return True
    if _PLAN_HDR.match(text):
        return True
    if _PROCESS_NARRATIVE.match(text):
        return True
    match = _PROCESS_HDR.match(text)
    # Formal signature form only (group 1 set). Dash-prose falls through as body.
    if match and match.group(1):
        return True
    return False


class Parser:
    def __init__(self, lines: list[Line], model: ValidationMetamodel | None = None):
        self.lines = lines
        self.pos = 0
        self.errors: list[str] = []
        self.model = model or DEFAULT_METAMODEL

    def _error(self, message: str, line: Line | None = None) -> None:
        if line:
            self.errors.append(f"line {line.lineno}: {message}")
        else:
            self.errors.append(message)

    def _peek(self) -> Line | None:
        if self.pos >= len(self.lines):
            return None
        return self.lines[self.pos]

    def _advance(self) -> Line | None:
        line = self._peek()
        if line:
            self.pos += 1
        return line

    def _at_indent(self, minimum: int) -> bool:
        line = self._peek()
        return line is not None and line.indent >= minimum

    def parse_document(self, source_kind: str = "cairn") -> CairnDocument:
        doc = CairnDocument(source_kind=source_kind)
        operator_mode = False
        while self._peek():
            line = self._peek()
            assert line is not None
            profile = is_render_profile(line)
            if profile:
                self._advance()
                doc.directives.append(RenderProfileDirective(profile=profile, lineno=line.lineno))
                operator_mode = profile.lower() == "operator"
                continue
            upper = line.text.upper()
            if upper == "CONTEXT":
                operator_mode = False
                doc.context_blocks.append(self._parse_context_block())
            elif upper == "OUTCOMES":
                operator_mode = False
                doc.outcomes_blocks.append(self._parse_outcomes_block())
            elif upper == "REQUIREMENTS":
                operator_mode = False
                doc.requirements_blocks.append(self._parse_requirements_block())
            elif upper.startswith("PLAN ") and _PLAN_HDR.match(line.text):
                operator_mode = False
                doc.plans.append(self._parse_plan())
            elif upper.startswith("PLAN "):
                if operator_mode:
                    self._advance()
                else:
                    self._error(f"invalid PLAN header: {line.text!r}", line)
                    self._advance()
            elif upper.startswith("PROCESS"):
                operator_mode = False
                doc.processes.append(self._parse_process())
            elif operator_mode:
                self._advance()
            elif not _is_block_start(line.text):
                self._advance()
            else:
                self._error(f"unexpected top-level line: {line.text!r}", line)
                self._advance()
        doc.parse_errors = list(self.errors)
        return doc

    def _parse_context_block(self) -> ContextBlock:
        line = self._advance()
        assert line is not None
        block = ContextBlock(lineno=line.lineno)
        base = line.indent
        while self._peek() and self._peek().indent == base:
            cur = self._peek()
            assert cur is not None
            # Stop at any top-level block (PLAN/PROCESS/OUTCOMES/…), not only section titles.
            if _is_block_start(cur.text):
                break
            block.lines.append(self._advance().text)  # type: ignore[union-attr]
        return block

    def _parse_outcomes_block(self) -> OutcomesBlock:
        line = self._advance()
        assert line is not None
        block = OutcomesBlock(lineno=line.lineno)
        base = line.indent
        while self._peek() and self._peek().indent == base:
            cur = self._peek()
            assert cur is not None
            if _is_block_start(cur.text):
                break
            emergent = _EMERGENT.match(cur.text)
            if emergent:
                self._advance()
                sat = emergent.group(1)
                attrs = _parse_modifiers_dict([sat.strip("[]")]) if "[" in sat else {}
                eb = EmergentBlock(satisfies=sat, attrs=attrs, lineno=cur.lineno)
                while self._peek() and self._peek().indent > base:
                    eb.lines.append(self._advance().text)  # type: ignore[union-attr]
                block.emergent_blocks.append(eb)
            else:
                block.lines.append(self._advance().text)  # type: ignore[union-attr]
        return block

    def _parse_requirements_block(self) -> RequirementsBlock:
        line = self._advance()
        assert line is not None
        block = RequirementsBlock(lineno=line.lineno)
        base = line.indent
        while self._peek() and self._peek().indent == base:
            cur = self._peek()
            assert cur is not None
            if _is_block_start(cur.text):
                break
            cur = self._advance()
            assert cur is not None
            req_match = _REQ_ID.match(cur.text)
            if not req_match:
                self._error(f"expected requirement id R<n>. …, got {cur.text!r}", cur)
                continue
            body = req_match.group(2).strip()
            priority = None
            pri = _PRIORITY.search(body)
            if pri:
                priority = pri.group(1).upper()
                body = _PRIORITY.sub("", body).strip()
            req = Requirement(req_id=req_match.group(1).upper(), text=body, priority=priority, lineno=cur.lineno)
            req_indent = cur.indent
            while self._peek() and self._peek().indent > req_indent:
                sub = self._advance()
                assert sub is not None
                if sub.text.upper().startswith("ACCEPTANCE:"):
                    req.acceptance = sub.text.split(":", 1)[1].strip()
                else:
                    req.text = f"{req.text} {sub.text}".strip()
            block.requirements.append(req)
        return block

    def _parse_plan(self) -> Plan:
        line = self._advance()
        assert line is not None
        match = _PLAN_HDR.match(line.text)
        if not match:
            self._error(f"invalid PLAN header: {line.text!r}", line)
            return Plan(plan_id="unknown", revision=0, status="draft", lineno=line.lineno)
        plan = Plan(
            plan_id=match.group(1),
            revision=int(match.group(2)),
            status=match.group(3).lower(),
            lineno=line.lineno,
        )
        body_indent = line.indent + 2
        while self._peek() and self._peek().indent >= body_indent:
            cur = self._peek()
            assert cur is not None
            upper = cur.text.upper()
            if upper.startswith("PARENT:"):
                self._advance()
                val = cur.text.split(":", 1)[1].strip()
                plan.parent = None if val.lower() == "none" else val
            elif upper.startswith("REQUEST:"):
                self._advance()
                plan.request = cur.text.split(":", 1)[1].strip()
            elif upper.startswith("TRIGGER:"):
                self._advance()
                plan.trigger = cur.text.split(":", 1)[1].strip()
            elif upper.startswith("INTENT:"):
                self._advance()
                plan.intent = cur.text.split(":", 1)[1].strip()
            elif upper.startswith("ON_UNCERTAINTY:") or upper.startswith("ON-UNCERTAINTY:"):
                self._advance()
                plan.on_uncertainty = cur.text.split(":", 1)[1].strip().lower()
            elif upper.startswith("ASSUMES:"):
                self._advance()
                raw = cur.text.split(":", 1)[1].strip()
                plan.assumes = [p.strip() for p in raw.split(",") if p.strip()]
            elif upper.startswith("OUTCOMES:") or upper == "OUTCOMES":
                self._advance()
                after = cur.text.split(":", 1)[1].strip() if ":" in cur.text else ""
                if after:
                    plan.outcomes.append(after.lstrip("- ").strip())
                # Collect nested bullet lines under OUTCOMES.
                while self._peek() and self._peek().indent > cur.indent:
                    nested = self._advance()
                    assert nested is not None
                    text = nested.text.strip()
                    if text.startswith("-"):
                        text = text[1:].strip()
                    if text:
                        plan.outcomes.append(text)
            elif upper.startswith("REEVALUATE_WHEN:") or upper.startswith("REEVALUATE-WHEN:"):
                self._advance()
                after = cur.text.split(":", 1)[1].strip()
                if after:
                    plan.reevaluate_when.append(after)
                while self._peek() and self._peek().indent > cur.indent:
                    nested = self._advance()
                    assert nested is not None
                    text = nested.text.strip().lstrip("- ").strip()
                    if text:
                        plan.reevaluate_when.append(text)
            elif upper.startswith("EXPLORATION_BUDGET:") or upper.startswith("EXPLORATION-BUDGET:"):
                self._advance()
                raw = cur.text.split(":", 1)[1].strip()
                try:
                    plan.exploration_budget = int(raw)
                except ValueError:
                    self._error(f"EXPLORATION_BUDGET must be an integer, got {raw!r}", cur)
            elif upper.startswith("REFLECTIVE_PASS:") or upper.startswith("REFLECTIVE-PASS:"):
                self._advance()
                raw = cur.text.split(":", 1)[1].strip().lower()
                plan.reflective_pass = raw in {"1", "true", "yes", "on"}
            elif upper.startswith("PROCESS"):
                plan.process = self._parse_process()
            else:
                self._error(f"unexpected PLAN body line: {cur.text!r}", cur)
                self._advance()
        return plan

    def _parse_process(self) -> Process:
        line = self._advance()
        assert line is not None
        proc = Process(name="", lineno=line.lineno)

        narrative = _PROCESS_NARRATIVE.match(line.text)
        if narrative:
            proc.name = narrative.group(1).strip()
            proc.description = narrative.group(2).strip()
        else:
            match = _PROCESS_HDR.match(line.text)
            if not match:
                self._error(f"invalid PROCESS header: {line.text!r}", line)
                proc.name = line.text
            elif match.group(1):
                proc.name = match.group(1).strip()
                proc.signature = ProcessSignature(inputs=match.group(2).strip(), outputs=match.group(3).strip())
            else:
                tail = (match.group(4) or "").strip()
                if ":" in tail:
                    proc.name, proc.description = [p.strip() for p in tail.split(":", 1)]
                else:
                    proc.name = tail or "unnamed"

        body_indent = line.indent + 2
        while self._peek() and self._peek().indent >= body_indent:
            cur = self._peek()
            assert cur is not None
            if cur.indent < body_indent:
                break
            upper = cur.text.upper()
            if upper == "STATE":
                proc.state = self._parse_state_block()
            elif upper in {"CONSTRAINTS", "BOUNDARIES"}:
                proc.constraints = self._parse_constraints_block()
            elif upper == "CONTEXT":
                proc.context = self._parse_context_block()
            elif self.model.annotation_pattern.match(cur.text):
                proc.elements.append(self._parse_annotation())
            elif _STEP_ID.match(cur.text):
                proc.steps.append(self._parse_step(body_indent))
            elif self.model.construct_line_pattern.match(cur.text):
                proc.elements.append(self._parse_construct_line())
            elif proc.signature is None or proc.description:
                self._advance()
            else:
                self._error(f"unexpected PROCESS element: {cur.text!r}", cur)
                self._advance()
        return proc

    def _parse_state_block(self) -> StateBlock:
        line = self._advance()
        assert line is not None
        block = StateBlock(lineno=line.lineno)
        decl_indent = line.indent + 2
        while self._peek() and self._peek().indent >= decl_indent:
            cur = self._advance()
            assert cur is not None
            match = _STATE_DECL.match(cur.text)
            if match:
                block.declarations.append(
                    StateDecl(
                        name=match.group(1),
                        scope=match.group(2).lower(),
                        direction=match.group(3).lower(),
                        ref=match.group(4),
                        comment=match.group(5).strip() if match.group(5) else None,
                        lineno=cur.lineno,
                    )
                )
            else:
                self._error(f"invalid STATE declaration: {cur.text!r}", cur)
        return block

    def _parse_constraints_block(self) -> ConstraintsBlock:
        line = self._advance()
        assert line is not None
        keyword = line.text.split(":", 1)[0].strip().upper()
        block = ConstraintsBlock(keyword=keyword, lineno=line.lineno)
        if ":" in line.text:
            block.inline_text = line.text.split(":", 1)[1].strip()
            return block
        inner = line.indent + 2
        while self._peek() and self._peek().indent >= inner:
            block.lines.append(self._advance().text)  # type: ignore[union-attr]
        return block

    def _parse_annotation(self) -> Annotation:
        line = self._advance()
        assert line is not None
        ann = self.model.annotation_pattern.match(line.text)
        assert ann is not None
        annotation = Annotation(
            keyword=ann.group(1).upper().replace(" ", "_"),
            text=ann.group(2).strip(),
            lineno=line.lineno,
        )
        while self._peek() and self._peek().indent > line.indent:
            sub = self._peek()
            assert sub is not None
            if self.model.annotation_pattern.match(sub.text) or _is_block_start(sub.text) or _STEP_ID.match(sub.text):
                break
            annotation.text = f"{annotation.text}\n{sub.text}".strip()
            self._advance()
        return annotation

    def _parse_step(self, parent_indent: int) -> Step:
        line = self._advance()
        assert line is not None
        step_match = _STEP_ID.match(line.text)
        construct = None
        body = line.text
        step_id = ""

        step_name = None
        if step_match:
            step_id = step_match.group(1) + (step_match.group(2) or "")
            body = step_match.group(3).strip()
            name_match = self.model.step_name_pattern.match(body)
            if name_match:
                step_name = name_match.group(1)
                body = name_match.group(2).strip()
        else:
            cl = self.model.construct_line_pattern.match(line.text)
            if cl:
                step_id = "0"
                construct = self.model.alias(cl.group(1).upper())
                body = cl.group(2).strip()
            else:
                self._error(f"invalid step line: {line.text!r}", line)
                step_id = "0"
                body = line.text

        cstep = self.model.construct_step_pattern.match(body)
        mods = []
        if cstep:
            construct = self.model.alias(cstep.group(1).upper())
            body = cstep.group(2).strip()
            # parse leading [modifiers] for the construct itself (e.g. REGULATION [STRATEGY: ...])
            mod_match = re.match(r"^(\[[^\]]+\])\s*(.*)$", body)
            if mod_match:
                mods = split_tag_list(mod_match.group(1).strip("[]"))
                body = mod_match.group(2).strip()

        cleaned, tags = extract_bracket_tags(body)
        if cleaned.startswith("→"):
            cleaned = cleaned.lstrip("→").strip()

        parsed_mods = _parse_modifiers_dict(mods)
        step = Step(
            step_id=step_id,
            name=step_name,
            construct=construct,
            text=cleaned,
            tags=tags,
            lineno=line.lineno,
            modifiers=mods,
            parsed_modifiers=parsed_mods,
        )
        child_indent = line.indent + 2
        while self._peek() and self._peek().indent >= child_indent:
            cur = self._peek()
            assert cur is not None
            ann = self.model.annotation_pattern.match(cur.text)
            if ann:
                step.annotations.append(self._parse_annotation())
                continue
            cline = self.model.construct_line_pattern.match(cur.text)
            if cline and not _STEP_ID.match(cur.text):
                step.construct_lines.append(self._parse_construct_line())
                continue
            if _STEP_ID.match(cur.text):
                step.children.append(self._parse_step(line.indent))
                continue
            self._advance()
        return step

    def _parse_construct_line(self) -> ConstructLine:
        line = self._advance()
        assert line is not None
        match = self.model.construct_line_pattern.match(line.text)
        if not match:
            return ConstructLine(construct="STEP", text=line.text, lineno=line.lineno, parsed_modifiers={})
        construct = self.model.alias(match.group(1).upper())
        rest = match.group(2).strip()
        arrow_target = None
        if "→" in rest:
            before, after = rest.split("→", 1)
            rest = before.strip()
            arrow_target = after.strip()
        mods: list[str] = []
        mod_match = re.match(r"^(\[[^\]]+\])\s*(.*)$", rest)
        if mod_match:
            mods = split_tag_list(mod_match.group(1).strip("[]"))
            rest = mod_match.group(2).strip()
        cleaned, tags = extract_bracket_tags(rest)
        if tags:
            mods.extend(tags)
        parsed_mods = _parse_modifiers_dict(mods)
        return ConstructLine(
            construct=construct,
            modifiers=mods,
            parsed_modifiers=parsed_mods,
            arrow_target=arrow_target,
            text=cleaned,
            lineno=line.lineno,
        )


def _parse_modifiers_dict(mods: list[str]) -> dict[str, str]:
    """Parse modifier list like ['STRATEGY: foo', 'TARGET: bar'] or with ; into dict."""
    result: dict[str, str] = {}
    for m in mods:
        # split on ; or , for compound
        for part in m.replace(";", ",").split(","):
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                k, v = part.split(":", 1)
                result[k.strip().upper()] = v.strip()
            else:
                result[part.upper()] = "true"
    return result


def parse_document(text: str, model: ValidationMetamodel | None = None) -> CairnDocument:
    """Parse Cairn skeleton text or markdown-wrapped ``.cairn.md`` content."""
    source, kind = extract_cairn_source(text)
    lines = tokenize_lines(source)
    parser = Parser(lines, model)
    return parser.parse_document(source_kind=kind)
