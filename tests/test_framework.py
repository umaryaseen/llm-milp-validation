import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from thesis_bench.benchmarks.mock import MockBenchmark
from thesis_bench.config.loader import load_config
from thesis_bench.config.models import RunConfig
from thesis_bench.experiments.models import ExperimentRecord
from thesis_bench.experiments.runner import RunFailedError, dry_run, run_case
from thesis_bench.experiments.storage import ArtifactConflictError
from thesis_bench.providers.base import GenerationConfig, LLMRequest, LLMResponse, Message
from thesis_bench.providers.mock import MockLLMProvider

CONFIG = Path(__file__).parents[1] / "configs" / "mock.toml"


def test_configuration_validation_rejects_unknown_fields() -> None:
    config = load_config(CONFIG)
    assert config.model.provider == "mock"
    invalid = config.model_dump(mode="python")
    invalid["unknown"] = True
    with pytest.raises(ValidationError):
        RunConfig.model_validate(invalid)


def test_mock_provider_is_deterministic() -> None:
    request = LLMRequest(
        model_id="fixture-v1",
        messages=(Message(role="user", content="hello"),),
        generation=GenerationConfig(seed=7),
    )
    first = MockLLMProvider().generate(request)
    second = MockLLMProvider().generate(request)
    assert first == second
    assert first.provider == "mock"
    assert first.model_id == "fixture-v1"


def test_run_id_uniqueness_and_no_overwrite(tmp_path: Path) -> None:
    original = load_config(CONFIG)
    config = original.model_copy(
        update={"experiment": original.experiment.model_copy(update={"output_dir": tmp_path})}
    )
    first = dry_run(config, run_id="fixed-run")
    assert first.is_dir()
    with pytest.raises(ArtifactConflictError):
        dry_run(config, run_id="fixed-run")
    second = dry_run(config)
    assert second.name != "fixed-run"


def test_record_round_trip(tmp_path: Path) -> None:
    original = load_config(CONFIG)
    config = original.model_copy(
        update={"experiment": original.experiment.model_copy(update={"output_dir": tmp_path})}
    )
    run_dir = dry_run(config, run_id="round-trip")
    record = ExperimentRecord.model_validate_json((run_dir / "record.json").read_text())
    assert ExperimentRecord.model_validate_json(record.model_dump_json()) == record
    assert record.status == "completed"


def test_dry_run_persists_complete_artifacts(tmp_path: Path) -> None:
    original = load_config(CONFIG)
    config = original.model_copy(
        update={"experiment": original.experiment.model_copy(update={"output_dir": tmp_path})}
    )
    run_dir = dry_run(config, run_id="smoke")
    assert {p.name for p in run_dir.iterdir()} == {
        "request.json", "response.json", "raw_response.txt", "record.json"
    }
    request = json.loads((run_dir / "request.json").read_text())
    assert request["case"]["case_id"] == "mock-001"


def test_mock_benchmark_exposes_optional_fields() -> None:
    case = next(iter(MockBenchmark().iter_cases()))
    assert case.reference_formulation is None
    assert case.expected_solution is None
    assert case.structured_data is not None


def test_mismatched_returned_model_is_preserved_as_failed_run(tmp_path: Path) -> None:
    class WrongModelProvider(MockLLMProvider):
        def generate(self, request: LLMRequest) -> LLMResponse:
            return super().generate(request).model_copy(update={"model_id": "wrong-model"})

    original = load_config(CONFIG)
    config = original.model_copy(
        update={"experiment": original.experiment.model_copy(update={"output_dir": tmp_path})}
    )
    with pytest.raises(RunFailedError):
        run_case(
            config,
            next(iter(MockBenchmark().iter_cases())),
            WrongModelProvider(),
            run_id="mismatched-model",
        )
    record = json.loads(
        (tmp_path / "foundation-mock" / "runs" / "mismatched-model" / "record.json").read_text()
    )
    assert record["status"] == "failed"
    assert record["error"]["stage"] == "response_identity"
