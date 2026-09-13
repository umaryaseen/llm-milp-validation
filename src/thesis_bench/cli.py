import argparse
import logging
import tomllib
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from thesis_bench.config.loader import load_config
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        config = load_config(args.config)
        if args.command == "validate-config":
            print(f"Valid configuration: {config.experiment.experiment_id}")
        else:
            print(dry_run(config, run_id=args.run_id))
    except (ValidationError, tomllib.TOMLDecodeError, ValueError, OSError,
            ArtifactConflictError, RunFailedError) as exc:
        logger.error("%s", exc)
        return 1
    return 0
