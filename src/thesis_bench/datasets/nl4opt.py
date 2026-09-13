"""Faithful access to the official NL4Opt generation JSONL source."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from thesis_bench.benchmarks.base import BenchmarkCase
from thesis_bench.datasets.provenance import DatasetManifest, load_manifest

REQUIRED_RECORD_FIELDS = frozenset(
    {
        "document",
        "vars",
        "var_mentions",
        "var_mention_to_first_var",
        "first_var_to_mentions",
        "params",
        "obj_declaration",
        "const_declarations",
        "spans",
        "tokens",
        "_input_hash",
        "order_mapping",
    }
)


class DatasetSchemaError(ValueError):
    """A source record cannot be represented without losing required information."""


def iter_raw_records(path: Path) -> Iterator[tuple[str, dict[str, Any], int]]:
    with path.open(encoding="utf-8", newline="") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                outer = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DatasetSchemaError(
                    f"{path}: line {line_number} is not valid JSON: {exc}"
                ) from exc
            if not isinstance(outer, dict) or len(outer) != 1:
                raise DatasetSchemaError(
                    f"{path}: line {line_number} must be an object with exactly one source ID"
                )
            source_id, record = next(iter(outer.items()))
            if not isinstance(source_id, str) or not source_id:
                raise DatasetSchemaError(f"{path}: line {line_number} has an invalid source ID")
            if not isinstance(record, dict):
                raise DatasetSchemaError(f"{path}: line {line_number} record is not an object")
            missing = REQUIRED_RECORD_FIELDS - record.keys()
            if missing:
                missing_names = ", ".join(sorted(missing))
                raise DatasetSchemaError(
                    f"{path}: line {line_number} missing fields: {missing_names}"
                )
            if not isinstance(record["document"], str):
                raise DatasetSchemaError(f"{path}: line {line_number} document is not a string")
            yield source_id, record, line_number


class NL4OptAdapter:
    """Adapter that normalizes access while retaining the complete raw record."""

    benchmark_id = "nl4opt_generation"
    source_alias = "neurips2022-official"

    def __init__(self, root: Path, manifest: DatasetManifest) -> None:
        self.root = root.resolve()
        self.manifest = manifest

    @classmethod
    def from_manifest(cls, root: Path) -> "NL4OptAdapter":
        manifest_path = root / "data" / "manifests" / "nl4opt_generation.json"
        return cls(root, load_manifest(manifest_path))

    @property
    def benchmark_version(self) -> str:
        return self.manifest.source_commit_sha

    @property
    def split(self) -> str | None:
        return None

    @property
    def supported_splits(self) -> tuple[str, ...]:
        return self.manifest.available_splits

    def _file_for_split(self, split: str) -> Path:
        if split not in self.supported_splits:
            supported = ", ".join(self.supported_splits)
            raise ValueError(f"unsupported split {split!r}; supported splits: {supported}")
        for acquired in self.manifest.files:
            if acquired.upstream_relative_path == f"generation_data/{split}.jsonl":
                return self.root / acquired.local_raw_path
        raise DatasetSchemaError(f"manifest has no raw JSONL file for split {split!r}")

    def iter_cases(self, split: str | None = None) -> Iterator[BenchmarkCase]:
        splits = (split,) if split is not None else self.supported_splits
        seen_ids: set[str] = set()
        for selected_split in splits:
            path = self._file_for_split(selected_split)
            for source_id, record, line_number in iter_raw_records(path):
                if source_id in seen_ids:
                    raise DatasetSchemaError(f"duplicate source ID {source_id!r} in {path}")
                seen_ids.add(source_id)
                yield BenchmarkCase(
                    benchmark_id=self.benchmark_id,
                    benchmark_version=self.benchmark_version,
                    split=selected_split,
                    case_id=source_id,
                    description=record["document"],
                    reference_objective=record["obj_declaration"],
                    reference_constraints=record["const_declarations"],
                    named_entities={"spans": record["spans"], "tokens": record["tokens"]},
                    source_id=source_id,
                    raw_record=record,
                    metadata={
                        "upstream_relative_path": f"generation_data/{selected_split}.jsonl",
                        "source_index": line_number,
                        "input_hash": record["_input_hash"],
                    },
                )
