from pathlib import Path

from thesis_bench.benchmarks.base import BenchmarkAdapter
from thesis_bench.datasets.nl4opt import NL4OptAdapter


def get_benchmark(benchmark_id: str, *, root: Path | None = None) -> BenchmarkAdapter:
    """Return the smallest explicit registry for currently supported datasets."""
    if benchmark_id == "nl4opt_generation":
        return NL4OptAdapter.from_manifest(root or Path.cwd())
    raise ValueError(
        f"unsupported benchmark {benchmark_id!r}; supported benchmarks: nl4opt_generation"
    )
