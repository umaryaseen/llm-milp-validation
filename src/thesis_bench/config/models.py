from pathlib import Path
from typing import Literal

from pydantic import Field, JsonValue

from thesis_bench.models import FileID, NonEmptyStr, SchemaModel
from thesis_bench.prompts.protocol import PromptProtocol
from thesis_bench.providers.base import GenerationConfig


class BenchmarkConfig(SchemaModel):
    id: NonEmptyStr
    version: NonEmptyStr
    split: NonEmptyStr | None = None
    options: dict[str, JsonValue] = Field(default_factory=dict)


class ModelConfig(SchemaModel):
    provider: NonEmptyStr
    model_id: NonEmptyStr
    api_key_env: str | None = Field(default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    generation: GenerationConfig = Field(default_factory=GenerationConfig)


class ExperimentConfig(SchemaModel):
    experiment_id: FileID
    output_dir: Path
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class RunConfig(SchemaModel):
    schema_version: Literal["1"] = "1"
    experiment: ExperimentConfig
    benchmark: BenchmarkConfig
    model: ModelConfig
    prompt: PromptProtocol
