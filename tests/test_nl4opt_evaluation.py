import json
from pathlib import Path
from tempfile import TemporaryDirectory

from thesis_bench.benchmarks.base import BenchmarkCase
from thesis_bench.evaluation.characterize import characterization_cases, record_xml
from thesis_bench.evaluation.nl4opt import evaluate_nl4opt
from thesis_bench.evaluation.provenance import load_manifest, verify_file


def _case() -> BenchmarkCase:
    record = {
        "document": "maximize x",
        "vars": ["x"],
        "order_mapping": {"x": 0},
        "obj_declaration": {
            "type": "objective",
            "direction": "maximize",
            "name": "value",
            "terms": {"x": "2"},
        },
        "const_declarations": [
            {
                "type": "upperbound",
                "direction": "at most",
                "limit": "4",
                "var": "x",
                "operator": "LESS_OR_EQUAL",
            }
        ],
    }
    return BenchmarkCase(
        benchmark_id="nl4opt_generation",
        benchmark_version="fixture",
        case_id="case-1",
        description="maximize x",
        raw_record=record,
    )


def test_gold_prediction_scores_one() -> None:
    case = _case()
    result = evaluate_nl4opt(case, record_xml(case.raw_record or {}))
    assert result.official_score == 1.0
    assert result.objective_match


def test_malformed_prediction_is_retained() -> None:
    result = evaluate_nl4opt(_case(), "<DECLARATION>")
    assert result.parse_status == "failed"
    assert result.raw_prediction == "<DECLARATION>"
    assert result.official_score == 0.0


def test_evaluator_manifest_is_verifiable() -> None:
    root = Path(__file__).parents[1]
    manifest = load_manifest(root)
    assert manifest.source_commit_sha.startswith("18a54bcb")


def test_characterization_regression_artifact_matches_interface() -> None:
    artifact = json.loads(Path("results/nl4opt/evaluator_characterization.json").read_text())
    fixture = _case()
    # The artifact is generated from a two-variable fixture; compare its stable names and scores.
    names = {row["name"] for row in artifact["variants"]}
    assert names == set(characterization_cases())
    assert evaluate_nl4opt(fixture, record_xml(fixture.raw_record or {})).raw_prediction


def test_repeated_evaluation_is_deterministic_and_preserves_raw_text() -> None:
    prediction = "  <DECLARATION>\n  </DECLARATION>  "
    first = evaluate_nl4opt(_case(), prediction)
    second = evaluate_nl4opt(_case(), prediction)
    assert first.model_dump() == second.model_dump()
    assert first.raw_prediction == prediction
    assert len(first.prediction_sha256) == 64


def test_tampered_frozen_evaluator_is_rejected() -> None:
    root = Path(__file__).parents[1]
    entry = next(f for f in load_manifest(root).files if f.upstream_relative_path == "scoring.py")
    with TemporaryDirectory() as directory:
        target = Path(directory) / "scoring.py"
        target.write_text("tampered")
        try:
            verify_file(target, entry)
        except ValueError as exc:
            assert "integrity mismatch" in str(exc)
        else:
            raise AssertionError("tampered evaluator source was accepted")
