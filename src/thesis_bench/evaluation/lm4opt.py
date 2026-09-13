"""Paper-reconstructed compatibility parser; not the original LM4OPT implementation."""

from __future__ import annotations

import math
import re
from typing import Literal
from xml.sax.saxutils import escape

from thesis_bench.models import SchemaModel

PARSER_ID = "lm4opt_paper_reconstructed"
PARSER_VERSION = "1"
_SECTIONS = ("variables", "constraints", "objective function")


class LM4OptResponse(SchemaModel):
    raw_text: str
    variables: tuple[str, ...]
    constraints: tuple[str, ...]
    objective: str | None
    missing_sections: tuple[str, ...] = ()
    extra_text: str = ""
    structural_errors: tuple[str, ...] = ()


class LM4OptCanonical(SchemaModel):
    variables: tuple[str, ...]
    objective: tuple[float, ...]
    constraints: tuple[tuple[float, ...], ...]
    source_objective_direction: Literal["minimize", "maximize"]
    canonical_objective_direction: Literal["minimize"] = "minimize"


class LM4OptParseResult(SchemaModel):
    parser_id: Literal["lm4opt_paper_reconstructed"] = PARSER_ID
    parser_version: Literal["1"] = PARSER_VERSION
    response: LM4OptResponse
    canonical: LM4OptCanonical | None = None
    errors: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


def _unmath(text: str) -> str:
    text = text.strip()
    while text.startswith("$") and text.endswith("$"):
        text = text[1:-1].strip()
    return text


def parse_response(raw_text: str) -> LM4OptResponse:
    """Identify sections without requiring correct mathematics; retain the full raw string."""
    markers = list(re.finditer(
        r"(?im)^[ \t]*(Variables|Constraints|Objective Function)[ \t]*:", raw_text
    ))
    sections: dict[str, str] = {}
    errors: list[str] = []
    names = [marker.group(1).lower() for marker in markers]
    for index, marker in enumerate(markers):
        key = names[index]
        end = markers[index + 1].start() if index + 1 < len(markers) else len(raw_text)
        if key in sections:
            errors.append(f"duplicate section: {key}")
        else:
            sections[key] = raw_text[marker.end():end]
    if names != [name for name in _SECTIONS if name in names]:
        errors.append("sections must appear once in Variables/Constraints/Objective Function order")
    objective_lines = [
        line.strip() for line in sections.get("objective function", "").splitlines()
        if line.strip()
    ]
    extra = [raw_text[:markers[0].start()] if markers else raw_text, *objective_lines[1:]]
    return LM4OptResponse(
        raw_text=raw_text,
        variables=tuple(
            item.strip() for item in _unmath(sections.get("variables", "")).split(",")
            if item.strip()
        ),
        constraints=tuple(
            _unmath(line) for line in sections.get("constraints", "").splitlines()
            if line.strip()
        ),
        objective=_unmath(objective_lines[0]) if objective_lines else None,
        missing_sections=tuple(name for name in _SECTIONS if name not in sections),
        extra_text="\n".join(part.strip() for part in extra if part.strip()),
        structural_errors=tuple(errors),
    )


_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)"
_TERM = re.compile(rf"\(\s*({_NUMBER})\s*\)\s*\*\s*(.+)")
_CONSTRAINT = re.compile(rf"(.+?)\s*(?:<=|≤|\\leq)\s*({_NUMBER})")


def _finite(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("coefficient/RHS is not finite")
    return value


def _linear(
    expression: str, variables: tuple[str, ...], *, paper_hotel_alias: bool, notes: list[str]
) -> tuple[float, ...]:
    coefficients = [0.0] * len(variables)
    seen: set[str] = set()
    for term in re.split(r"\s+\+\s+", expression.strip()):
        match = _TERM.fullmatch(term)
        if match is None:
            raise ValueError(f"unsupported linear term: {term!r}")
        value, variable = match.groups()
        variable = variable.strip()
        if (
            paper_hotel_alias and variables == ("cleaners", "receptionists")
            and variable == "receptionist"
        ):
            variable = "receptionists"
            note = "explicit Figure 1 assumption: receptionist refers to receptionists"
            if note not in notes:
                notes.append(note)
        if variable not in variables:
            raise ValueError(f"undeclared variable: {variable!r}")
        if variable in seen:
            raise ValueError(f"repeated term for variable: {variable!r}")
        seen.add(variable)
        coefficients[variables.index(variable)] = _finite(value)
    return tuple(coefficients)


class LM4OptPaperReconstructedParser:
    """Explicit-linear grammar independent of case references and gold mappings.

    The optional paper-example alias is exclusively for the documented Figure 1
    regression. Normal mock runs use strict spelling and never enable this assumption.
    """

    def convert(
        self, response: LM4OptResponse, *, paper_hotel_alias: bool = False
    ) -> LM4OptParseResult:
        errors = list(response.structural_errors)
        notes: list[str] = []
        if response.missing_sections:
            errors.append(f"missing sections: {response.missing_sections}")
        if response.extra_text:
            errors.append("unexpected text outside the three sections")
        variables = response.variables
        if not variables or len(set(variables)) != len(variables):
            errors.append("variables must be nonempty and unique")
        if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_ -]*", name) for name in variables):
            errors.append("unsupported variable name")
        match = re.fullmatch(r"(minimize|maximize)\s+(.+)", response.objective or "")
        objective: tuple[float, ...] = ()
        direction: Literal["minimize", "maximize"] = "minimize"
        if match is None:
            errors.append("objective must be minimize/maximize followed by a linear expression")
        else:
            direction = "maximize" if match.group(1) == "maximize" else "minimize"
            try:
                objective = _linear(
                    match.group(2), variables, paper_hotel_alias=paper_hotel_alias, notes=notes
                )
                if direction == "maximize":
                    objective = tuple(-value for value in objective)
                    notes.append(
                        "maximization coefficients negated for paper minimization convention"
                    )
            except ValueError as exc:
                errors.append(f"objective: {exc}")
        rows: list[tuple[float, ...]] = []
        for index, line in enumerate(response.constraints):
            try:
                constraint = _CONSTRAINT.fullmatch(line)
                if constraint is None:
                    raise ValueError("expected an explicit linear expression followed by <= RHS")
                terms = _linear(
                    constraint.group(1), variables, paper_hotel_alias=paper_hotel_alias, notes=notes
                )
                rows.append((*terms, _finite(constraint.group(2))))
            except ValueError as exc:
                errors.append(f"constraint {index + 1}: {exc}")
        canonical = None if errors else LM4OptCanonical(
            variables=variables, objective=objective, constraints=tuple(rows),
            source_objective_direction=direction,
        )
        return LM4OptParseResult(
            response=response, canonical=canonical, errors=tuple(errors), notes=tuple(notes)
        )

    def parse(self, raw_text: str, *, paper_hotel_alias: bool = False) -> LM4OptParseResult:
        return self.convert(parse_response(raw_text), paper_hotel_alias=paper_hotel_alias)


def to_phase2_xml(canonical: LM4OptCanonical) -> str:
    """Our explicit bridge, not a claim about the authors' unreleased conversion path."""
    body = "<OBJ_DIR>minimize</OBJ_DIR><OBJ_NAME>objective</OBJ_NAME>"
    for variable, coefficient in zip(canonical.variables, canonical.objective, strict=True):
        body += f"<VAR>{escape(variable)}</VAR><PARAM>{coefficient}</PARAM>"
    declarations = [f"<DECLARATION>{body}</DECLARATION>"]
    for row in canonical.constraints:
        terms = "<CONST_DIR>at most</CONST_DIR><OPERATOR>LESS_OR_EQUAL</OPERATOR>"
        terms += f"<LIMIT>{row[-1]}</LIMIT><CONST_TYPE>[LINEAR_CONSTRAINT]</CONST_TYPE>"
        for variable, coefficient in zip(canonical.variables, row[:-1], strict=True):
            terms += f"<VAR>{escape(variable)}</VAR><PARAM>{coefficient}</PARAM>"
        declarations.append(f"<DECLARATION>{terms}</DECLARATION>")
    return "".join(declarations)
