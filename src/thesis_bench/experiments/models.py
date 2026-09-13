from typing import Literal
from uuid import uuid4

from pydantic import AwareDatetime, Field, JsonValue, model_validator

from thesis_bench.benchmarks.base import BenchmarkCase
from thesis_bench.models import FileID, NonEmptyStr, SchemaModel
from thesis_bench.prompts.protocol import PromptProtocol
from thesis_bench.providers.base import Cost, GenerationConfig, LLMRequest, TokenUsage


def new_run_id() -> str:
    return str(uuid4())


class ErrorInfo(SchemaModel):
    type: NonEmptyStr
    message: str
    stage: NonEmptyStr
    traceback: str


class ExperimentRequest(SchemaModel):
    schema_version: Literal["1"] = "1"
    experiment_id: FileID
    run_id: FileID
    timestamp: AwareDatetime
    provider: NonEmptyStr
    case: BenchmarkCase
    prompt: PromptProtocol
    request: LLMRequest


class ExperimentRecord(SchemaModel):
    schema_version: Literal["1"] = "1"
    experiment_id: FileID
    run_id: FileID
    benchmark: NonEmptyStr
    benchmark_version: NonEmptyStr
    case_id: NonEmptyStr
    split: NonEmptyStr | None = None
    provider: NonEmptyStr
    model_id: NonEmptyStr
    prompt_protocol: NonEmptyStr
    prompt_version: NonEmptyStr
    prompt_condition: NonEmptyStr
    generation: GenerationConfig
    timestamp: AwareDatetime
    finished_at: AwareDatetime
    request_path: str = "request.json"
    response_path: str | None = None
    raw_response_path: str | None = None
    parsed_response_path: str | None = None
    evaluation_result_path: str | None = None
    latency_seconds: float = Field(ge=0, allow_inf_nan=False)
    token_usage: TokenUsage | None = None
    cost: Cost | None = None
    status: Literal["completed", "failed"]
    error: ErrorInfo | None = None
    metrics: dict[str, JsonValue] = Field(default_factory=dict)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_outcome(self) -> "ExperimentRecord":
        if self.finished_at < self.timestamp:
            raise ValueError("finished_at must not precede timestamp")
        if self.status == "failed" and self.error is None:
            raise ValueError("failed records require error information")
        if self.status == "completed":
            if self.error is not None:
                raise ValueError("completed records cannot contain an error")
            if self.response_path is None or self.raw_response_path is None:
                raise ValueError("completed records require normalized and raw response paths")
        return self
