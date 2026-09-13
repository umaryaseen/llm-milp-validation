import json
import shutil
from pathlib import Path

import pytest

from thesis_bench.cli import main
from thesis_bench.datasets.acquisition import DatasetIntegrityError, fetch_dataset, verify_dataset
from thesis_bench.datasets.nl4opt import DatasetSchemaError, NL4OptAdapter, iter_raw_records
from thesis_bench.datasets.provenance import DatasetManifest, manifest_json

FIXTURE = Path(__file__).parent / "fixtures" / "nl4opt_source"
FROZEN_SHA = "a" * 40


def acquire_fixture(root: Path, calls: list[int] | None = None) -> DatasetManifest:
    def clone(destination: Path) -> str:
        if calls is not None:
            calls.append(1)
        shutil.copytree(FIXTURE, destination)
        return FROZEN_SHA

    return fetch_dataset(root=root, clone=clone)


def test_fixture_acquisition_writes_manifest_and_adapter_cases(tmp_path: Path) -> None:
    manifest = acquire_fixture(tmp_path)
    assert manifest.source_commit_sha == FROZEN_SHA
    assert manifest.available_splits == ("train", "dev", "test")
    assert manifest.split_counts == {"train": 1, "dev": 1, "test": 1}
    assert manifest.total_count == 3
    serialized = manifest_json(manifest)
    assert serialized == manifest_json(type(manifest).model_validate_json(serialized))

    adapter = NL4OptAdapter.from_manifest(tmp_path)
    cases = list(adapter.iter_cases())
    assert [case.case_id for case in cases] == [
        "train-source-001",
        "dev-source-001",
        "test-source-001",
    ]
    assert len({case.case_id for case in cases}) == len(cases)
    assert {case.benchmark_version for case in cases} == {FROZEN_SHA}
    assert cases[0].reference_objective == {
        "type": "objective",
        "direction": "maximize",
        "name": "profit",
        "terms": {"x": "2"},
    }
    assert cases[0].raw_record is not None
    assert cases[0].raw_record["document"] == "Train fixture problem."


def test_split_attribution_and_unsupported_split(tmp_path: Path) -> None:
    acquire_fixture(tmp_path)
    adapter = NL4OptAdapter.from_manifest(tmp_path)
    assert [case.split for case in adapter.iter_cases(split="test")] == ["test"]
    with pytest.raises(ValueError, match="supported splits: train, dev, test"):
        list(adapter.iter_cases(split="validation"))


def test_raw_record_is_preserved_and_repeated_loads_are_stable(tmp_path: Path) -> None:
    acquire_fixture(tmp_path)
    adapter = NL4OptAdapter.from_manifest(tmp_path)
    first = [case.model_dump(mode="json") for case in adapter.iter_cases()]
    second = [case.model_dump(mode="json") for case in adapter.iter_cases()]
    assert first == second
    raw_path = (
        tmp_path
        / "data/raw/nl4opt_generation"
        / FROZEN_SHA
        / "generation_data/train.jsonl"
    )
    raw_line = raw_path.read_text()
    outer = json.loads(raw_line)
    case = first[0]
    assert case["source_id"] in outer
    assert case["raw_record"] == outer[case["source_id"]]


def test_malformed_record_is_surfaced(tmp_path: Path) -> None:
    path = tmp_path / "malformed.jsonl"
    path.write_text('{"bad": 1, "second": 2}\n', encoding="utf-8")
    try:
        with pytest.raises(DatasetSchemaError, match="exactly one source ID"):
            list(iter_raw_records(path))
    finally:
        path.unlink(missing_ok=True)


def test_checksum_tamper_and_missing_file_fail_loudly(tmp_path: Path) -> None:
    acquire_fixture(tmp_path)
    raw_file = tmp_path / "data/raw/nl4opt_generation" / FROZEN_SHA / "generation_data/train.jsonl"
    raw_file.write_bytes(raw_file.read_bytes().replace(b"Train fixture", b"train fixture", 1))
    with pytest.raises(DatasetIntegrityError, match="expected checksum"):
        verify_dataset(root=tmp_path)
    with pytest.raises(DatasetIntegrityError, match="expected checksum"):
        NL4OptAdapter.from_manifest(tmp_path)

    raw_file.write_text((FIXTURE / "generation_data/train.jsonl").read_text(), encoding="utf-8")
    raw_file.unlink()
    with pytest.raises(DatasetIntegrityError, match="required raw file is missing"):
        verify_dataset(root=tmp_path)


def test_fetch_is_idempotent_when_existing_source_is_valid(tmp_path: Path) -> None:
    calls: list[int] = []
    first = acquire_fixture(tmp_path, calls)
    second = fetch_dataset(root=tmp_path, clone=lambda _: pytest.fail("must not clone"))
    assert first == second
    assert len(calls) == 1


def test_malformed_acquisition_bytes_are_retained(tmp_path: Path) -> None:
    def clone(destination: Path) -> str:
        shutil.copytree(FIXTURE, destination)
        train = destination / "generation_data" / "train.jsonl"
        train.write_text(train.read_text() + '{"malformed": true, "extra": true}\n')
        return FROZEN_SHA

    with pytest.raises(DatasetSchemaError):
        fetch_dataset(root=tmp_path, clone=clone)
    assert (
        tmp_path
        / "data/raw/nl4opt_generation"
        / FROZEN_SHA
        / "generation_data/train.jsonl"
    ).is_file()


def test_info_command_works_for_local_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    acquire_fixture(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert main(["datasets", "info", "nl4opt"]) == 0
    output = capsys.readouterr().out
    assert '"frozen_git_sha": "' + FROZEN_SHA + '"' in output
    assert '"integrity": "verified"' in output
