"""Acquire and verify frozen upstream NL4Opt generation data."""

import shutil
import subprocess
import tempfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from thesis_bench.datasets.nl4opt import iter_raw_records
from thesis_bench.datasets.provenance import (
    AcquiredFile,
    DatasetManifest,
    load_manifest,
    manifest_json,
    sha256_file,
    utc_now,
)

OFFICIAL_REPOSITORY_URL = "https://github.com/nl4opt/nl4opt-competition.git"
BENCHMARK_ID = "nl4opt_generation"
SOURCE_ALIAS = "neurips2022-official"
LICENSE_PATH = "LICENSE"
GENERATION_FILES = (
    "generation_data/train.jsonl",
    "generation_data/dev.jsonl",
    "generation_data/test.jsonl",
)
REQUIRED_UPSTREAM_FILES = (LICENSE_PATH, *GENERATION_FILES)


class DatasetIntegrityError(RuntimeError):
    """Frozen data or provenance does not match the recorded source."""


class DatasetPaths:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.manifest = self.root / "data" / "manifests" / f"{BENCHMARK_ID}.json"
        self.raw_base = self.root / "data" / "raw" / BENCHMARK_ID


def _clone_repository(destination: Path) -> str:
    subprocess.run(
        ["git", "clone", "--quiet", OFFICIAL_REPOSITORY_URL, str(destination)],
        check=True,
        capture_output=True,
        text=True,
    )
    result = subprocess.run(
        ["git", "-C", str(destination), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _validate_commit(commit: str) -> str:
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise DatasetIntegrityError(f"upstream returned an invalid full Git commit SHA: {commit!r}")
    return commit


def _split_counts(raw_root: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for split in ("train", "dev", "test"):
        path = raw_root / "generation_data" / f"{split}.jsonl"
        counts[split] = sum(1 for _ in iter_raw_records(path))
    return counts


def _manifest_for_raw(root: Path, commit: str, acquired_at: datetime) -> DatasetManifest:
    raw_root = root / "data" / "raw" / BENCHMARK_ID / commit
    files: list[AcquiredFile] = []
    for relative in REQUIRED_UPSTREAM_FILES:
        path = raw_root / relative
        if not path.is_file():
            raise DatasetIntegrityError(f"required acquired file is missing: {relative}")
        files.append(
            AcquiredFile(
                upstream_relative_path=relative,
                local_raw_path=path.relative_to(root).as_posix(),
                sha256=sha256_file(path),
                byte_size=path.stat().st_size,
            )
        )
    counts = _split_counts(raw_root)
    return DatasetManifest(
        benchmark_id=BENCHMARK_ID,
        source_alias=SOURCE_ALIAS,
        upstream_repository_url=OFFICIAL_REPOSITORY_URL.removesuffix(".git"),
        source_commit_sha=commit,
        acquired_at=acquired_at,
        license_identifier="MIT",
        upstream_license_path=LICENSE_PATH,
        upstream_license_sha256=files[0].sha256,
        raw_data_root=raw_root.relative_to(root).as_posix(),
        files=tuple(files),
        available_splits=("train", "dev", "test"),
        split_counts=counts,
        total_count=sum(counts.values()),
        source_format="JSON Lines; one outer source-ID object per line",
        acquisition_method=(
            "git clone of the official repository followed by byte-preserving copy "
            "of required files"
        ),
        citation={
            "competition": (
                "NL4Opt Competition: Formulating Optimization Problems Based on "
                "Their Natural Language Descriptions"
            ),
            "year": 2022,
            "repository_readme": "https://github.com/nl4opt/nl4opt-competition",
            "generation_baseline": "https://github.com/nl4opt/nl4opt-subtask2-baseline",
        },
    )


def _write_manifest(path: Path, manifest: DatasetManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(manifest_json(manifest), encoding="utf-8")
    temporary.replace(path)


def fetch_dataset(
    *,
    root: Path | None = None,
    update: bool = False,
    clone: Callable[[Path], str] | None = None,
) -> DatasetManifest:
    """Fetch once, or explicitly acquire a new source version with ``update=True``."""
    paths = DatasetPaths(root or Path.cwd())
    if paths.manifest.exists() and not update:
        manifest = verify_dataset(root=paths.root)
        return manifest
    if paths.raw_base.exists() and not paths.manifest.exists():
        raise DatasetIntegrityError(
            f"raw data exists without provenance manifest at {paths.manifest}; refusing replacement"
        )
    with tempfile.TemporaryDirectory(prefix="nl4opt-acquire-") as temporary_name:
        temporary = Path(temporary_name) / "upstream"
        commit = _validate_commit((clone or _clone_repository)(temporary))
        source_files = [temporary / relative for relative in REQUIRED_UPSTREAM_FILES]
        missing = [
            relative
            for relative, path in zip(REQUIRED_UPSTREAM_FILES, source_files, strict=True)
            if not path.is_file()
        ]
        if missing:
            raise DatasetIntegrityError(
                f"official source is missing required files: {', '.join(missing)}"
            )
        destination = paths.raw_base / commit
        if destination.exists():
            raise DatasetIntegrityError(
                f"frozen raw source already exists at {destination}; refusing to overwrite"
            )
        destination.mkdir(parents=True)
        try:
            for relative in REQUIRED_UPSTREAM_FILES:
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(temporary / relative, target)
            manifest = _manifest_for_raw(paths.root, commit, utc_now())
            _write_manifest(paths.manifest, manifest)
        except Exception:
            shutil.rmtree(destination)
            raise
    return verify_dataset(root=paths.root)


def verify_dataset(*, root: Path | None = None) -> DatasetManifest:
    """Verify manifest, byte checksums/sizes, JSONL parseability, schema, and counts."""
    paths = DatasetPaths(root or Path.cwd())
    if not paths.manifest.is_file():
        raise DatasetIntegrityError(f"provenance manifest is missing: {paths.manifest}")
    manifest = load_manifest(paths.manifest)
    if manifest.benchmark_id != BENCHMARK_ID:
        raise DatasetIntegrityError(f"unexpected benchmark ID in manifest: {manifest.benchmark_id}")
    if manifest.source_alias != SOURCE_ALIAS:
        raise DatasetIntegrityError(f"unexpected source alias in manifest: {manifest.source_alias}")
    expected_repository = OFFICIAL_REPOSITORY_URL.removesuffix(".git")
    if manifest.upstream_repository_url != expected_repository:
        raise DatasetIntegrityError(
            "manifest upstream repository is not the official NL4Opt repository"
        )
    manifest_paths = {acquired.upstream_relative_path for acquired in manifest.files}
    missing_required = sorted(set(REQUIRED_UPSTREAM_FILES) - manifest_paths)
    if missing_required:
        raise DatasetIntegrityError(
            f"manifest is missing required upstream files: {', '.join(missing_required)}"
        )
    if manifest.source_commit_sha not in Path(manifest.raw_data_root).parts:
        raise DatasetIntegrityError("manifest raw_data_root does not contain its frozen commit SHA")
    for acquired in manifest.files:
        path = paths.root / acquired.local_raw_path
        if not path.is_file():
            raise DatasetIntegrityError(f"required raw file is missing: {acquired.local_raw_path}")
        actual_size = path.stat().st_size
        actual_hash = sha256_file(path)
        if actual_size != acquired.byte_size:
            raise DatasetIntegrityError(
                f"modified file {acquired.local_raw_path}: expected size "
                f"{acquired.byte_size}, actual {actual_size}"
            )
        if actual_hash != acquired.sha256:
            raise DatasetIntegrityError(
                f"modified file {acquired.local_raw_path}: expected checksum "
                f"{acquired.sha256}, actual {actual_hash}"
            )
    observed: dict[str, int] = {}
    for split in manifest.available_splits:
        jsonl_path = paths.root / manifest.raw_data_root / "generation_data" / f"{split}.jsonl"
        try:
            observed[split] = sum(1 for _ in iter_raw_records(jsonl_path))
        except (OSError, ValueError) as exc:
            raise DatasetIntegrityError(
                f"split {split!r} failed schema verification: {exc}"
            ) from exc
    if observed != manifest.split_counts:
        raise DatasetIntegrityError(
            f"split counts differ from manifest: expected {manifest.split_counts}, "
            f"actual {observed}"
        )
    if sum(observed.values()) != manifest.total_count:
        raise DatasetIntegrityError(
            f"total count differs from manifest: expected {manifest.total_count}, "
            f"actual {sum(observed.values())}"
        )
    return manifest
