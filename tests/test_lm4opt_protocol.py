import json
from pathlib import Path

import pytest

from thesis_bench.benchmarks.base import BenchmarkCase
from thesis_bench.evaluation.lm4opt import LM4OptPaperReconstructedParser
from thesis_bench.experiments.lm4opt import run_lm4opt_mock
from thesis_bench.experiments.storage import ArtifactConflictError
from thesis_bench.prompts.lm4opt import (
    PROTOCOL_ONE_SHOT,
    PROTOCOL_ZERO_SHOT,
    get_lm4opt_protocol,
    protocol_names,
)

ROOT = Path(__file__).parents[1]


def _snapshot_case() -> BenchmarkCase:
    data = json.loads((ROOT / "tests/fixtures/lm4opt/snapshot_case.json").read_text())
    return BenchmarkCase(**data)


def _case_with_gold() -> BenchmarkCase:
    return BenchmarkCase(
        benchmark_id="nl4opt_generation",
        benchmark_version="fixture",
        case_id="fixture-1",
        split="test",
        description="Maximize the value of x subject to a limit.",
        raw_record={
            "document": "Maximize the value of x subject to a limit.",
            "vars": ["x"],
            "order_mapping": {"x": 0},
            "obj_declaration": {
                "type": "objective", "direction": "maximize", "name": "value",
                "terms": {"x": "2"},
            },
            "const_declarations": [{
                "type": "upperbound",
                "direction": "at most", "limit": "4", "var": "x",
                "operator": "LESS_OR_EQUAL",
            }],
        },
    )


def test_protocols_are_versioned_and_hashes_are_stable() -> None:
    assert protocol_names() == (PROTOCOL_ZERO_SHOT, PROTOCOL_ONE_SHOT)
    case = _snapshot_case()
    assert get_lm4opt_protocol(PROTOCOL_ZERO_SHOT).version == "1"
    assert get_lm4opt_protocol(PROTOCOL_ONE_SHOT).version == "1"
    assert get_lm4opt_protocol(PROTOCOL_ZERO_SHOT).template_sha256 == (
        "04676a74833d4938f83fd53b492065aa6403d6156600b18edce6b4de282de249"
    )
    assert get_lm4opt_protocol(PROTOCOL_ONE_SHOT).rendered_prompt_sha256(case) == (
        "6f1096991c70e55296d5664110dd2e815d07efd5202681eebbbe65ae8adcb31b"
    )


def test_snapshots_and_condition_distinction() -> None:
    case = _snapshot_case()
    zero = get_lm4opt_protocol(PROTOCOL_ZERO_SHOT).render(case)[0].content
    one = get_lm4opt_protocol(PROTOCOL_ONE_SHOT).render(case)[0].content
    assert zero == (ROOT / "tests/fixtures/prompts/lm4opt/-804075997_zero_shot.txt").read_text()
    assert one == (ROOT / "tests/fixtures/prompts/lm4opt/-804075997_one_shot.txt").read_text()
    assert "Example Problem Description" not in zero
    assert "Example Problem Description" in one
    assert case.description in zero and case.description in one


def test_prompt_exposes_description_only() -> None:
    case = _snapshot_case().model_copy(update={
        "reference_formulation": "GOLD-CONSTRAINT",
        "reference_objective": "GOLD-OBJECTIVE",
        "named_entities": {"gold": "NER"},
        "raw_record": {"obj_declaration": "GOLD-OBJ", "const_declarations": "GOLD-CONST"},
    })
    prompt = get_lm4opt_protocol(PROTOCOL_ONE_SHOT).render(case)[0].content
    for forbidden in ("GOLD-CONSTRAINT", "GOLD-OBJECTIVE", "GOLD-OBJ", "GOLD-CONST", "NER"):
        assert forbidden not in prompt


def test_structural_failures_are_visible_and_raw_text_is_preserved() -> None:
    raw = "prefix\nVariables: x\nObjective Function:\nminimize (1) * x\nsuffix"
    parsed = LM4OptPaperReconstructedParser().parse(raw)
    assert parsed.response.raw_text == raw
    assert "constraints" in parsed.response.missing_sections
    assert parsed.errors
    assert any("unexpected text" in error for error in parsed.errors)


def test_source_level_doubled_dollar_math_is_accepted() -> None:
    raw = (
        "Variables: $$x, y$$\nConstraints:\n$$(1.0) * x + (2.0) * y <= 4.0$$\n"
        "Objective Function:\n$$minimize (3.0) * x + (4.0) * y$$"
    )
    result = LM4OptPaperReconstructedParser().parse(raw)
    assert result.canonical is not None
    assert result.canonical.objective == (3.0, 4.0)


def test_fixture_coverage_and_malformed_variants() -> None:
    cases = json.loads((ROOT / "tests/fixtures/lm4opt/cases.json").read_text())
    assert sum(item["split"] == "train" for item in cases) >= 2
    assert sum(item["split"] == "dev" for item in cases) >= 2
    assert sum(item["split"] == "test" for item in cases) >= 5
    parser = LM4OptPaperReconstructedParser()
    malformed = (ROOT / "tests/fixtures/lm4opt/responses/malformed.txt").read_text()
    missing = (ROOT / "tests/fixtures/lm4opt/responses/missing_constraints.txt").read_text()
    wrong = (ROOT / "tests/fixtures/lm4opt/responses/wrong_objective.txt").read_text()
    assert parser.parse(malformed).response.raw_text == malformed
    assert "constraints" in parser.parse(missing).response.missing_sections
    assert parser.parse(wrong).canonical is not None


def test_hotel_figure_regression_and_explicit_typo_assumption() -> None:
    raw = """Variables: cleaners, receptionists
Constraints:
(-1.0) * cleaners + (-1.0) * receptionists <= -100.0
(-0.0) * cleaners + (-1.0) * receptionists <= -20.0
(0.33) * cleaners + (-1.0) * receptionists <= -0.0
(500.0) * cleaners + (350.0) * receptionists <= 30000.0
Objective Function:
minimize (500.0) * cleaners + (350.0) * receptionist"""
    result = LM4OptPaperReconstructedParser().parse(raw, paper_hotel_alias=True)
    assert result.canonical is not None
    assert result.canonical.constraints == (
        (-1.0, -1.0, -100.0), (0.0, -1.0, -20.0),
        (0.33, -1.0, 0.0), (500.0, 350.0, 30000.0),
    )
    assert result.canonical.objective == (500.0, 350.0)
    assert result.notes


def test_maximize_conversion_is_explicit() -> None:
    raw = "Variables: x\nConstraints:\n(1.0) * x <= 4.0\nObjective Function:\nmaximize (2.0) * x"
    result = LM4OptPaperReconstructedParser().parse(raw)
    assert result.canonical is not None
    assert result.canonical.objective == (-2.0,)
    assert "maximization coefficients negated" in result.notes[0]


@pytest.mark.parametrize("protocol", [PROTOCOL_ZERO_SHOT, PROTOCOL_ONE_SHOT])
def test_mock_end_to_end_and_run_conflict(tmp_path: Path, protocol: str) -> None:
    case = _case_with_gold()
    response = (
        "Variables: x\nConstraints:\n(1.0) * x <= 4.0\n"
        "Objective Function:\nminimize (2.0) * x"
    )
    path = run_lm4opt_mock(tmp_path, case, protocol, response, run_id="fixed")
    assert json.loads((path / "evaluation.json").read_text())["official_score"] == 1.0
    record = json.loads((path / "record.json").read_text())
    assert record["template_sha256"]
    assert record["rendered_prompt_sha256"]
    assert json.loads((path / "response.json").read_text())["provider"] == "mock"
    with pytest.raises(ArtifactConflictError):
        run_lm4opt_mock(tmp_path, case, protocol, response, run_id="fixed")
