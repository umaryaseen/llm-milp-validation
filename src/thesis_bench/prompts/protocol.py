from string import Template

from pydantic import Field, JsonValue, field_validator

from thesis_bench.benchmarks.base import BenchmarkCase
from thesis_bench.models import NonEmptyStr, SchemaModel
from thesis_bench.providers.base import Message


class PromptProtocol(SchemaModel):
    name: NonEmptyStr
    version: NonEmptyStr
    template: NonEmptyStr
    condition: NonEmptyStr
    condition_metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("template")
    @classmethod
    def validate_template(cls, value: str) -> str:
        template = Template(value)
        if not template.is_valid() or set(template.get_identifiers()) != {"description"}:
            raise ValueError(
                "template must use ${description} and no other placeholders; use $$ for $")
        return value

    def render(self, case: BenchmarkCase) -> tuple[Message, ...]:
        """Substitute once, without trimming, repairing, or exposing reference labels."""
        return (Message(role="user", content=Template(self.template).substitute(
            description=case.description
        )),)
