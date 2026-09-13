from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from thesis_bench.benchmarks.base import BenchmarkCase
from thesis_bench.datasets.acquisition import verify_dataset
from thesis_bench.datasets.registry import get_benchmark
from thesis_bench.evaluation.nl4opt import evaluate_nl4opt
from thesis_bench.evaluation.provenance import EVALUATOR_SHA, verify_evaluator
from thesis_bench.evaluation.serialization import record_xml


def _case(record: dict[str, Any]) -> BenchmarkCase:
    return BenchmarkCase(
        benchmark_id="nl4opt_generation",
        benchmark_version="fixture",
        case_id="characterization-case",
        description="fixture",
        raw_record=record,
    )


def characterization_cases() -> dict[str, str]:
    record: dict[str, Any] = {
        "vars": ["x", "y"],
        "order_mapping": {"x": 0, "y": 1},
        "obj_declaration": {
            "type": "objective",
            "direction": "maximize",
            "name": "value",
            "terms": {"x": "2", "y": "3"},
        },
        "const_declarations": [
            {
                "type": "linear",
                "direction": "at most",
                "limit": "10",
                "operator": "LESS_OR_EQUAL",
                "terms": {"x": "1", "y": "1"},
            },
            {
                "type": "lowerbound",
                "direction": "at least",
                "limit": "2",
                "var": "x",
                "operator": "GREATER_OR_EQUAL",
            },
        ],
    }
    perfect = record_xml(record)
    missing = record_xml({**record, "const_declarations": record["const_declarations"][:1]})
    extra_record = {
        **record,
        "const_declarations": [
            *record["const_declarations"],
            {
                "type": "upperbound",
                "direction": "at most",
                "limit": "99",
                "var": "y",
                "operator": "LESS_OR_EQUAL",
            },
        ],
    }
    wrong_coefficient = {
        **record,
        "const_declarations": [
            {**record["const_declarations"][0], "terms": {"x": "2", "y": "1"}},
            record["const_declarations"][1],
        ],
    }
    wrong_rhs = {
        **record,
        "const_declarations": [
            {**record["const_declarations"][0], "limit": "11"},
            record["const_declarations"][1],
        ],
    }
    wrong_objective = {
        **record,
        "obj_declaration": {**record["obj_declaration"], "terms": {"x": "9", "y": "3"}},
    }
    wrong_objective_direction = {
        **record,
        "obj_declaration": {**record["obj_declaration"], "direction": "minimize"},
    }
    wrong_direction = {
        **record,
        "const_declarations": [
            {**record["const_declarations"][0], "operator": "GREATER_OR_EQUAL"},
            record["const_declarations"][1],
        ],
    }
    reordered = {**record, "const_declarations": list(reversed(record["const_declarations"]))}
    scaled = {
        **record,
        "const_declarations": [
            {**record["const_declarations"][0], "limit": "20", "terms": {"x": "2", "y": "2"}},
            record["const_declarations"][1],
        ],
    }
    sign_normalized = {
        **record,
        "const_declarations": [
            {
                **record["const_declarations"][0],
                "operator": "GREATER_OR_EQUAL",
                "limit": "-10",
                "terms": {"x": "-1", "y": "-1"},
            },
            record["const_declarations"][1],
        ],
    }
    return {
        "perfect": perfect,
        "missing_constraint": missing,
        "extra_constraint": record_xml(extra_record),
        "wrong_direction": record_xml(wrong_direction),
        "wrong_coefficient": record_xml(wrong_coefficient),
        "wrong_rhs": record_xml(wrong_rhs),
        "wrong_objective": record_xml(wrong_objective),
        "wrong_objective_direction": record_xml(wrong_objective_direction),
        "constraint_order_permutation": record_xml(reordered),
        "algebraic_scaling": record_xml(scaled),
        "sign_normalized_equivalent": record_xml(sign_normalized),
        "malformed": "<DECLARATION>",
        "empty": "",
        "duplicate_constraint": perfect
        + record_xml(record)[record_xml(record).find("<DECLARATION><CONST_DIR>") :],
    }


def characterize(root: Path) -> dict[str, Any]:
    verify_evaluator(root)
    fixture = _case(
        {
            "vars": ["x", "y"],
            "order_mapping": {"x": 0, "y": 1},
            "obj_declaration": {
                "type": "objective",
                "direction": "maximize",
                "name": "value",
                "terms": {"x": "2", "y": "3"},
            },
            "const_declarations": [
                {
                    "type": "linear",
                    "direction": "at most",
                    "limit": "10",
                    "operator": "LESS_OR_EQUAL",
                    "terms": {"x": "1", "y": "1"},
                },
                {
                    "type": "lowerbound",
                    "direction": "at least",
                    "limit": "2",
                    "var": "x",
                    "operator": "GREATER_OR_EQUAL",
                },
            ],
        }
    )
    rows = []
    for name, prediction in characterization_cases().items():
        result = evaluate_nl4opt(fixture, prediction)
        rows.append(
            {
                "name": name,
                "official_score": result.official_score,
                "parse_status": result.parse_status,
                "false_positives": result.false_positives,
                "false_negatives": result.false_negatives,
                "objective_match": result.objective_match,
            }
        )
    return {
        "evaluator_version": EVALUATOR_SHA,
        "dataset_version": "fixture",
        "case_id": fixture.case_id,
        "variants": rows,
    }


def gold_check(root: Path) -> dict[str, Any]:
    verify_evaluator(root)
    manifest = verify_dataset(root=root)
    adapter = get_benchmark("nl4opt_generation", root=root)
    total = parsed = 0
    errors: list[str] = []
    numerator = denominator = 0
    for split in adapter.supported_splits:
        for case in adapter.iter_cases(split=split):
            total += 1
            try:
                result = evaluate_nl4opt(case, record_xml(case.raw_record or {}))
                parsed += int(result.parse_status != "failed")
                numerator += result.false_positives + result.false_negatives
                denominator += result.denominator
                if result.official_score != 1.0:
                    errors.append(case.case_id)
            except Exception as exc:
                errors.append(f"{case.case_id}: {type(exc).__name__}")
    return {
        "evaluator_version": EVALUATOR_SHA,
        "dataset_version": manifest.source_commit_sha,
        "total_cases": total,
        "successfully_parsed": parsed,
        "anomalous_case_ids": errors,
        "anomaly_count": len(errors),
        "aggregate_official_score": 1 - numerator / denominator,
    }


def write_characterization(root: Path) -> Path:
    path = root / "results" / "nl4opt" / "evaluator_characterization.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(characterize(root), indent=2) + "\n", encoding="utf-8")
    return path
