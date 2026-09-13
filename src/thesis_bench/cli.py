import argparse
import json
import logging
import subprocess
import tomllib
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from thesis_bench.benchmarks.base import BenchmarkCase
from thesis_bench.config.loader import load_config
from thesis_bench.datasets.acquisition import (
    DatasetIntegrityError,
    DatasetPaths,
    fetch_dataset,
    verify_dataset,
)
from thesis_bench.datasets.registry import get_benchmark
from thesis_bench.evaluation.characterize import gold_check, write_characterization
from thesis_bench.evaluation.provenance import fetch_evaluator, verify_evaluator
from thesis_bench.experiments.lm4opt import run_lm4opt_mock
from thesis_bench.experiments.runner import RunFailedError, dry_run
from thesis_bench.experiments.storage import ArtifactConflictError
from thesis_bench.prompts.lm4opt import get_lm4opt_protocol, protocol_names

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
    evaluators = subparsers.add_parser("evaluators", help="Inspect the pinned official evaluators")
    evaluator_commands = evaluators.add_subparsers(dest="evaluator_command", required=True)
    for command, help_text in (
        ("fetch", "Acquire pinned evaluator source"),
        ("verify", "Verify pinned evaluator source"),
        ("info", "Show evaluator provenance"),
        ("characterize", "Write offline evaluator characterization"),
    ):
        command_parser = evaluator_commands.add_parser(command, help=help_text)
        command_parser.add_argument("evaluator", choices=("nl4opt",))
    evaluator_commands.add_parser("gold-check", help="Check all frozen gold records").add_argument(
        "evaluator", choices=("nl4opt",)
    )
    prompts = subparsers.add_parser(
        "prompts", help="Inspect frozen paper-reproduced prompt protocols"
    )
    prompt_commands = prompts.add_subparsers(dest="prompt_command", required=True)
    render = prompt_commands.add_parser("render", help="Render one protocol for an NL4Opt case")
    render.add_argument("protocol", choices=protocol_names())
    render.add_argument("--case-id", required=True)
    render.add_argument("--split", required=True)
    render.add_argument("--show", action="store_true")
    info = prompt_commands.add_parser("info", help="Show protocol provenance")
    info.add_argument("protocol", choices=protocol_names())
    mock = subparsers.add_parser("lm4opt-dry-run", help="Run one offline LM4OPT fixture end to end")
    mock.add_argument("protocol", choices=protocol_names())
    mock.add_argument("--case-id", required=True)
    mock.add_argument("--split", required=True)
    mock.add_argument("--response-file", type=Path, required=True)
    mock.add_argument("--run-id", required=True)
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
        elif args.command == "prompts":
            return _prompts_command(args)
        elif args.command == "lm4opt-dry-run":
            return _lm4opt_dry_run_command(args)
        else:
            if args.command == "datasets":
                return _datasets_command(args)
            return _evaluators_command(args)
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


def _evaluators_command(args: argparse.Namespace) -> int:
    root = Path.cwd()
    if args.evaluator != "nl4opt":
        raise ValueError(f"unsupported evaluator {args.evaluator!r}")
    if args.evaluator_command == "fetch":
        manifest = fetch_evaluator(root)
        print(
            f"Frozen evaluator at {manifest.source_commit_sha}; "
            "manifest data/manifests/nl4opt_evaluator.json"
        )
    elif args.evaluator_command == "verify":
        manifest = verify_evaluator(root)
        print(f"Integrity verified: {manifest.evaluator_id} ({manifest.source_commit_sha})")
    elif args.evaluator_command == "info":
        print(json.dumps(verify_evaluator(root).model_dump(mode="json"), indent=2))
    elif args.evaluator_command == "characterize":
        print(write_characterization(root))
    else:
        report = gold_check(root)
        path = root / "results" / "nl4opt" / "gold_check.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
    return 0


def _find_nl4opt_case(root: Path, split: str, case_id: str) -> BenchmarkCase:
    adapter = get_benchmark("nl4opt_generation", root=root)
    for case in adapter.iter_cases(split=split):
        if case.case_id == case_id:
            return case
    raise ValueError(f"NL4Opt case not found: {split}/{case_id}")


def _prompts_command(args: argparse.Namespace) -> int:
    protocol = get_lm4opt_protocol(args.protocol)
    if args.prompt_command == "info":
        print(json.dumps({
            "protocol": protocol.name,
            "version": protocol.version,
            "template_sha256": protocol.template_sha256,
            "condition": protocol.condition,
            "source_status": protocol.source_status,
            "input_view": protocol.input_view,
            "demonstration_included": protocol.demonstration_included,
            "source_paper": "Ahmed and Choudhury (2024), arXiv:2403.01342, Figure 2",
        }, indent=2))
        return 0
    case = _find_nl4opt_case(Path.cwd(), args.split, args.case_id)
    result = {
        "protocol": protocol.name,
        "version": protocol.version,
        "case_id": case.case_id,
        "template_sha256": protocol.template_sha256,
        "rendered_prompt_sha256": protocol.rendered_prompt_sha256(case),
    }
    if args.show:
        result["prompt"] = protocol.render(case)[0].content
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _lm4opt_dry_run_command(args: argparse.Namespace) -> int:
    case = _find_nl4opt_case(Path.cwd(), args.split, args.case_id)
    raw_response = args.response_file.read_text(encoding="utf-8")
    print(run_lm4opt_mock(Path.cwd(), case, args.protocol, raw_response, run_id=args.run_id))
    return 0
