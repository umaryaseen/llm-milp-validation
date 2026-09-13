from typing import Literal, Protocol

from pydantic import Field, JsonValue

from thesis_bench.models import NonEmptyStr, SchemaModel


class Message(SchemaModel):
    role: Literal["system", "user", "assistant"]
    content: str


class GenerationConfig(SchemaModel):
    temperature: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    top_p: float | None = Field(default=None, gt=0, le=1, allow_inf_nan=False)
    max_output_tokens: int | None = Field(default=None, gt=0, strict=True)
    seed: int | None = Field(default=None, ge=0, strict=True)
    stop: tuple[NonEmptyStr, ...] = ()


class LLMRequest(SchemaModel):
    model_id: NonEmptyStr
    messages: tuple[Message, ...] = Field(min_length=1)
    generation: GenerationConfig


class TokenUsage(SchemaModel):
    input_tokens: int | None = Field(default=None, ge=0, strict=True)
    output_tokens: int | None = Field(default=None, ge=0, strict=True)
    total_tokens: int | None = Field(default=None, ge=0, strict=True)


class Cost(SchemaModel):
    amount: float = Field(ge=0, allow_inf_nan=False)
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class LLMResponse(SchemaModel):
    raw_text: str
    provider: NonEmptyStr
    model_id: NonEmptyStr
    latency_seconds: float = Field(ge=0, allow_inf_nan=False)
    token_usage: TokenUsage | None = None
    cost: Cost | None = None
    raw_metadata: dict[str, JsonValue] = Field(default_factory=dict)

class LLMProvider(Protocol):
    @property
    def name(self) -> str: ...

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Make exactly one attempt; propagate failures without hidden retries."""
        ...
