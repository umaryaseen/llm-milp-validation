"""Publish complete files without ever replacing an existing destination."""

import os
import tempfile
from pathlib import Path

from pydantic import BaseModel, TypeAdapter

from thesis_bench.config.models import RunConfig
from thesis_bench.models import FileID


class ArtifactConflictError(RuntimeError):
    """An experiment config or run directory already exists with conflicting state."""


def write_text_new(path: Path, text: str) -> None:
    """Atomically link a fully written file into place; os.link cannot overwrite."""
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_model_new(path: Path, model: BaseModel) -> None:
    write_text_new(path, model.model_dump_json(indent=2) + "\n")


class ArtifactStore:
    def reserve_run(self, config: RunConfig, run_id: str) -> Path:
        """Reserve before generation; failed and incomplete runs are also protected."""
        run_id = TypeAdapter(FileID).validate_python(run_id)
        experiment_dir = config.experiment.output_dir / config.experiment.experiment_id
        experiment_dir.mkdir(parents=True, exist_ok=True)
        config_path = experiment_dir / "config.json"
        snapshot = config.model_dump_json(indent=2) + "\n"
        try:
            write_text_new(config_path, snapshot)
        except FileExistsError:
            if config_path.read_text(encoding="utf-8") != snapshot:
                raise ArtifactConflictError(
                    f"Experiment configuration differs at {config_path}; use a new experiment_id"
                ) from None
        runs_dir = experiment_dir / "runs"
        runs_dir.mkdir(exist_ok=True)
        run_dir = runs_dir / run_id
        try:
            run_dir.mkdir()
        except FileExistsError:
            raise ArtifactConflictError(
                f"Run already exists at {run_dir}; refusing to overwrite. Use a new run_id"
            ) from None
        return run_dir
