import logging
import platform
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

from thesis_bench import __version__
from thesis_bench.benchmarks.base import BenchmarkCase
from thesis_bench.benchmarks.mock import MockBenchmark
from thesis_bench.config.models import RunConfig
from thesis_bench.experiments.models import (
    ErrorInfo,
    ExperimentRecord,
    ExperimentRequest,
    new_run_id,
)
from thesis_bench.experiments.storage import ArtifactStore, write_model_new, write_text_new
from thesis_bench.providers.base import LLMProvider, LLMRequest, LLMResponse
from thesis_bench.providers.mock import MockLLMProvider

logger = logging.getLogger(__name__)


class RunFailedError(RuntimeError):
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        super().__init__(f"Run failed; observation preserved at {run_dir / 'record.json'}")


def run_case(
    config: RunConfig,
    case: BenchmarkCase,
    provider: LLMProvider,
    *,
    run_id: str | None = None,
) -> Path:
    """Execute exactly one provider call and retain every returned string unchanged."""
    if (case.benchmark_id, case.benchmark_version, case.split) != (
        config.benchmark.id, config.benchmark.version, config.benchmark.split
    ):
        raise ValueError("case provenance does not match benchmark configuration")
    if provider.name != config.model.provider:
        raise ValueError("provider identity does not match model configuration")

    run_id = new_run_id() if run_id is None else run_id
    started_at = datetime.now(UTC)
    request = ExperimentRequest(
        experiment_id=config.experiment.experiment_id,
        run_id=run_id,
        timestamp=started_at,
        provider=provider.name,
        case=case,
        prompt=config.prompt,
        request=LLMRequest(
            model_id=config.model.model_id,
            messages=config.prompt.render(case),
            generation=config.model.generation,
        ),
    )
    run_dir = ArtifactStore().reserve_run(config, run_id)
    write_model_new(run_dir / "request.json", request)
    logger.info("Starting run %s/%s", config.experiment.experiment_id, run_id)
    response: LLMResponse | None = None
    error: ErrorInfo | None = None
    raw_response_path: str | None = None
    response_path: str | None = None
    stage = "generation"
    start = time.perf_counter()
    try:
        response = provider.generate(request.request)
        stage = "response_persistence"
        write_text_new(run_dir / "raw_response.txt", response.raw_text)
        raw_response_path = "raw_response.txt"
        write_model_new(run_dir / "response.json", response)
        response_path = "response.json"
        stage = "response_identity"
        if response.provider != provider.name:
            raise ValueError("returned provider identity does not match the requested provider")
        if response.model_id != request.request.model_id:
            raise ValueError("returned model identity does not match the requested model")
    except Exception as exc:
        error = ErrorInfo(
            type=type(exc).__name__, message=str(exc), stage=stage, traceback=traceback.format_exc()
        )
    elapsed = time.perf_counter() - start
    record = ExperimentRecord(
        experiment_id=config.experiment.experiment_id,
        run_id=run_id,
        benchmark=case.benchmark_id,
        benchmark_version=case.benchmark_version,
        case_id=case.case_id,
        split=case.split,
        provider=response.provider if response is not None else provider.name,
        model_id=response.model_id if response is not None else config.model.model_id,
        prompt_protocol=config.prompt.name,
        prompt_version=config.prompt.version,
        prompt_condition=config.prompt.condition,
        generation=config.model.generation,
        timestamp=started_at,
        finished_at=datetime.now(UTC),
        response_path=response_path,
        raw_response_path=raw_response_path,
        latency_seconds=response.latency_seconds if response is not None else elapsed,
        token_usage=response.token_usage if response is not None else None,
        cost=response.cost if response is not None else None,
        status="failed" if error is not None else "completed",
        error=error,
        metadata={
            "framework_version": __version__,
            "python_version": platform.python_version(),
            "experiment": config.experiment.metadata,
            "benchmark": case.metadata,
        },
    )
    # Final marker is written only once, after all available observations.
    write_model_new(run_dir / "record.json", record)
    if error is not None:
        logger.error("Run %s failed during %s; see %s", run_id, error.stage, run_dir)
        raise RunFailedError(run_dir)
    logger.info("Completed run %s; artifacts at %s", run_id, run_dir)
    return run_dir


def dry_run(config: RunConfig, *, run_id: str | None = None) -> Path:
    """Only synthetic data and the deterministic provider are executable today."""
    benchmark = MockBenchmark()
    if config.model.provider != MockLLMProvider.name:
        raise ValueError(
            "dry-run requires model.provider = 'mock'; real providers are not integrated"
        )
    if (config.benchmark.id, config.benchmark.version, config.benchmark.split) != (
        benchmark.benchmark_id, benchmark.benchmark_version, benchmark.split
    ) or config.benchmark.options:
        raise ValueError("dry-run requires benchmark mock/version 1/split test with no options")
    return run_case(config, next(iter(benchmark.iter_cases())), MockLLMProvider(), run_id=run_id)
