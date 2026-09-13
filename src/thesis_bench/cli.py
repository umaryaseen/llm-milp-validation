import argparse
import json
import logging
import subprocess
import tomllib
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from thesis_bench.config.loader import load_config
from thesis_bench.datasets.acquisition import (
    DatasetIntegrityError,
    DatasetPaths,
    fetch_dataset,
    verify_dataset,
)
from thesis_bench.datasets.registry import get_benchmark
from thesis_bench.experiments.runner import RunFailedError, dry_run
from thesis_bench.experiments.storage import ArtifactConflictError

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reproducible optimization-modeling experiments")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate-config", help="Validate a TOML experiment config")
    validate.add_argument("config", type=Path)
    run = subparsers.add_parser(
        "dry-run", help="Persist one synthetic case using the mock provider"
    )
    run.add_argument("config", type=Path)
    run.add_argument("--run-id", help="Explicit immutable run ID; otherwise generate a UUID4")
    datasets = subparsers.add_parser(
        "datasets", help="Acquire and inspect frozen benchmark sources"
    )
    dataset_commands = datasets.add_subparsers(dest="dataset_command", required=True)
    for command, help_text in (
        ("fetch", "Acquire or verify a frozen benchmark source"),
        ("verify", "Verify a frozen benchmark source"),
        ("info", "Show benchmark provenance and counts"),
    ):
        command_parser = dataset_commands.add_parser(command, help=help_text)
        command_parser.add_argument("benchmark", choices=("nl4opt",))
    dataset_commands.choices["fetch"].add_argument(
        "--update", action="store_true", help="Explicitly acquire a new upstream source version"
    )
    sample = dataset_commands.add_parser("sample", help="Show concise normalized benchmark cases")
    sample.add_argument("benchmark", choices=("nl4opt",))
    sample.add_argument("--split", required=True)
    sample.add_argument("--count", type=int, default=1)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        if args.command in {"validate-config", "dry-run"}:
            config = load_config(args.config)
        if args.command == "validate-config":
            print(f"Valid configuration: {config.experiment.experiment_id}")
        elif args.command == "dry-run":
            print(dry_run(config, run_id=args.run_id))
        else:
            return _datasets_command(args)
    except (
        ValidationError,
        tomllib.TOMLDecodeError,
        ValueError,
        OSError,
        subprocess.SubprocessError,
        ArtifactConflictError,
        DatasetIntegrityError,
        RunFailedError,
    ) as exc:
        logger.error("%s", exc)
        return 1
    return 0


def _datasets_command(args: argparse.Namespace) -> int:
    root = Path.cwd()
    if args.benchmark != "nl4opt":
        raise ValueError(f"unsupported benchmark {args.benchmark!r}")
    if args.dataset_command == "fetch":
        manifest = fetch_dataset(root=root, update=args.update)
        print(
            f"Frozen {manifest.benchmark_id} at {manifest.source_commit_sha}; "
            f"{manifest.total_count} records; manifest {DatasetPaths(root).manifest}"
        )
    elif args.dataset_command == "verify":
        manifest = verify_dataset(root=root)
        print(f"Integrity verified: {manifest.benchmark_id} ({manifest.total_count} records)")
    elif args.dataset_command == "info":
        manifest = verify_dataset(root=root)
        print(json.dumps({
            "benchmark_id": manifest.benchmark_id,
            "source_alias": manifest.source_alias,
            "source_repository": manifest.upstream_repository_url,
            "frozen_git_sha": manifest.source_commit_sha,
            "license": manifest.license_identifier,
            "splits": manifest.available_splits,
            "counts": manifest.split_counts,
            "total": manifest.total_count,
            "manifest": str(DatasetPaths(root).manifest),
            "raw_data_root": str(root / manifest.raw_data_root),
            "integrity": "verified",
        }, indent=2))
    else:
        if args.count < 1:
            raise ValueError("sample count must be positive")
        adapter = get_benchmark("nl4opt_generation", root=root)
        cases = list(adapter.iter_cases(split=args.split))[: args.count]
        print(json.dumps([
            {
                "case_id": case.case_id,
                "split": case.split,
                "description": case.description,
                "reference_objective": case.reference_objective,
                "reference_constraints": case.reference_constraints,
            }
            for case in cases
        ], indent=2, ensure_ascii=False))
    return 0
