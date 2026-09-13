from collections.abc import Iterable

from thesis_bench.benchmarks.base import BenchmarkCase


class MockBenchmark:
    """One synthetic case; never represents a downloaded benchmark."""

    benchmark_id = "mock"
    benchmark_version = "1"
    split = "test"

    def iter_cases(self) -> Iterable[BenchmarkCase]:
        yield BenchmarkCase(
            benchmark_id=self.benchmark_id,
            benchmark_version=self.benchmark_version,
            split=self.split,
            case_id="mock-001",
            description=(
                "A workshop makes chairs. Each chair uses 2 units of wood and earns "
                "3 units of profit. At most 10 units of wood are available. Choose a "
                "nonnegative integer number of chairs to maximize profit."
            ),
            structured_data={"wood_per_chair": 2, "profit_per_chair": 3, "wood_available": 10},
            metadata={"synthetic": True, "purpose": "framework smoke test"},
        )
