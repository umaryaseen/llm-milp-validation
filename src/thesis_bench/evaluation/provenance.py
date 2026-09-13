from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path

from pydantic import Field

from thesis_bench.models import NonEmptyStr, SchemaModel

EVALUATOR_SHA = "18a54bcb2c34be7d034d994c9e065e59cdf1ddfe"
REPOSITORY = "https://github.com/nl4opt/nl4opt-subtask2-baseline.git"
EVALUATOR_ID = "nl4opt_official_evaluator"
SOURCE_ALIAS = "nl4opt-subtask2-official"
FILES = (
    "LICENSE.txt",
    "scoring.py",
    "parsers.py",
    "test_utils.py",
    "parsing_utils/constants.py",
    "utils.py",
    "constants.py",
    "environment.yml",
    "README.md",
)


class EvaluatorFile(SchemaModel):
    upstream_relative_path: NonEmptyStr
    local_raw_path: NonEmptyStr
    sha256: NonEmptyStr
    size_bytes: int = Field(ge=0)


class EvaluatorManifest(SchemaModel):
    evaluator_id: NonEmptyStr
    source_alias: NonEmptyStr
    upstream_repository_url: NonEmptyStr
    source_commit_sha: NonEmptyStr
    license_identifier: NonEmptyStr
    license_file: NonEmptyStr
    license_sha256: NonEmptyStr
    acquired_at: date
    relationship_to_benchmark: NonEmptyStr
    files: tuple[EvaluatorFile, ...]


def manifest_path(root: Path) -> Path:
    return root / "data" / "manifests" / "nl4opt_evaluator.json"


def raw_root(root: Path) -> Path:
    return root / "data" / "raw" / "nl4opt_evaluator" / EVALUATOR_SHA


def vendor_root() -> Path:
    return Path(__file__).parents[1] / "_vendor" / "nl4opt"


def load_manifest(root: Path) -> EvaluatorManifest:
    return EvaluatorManifest.model_validate_json(manifest_path(root).read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_evaluator(root: Path) -> EvaluatorManifest:
    destination = raw_root(root)
    if destination.exists():
        return verify_evaluator(root)
    with tempfile.TemporaryDirectory(prefix="nl4opt-evaluator-") as temp:
        checkout = Path(temp) / "source"
        subprocess.run(["git", "clone", "--quiet", REPOSITORY, str(checkout)], check=True)
        subprocess.run(
            ["git", "-C", str(checkout), "checkout", "--quiet", EVALUATOR_SHA], check=True
        )
        destination.mkdir(parents=True)
        for relative in FILES:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(checkout / relative, target)
    entries = tuple(
        EvaluatorFile(
            upstream_relative_path=relative,
            local_raw_path=str(Path("data/raw/nl4opt_evaluator") / EVALUATOR_SHA / relative),
            sha256=_sha256(destination / relative),
            size_bytes=(destination / relative).stat().st_size,
        )
        for relative in FILES
    )
    manifest = EvaluatorManifest(
        evaluator_id=EVALUATOR_ID,
        source_alias=SOURCE_ALIAS,
        upstream_repository_url=REPOSITORY.removesuffix(".git"),
        source_commit_sha=EVALUATOR_SHA,
        license_identifier="MIT",
        license_file="LICENSE.txt",
        license_sha256=entries[0].sha256,
        acquired_at=date.today(),
        relationship_to_benchmark="nl4opt_generation",
        files=entries,
    )
    manifest_path(root).write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def verify_evaluator(root: Path) -> EvaluatorManifest:
    manifest = load_manifest(root)
    if (
        manifest.evaluator_id != EVALUATOR_ID
        or manifest.source_alias != SOURCE_ALIAS
        or manifest.upstream_repository_url != REPOSITORY.removesuffix(".git")
        or manifest.source_commit_sha != EVALUATOR_SHA
        or manifest.relationship_to_benchmark != "nl4opt_generation"
        or manifest.license_identifier != "MIT"
        or manifest.license_file != "LICENSE.txt"
    ):
        raise ValueError("evaluator manifest points to an unexpected source revision or benchmark")
    license_entry = next(
        (f for f in manifest.files if f.upstream_relative_path == manifest.license_file), None
    )
    if license_entry is None or manifest.license_sha256 != license_entry.sha256:
        raise ValueError("evaluator license checksum does not match its file entry")
    if len(manifest.files) != len(FILES) or {
        f.upstream_relative_path for f in manifest.files
    } != set(FILES):
        raise ValueError("evaluator manifest file inventory is incomplete or unexpected")
    for entry in manifest.files:
        relative = Path(entry.local_raw_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"invalid evaluator local path: {entry.local_raw_path}")
        expected = Path("data/raw/nl4opt_evaluator") / EVALUATOR_SHA / entry.upstream_relative_path
        if relative != expected:
            raise ValueError(f"unexpected evaluator local path: {entry.local_raw_path}")
        path = root / relative
        if not path.is_file():
            raise ValueError(f"missing evaluator source file: {entry.local_raw_path}")
        verify_file(path, entry)
    vendor = vendor_root()
    scoring_hash = next(
        f.sha256 for f in manifest.files if f.upstream_relative_path == "scoring.py"
    )
    if _sha256(vendor / "scoring.py") != scoring_hash:
        raise ValueError("vendored scoring source does not match frozen evaluator")
    parser_hash = next(f.sha256 for f in manifest.files if f.upstream_relative_path == "parsers.py")
    parser_bytes = (vendor / "parsers.py").read_bytes()
    original_import = b"import parsing_utils.constants as const"
    adapted_import = b"from .parsing_utils import constants as const"
    if _sha256(vendor / "parsers.py") != parser_hash and hashlib.sha256(
        parser_bytes.replace(adapted_import, original_import)
    ).hexdigest() != parser_hash:
        raise ValueError("vendored parser source does not match frozen evaluator")
    return manifest


def verify_file(path: Path, entry: EvaluatorFile) -> None:
    """Verify one frozen evaluator file for offline integrity checks."""
    if path.stat().st_size != entry.size_bytes or _sha256(path) != entry.sha256:
        raise ValueError(f"evaluator source integrity mismatch: {entry.upstream_relative_path}")
