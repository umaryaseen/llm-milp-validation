"""Auditable wrapper around the pinned, attributed official NL4Opt evaluator."""

from __future__ import annotations

import copy
import hashlib
import math
import xml.etree.ElementTree as ET
from dataclasses import asdict
from typing import Literal

import numpy as np
from pydantic import Field, JsonValue

from thesis_bench._vendor.nl4opt import parsers, scoring
from thesis_bench.benchmarks.base import BenchmarkCase
from thesis_bench.evaluation.provenance import EVALUATOR_SHA
from thesis_bench.evaluation.serialization import record_xml
from thesis_bench.models import NonEmptyStr, SchemaModel

EVALUATOR_ID = "nl4opt_official_evaluator"
EVALUATOR_VERSION = EVALUATOR_SHA
IMPLEMENTATION_VERSION = "0.1.0"


class EvaluationResult(SchemaModel):
    evaluator_id: Literal["nl4opt_official_evaluator"] = EVALUATOR_ID
    evaluator_version: NonEmptyStr = EVALUATOR_VERSION
    implementation_version: NonEmptyStr = IMPLEMENTATION_VERSION
    benchmark_id: NonEmptyStr
    benchmark_version: NonEmptyStr
    case_id: NonEmptyStr
    reference_mode: Literal["official_xml", "source_json"]
    raw_prediction: str
    prediction_sha256: NonEmptyStr
    parse_status: Literal["success", "recovered", "partial", "failed"]
    parsed_prediction: JsonValue
    predicted_canonical: JsonValue
    gold_canonical: JsonValue
    objective_match: bool
    matched_constraints: int
    predicted_constraints: int
    gold_constraints: int
    false_positives: int
    false_negatives: int
    denominator: int
    official_score: float = Field(allow_inf_nan=False)
    diagnostics: list[str] = Field(default_factory=list)
    error: str | None = None


class _ObservedParser(parsers.ModelOutputXMLParser):
    """Record upstream recovery/skipping without changing parser return values."""

    def __init__(self) -> None:
        super().__init__(print_errors=False)
        self.events: list[str] = []

    def parse_constraint(
        self, root: ET.Element, entities: dict[str, int]
    ) -> parsers.ConstraintDeclaration:
        try:
            return super().parse_constraint(root, entities)
        except ValueError as exc:
            # The upstream parse method catches this and skips the declaration.
            self.events.append(f"upstream skipped constraint: {type(exc).__name__}")
            raise


def _json_safe(value: object) -> JsonValue:
    """Represent non-finite upstream values explicitly; scoring still uses the original arrays."""
    if isinstance(value, float) and not math.isfinite(value):
        return {"non_finite": str(value)}
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported diagnostic value: {type(value).__name__}")


def _canonical_json(value: parsers.CanonicalFormulation) -> JsonValue:
    return _json_safe(
        {"objective": value.objective.tolist(), "constraints": value.constraints.tolist()}
    )


def evaluate_nl4opt(
    case: BenchmarkCase,
    prediction: str,
    *,
    reference_mode: Literal["official_xml", "source_json"] = "official_xml",
) -> EvaluationResult:
    if case.benchmark_id != "nl4opt_generation" or case.raw_record is None:
        raise ValueError("NL4Opt evaluation requires a raw NL4Opt generation record")
    if reference_mode not in {"official_xml", "source_json"}:
        raise ValueError("unsupported reference mode")
    record = copy.deepcopy(case.raw_record)
    order = record["order_mapping"]
    if not isinstance(order, dict):
        raise ValueError("NL4Opt order_mapping must be an object")
    observer = _ObservedParser()
    parsed = observer.parse(prediction, copy.deepcopy(order))
    diagnostics = observer.events.copy()
    recovered = False
    try:
        ET.fromstring(f"<s>{prediction}</s>")
    except ET.ParseError:
        recovered = True
        diagnostics.append("input is not well-formed XML; upstream BeautifulSoup recovery was used")
    failed = not prediction.strip() or (
        parsed.objective.direction == "" and not parsed.entities and not parsed.objective.terms
    )
    status = (
        "failed"
        if failed
        else "partial"
        if observer.events
        else "recovered"
        if recovered
        else "success"
    )
    if failed:
        diagnostics.append("upstream returned an empty ProblemFormulation after parsing failure")
    if reference_mode == "official_xml":
        gold_parsed = parsers.ModelOutputXMLParser(False).parse(
            record_xml(record), copy.deepcopy(order)
        )
    else:
        gold_parsed = parsers.JSONFormulationParser(False).parse(
            {case.case_id: record}, copy.deepcopy(order)
        )
    pred = parsers.convert_to_canonical(parsed)
    gold = parsers.convert_to_canonical(gold_parsed)
    fp, fn, denominator = scoring.per_example_scores(
        pred.objective,
        pred.constraints,
        gold.objective,
        gold.constraints,
    )
    unique = np.unique(pred.constraints, axis=0)
    objective_match = pred.objective.shape == gold.objective.shape and bool(
        (pred.objective == gold.objective).all()
    )
    matches = sum(
        len(row) > 0
        and len(gold.constraints) > 0
        and row.shape[0] == gold.constraints.shape[1]
        and bool((row == gold.constraints).all(axis=1).any())
        for row in unique
    )
    return EvaluationResult(
        benchmark_id=case.benchmark_id,
        benchmark_version=case.benchmark_version,
        case_id=case.case_id,
        reference_mode=reference_mode,
        raw_prediction=prediction,
        prediction_sha256=hashlib.sha256(prediction.encode("utf-8")).hexdigest(),
        parse_status=status,
        parsed_prediction=_json_safe(asdict(parsed)),
        predicted_canonical=_canonical_json(pred),
        gold_canonical=_canonical_json(gold),
        objective_match=objective_match,
        matched_constraints=int(matches),
        predicted_constraints=len(unique),
        gold_constraints=len(gold.constraints),
        false_positives=int(fp),
        false_negatives=int(fn),
        denominator=int(denominator),
        official_score=float(1 - (fp + fn) / denominator),
        diagnostics=diagnostics,
        error="upstream parse fallback" if failed else None,
    )
