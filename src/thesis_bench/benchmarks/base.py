from collections.abc import Iterable
from typing import Protocol

from pydantic import Field, JsonValue

from thesis_bench.models import NonEmptyStr, SchemaModel


class BenchmarkCase(SchemaModel):
    benchmark_id: NonEmptyStr
    benchmark_version: NonEmptyStr
    case_id: NonEmptyStr
    description: NonEmptyStr
    split: NonEmptyStr | None = None
    structured_data: JsonValue = None
    reference_formulation: JsonValue = None
    expected_solution: JsonValue = None
    expected_objective: float | None = Field(default=None, allow_inf_nan=False)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class BenchmarkAdapter(Protocol):
    @property
    def benchmark_id(self) -> str: ...

    @property
    def benchmark_version(self) -> str: ...

    @property
    def split(self) -> str | None: ...

    def iter_cases(self) -> Iterable[BenchmarkCase]: ...
