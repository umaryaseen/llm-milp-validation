"""Pydantic schemas and checksums for frozen benchmark sources."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, Field, JsonValue, field_validator

from thesis_bench.models import NonEmptyStr, SchemaModel

SHA256_PATTERN = r"^[0-9a-f]{64}$"
COMMIT_PATTERN = r"^[0-9a-f]{40}$"


class AcquiredFile(SchemaModel):
    upstream_relative_path: NonEmptyStr
    local_raw_path: NonEmptyStr
    sha256: str = Field(pattern=SHA256_PATTERN)
    byte_size: int = Field(ge=0, strict=True)

    @field_validator("upstream_relative_path", "local_raw_path")
    @classmethod
    def relative_path(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        if Path(normalized).is_absolute() or ".." in Path(normalized).parts:
            raise ValueError("manifest paths must be relative and stay within the project")
        return normalized


class DatasetManifest(SchemaModel):
    manifest_version: Literal["1"] = "1"
    benchmark_id: NonEmptyStr
    source_alias: NonEmptyStr
    upstream_repository_url: NonEmptyStr
    source_commit_sha: str = Field(pattern=COMMIT_PATTERN)
    acquired_at: AwareDatetime
    license_identifier: NonEmptyStr | None = None
    upstream_license_path: NonEmptyStr | None = None
    upstream_license_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    raw_data_root: NonEmptyStr
    files: tuple[AcquiredFile, ...] = Field(min_length=1)
    available_splits: tuple[NonEmptyStr, ...] = ()
    split_counts: dict[NonEmptyStr, int] = Field(default_factory=dict)
    total_count: int = Field(ge=0, strict=True)
    source_format: NonEmptyStr
    acquisition_method: NonEmptyStr
    citation: dict[str, JsonValue] = Field(default_factory=dict)
    upstream_ref: str | None = None

    @field_validator("raw_data_root", "upstream_license_path")
    @classmethod
    def relative_root(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.replace("\\", "/")
        if Path(normalized).is_absolute() or ".." in Path(normalized).parts:
            raise ValueError("manifest paths must be relative")
        return normalized


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> DatasetManifest:
    return DatasetManifest.model_validate_json(path.read_text(encoding="utf-8"))


def manifest_json(manifest: DatasetManifest) -> str:
    """Stable JSON for reviewable provenance diffs and deterministic fixture tests."""
    return json.dumps(
        manifest.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def utc_now() -> datetime:
    return datetime.now(UTC)
