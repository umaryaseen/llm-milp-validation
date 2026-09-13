"""Paper-reproduced LM4OPT prompt protocols and input policy."""

from __future__ import annotations

import hashlib
from importlib.resources import files
from pathlib import Path
from string import Template
from typing import Literal

from pydantic import JsonValue

from thesis_bench.benchmarks.base import BenchmarkCase
from thesis_bench.models import NonEmptyStr, SchemaModel
from thesis_bench.prompts.protocol import PromptProtocol
from thesis_bench.providers.base import Message

PROTOCOL_ZERO_SHOT = "nl4opt_lm4opt_zero_shot"
PROTOCOL_ONE_SHOT = "nl4opt_lm4opt_one_shot"
PROTOCOL_VERSION = "1"


class PromptInput(SchemaModel):
    """The only case data exposed to the historical GPT-style prompt."""

    description: NonEmptyStr


class LM4OptProtocol(SchemaModel):
    name: NonEmptyStr
    version: Literal["1"] = PROTOCOL_VERSION
    condition: Literal["zero-shot", "one-shot"]
    template_path: NonEmptyStr
    source_status: Literal["paper-reproduced"] = "paper-reproduced"
    input_view: Literal["problem description only"] = "problem description only"
    demonstration_included: bool
    condition_metadata: dict[str, JsonValue]

    @property
    def template(self) -> str:
        path = Path(self.template_path)
        if path.exists():
            return path.read_text(encoding="utf-8")
        packaged = files("thesis_bench").joinpath("prompt_artifacts", path.name)
        return packaged.read_text(encoding="utf-8")

    @property
    def template_sha256(self) -> str:
        return hashlib.sha256(self.template.encode("utf-8")).hexdigest()

    def input_view_for(self, case: BenchmarkCase) -> PromptInput:
        """Build a target-only view; references and NER fields never enter it."""
        return PromptInput(description=case.description)

    def render(self, case: BenchmarkCase) -> tuple[Message, ...]:
        prompt = PromptProtocol(
            name=self.name,
            version=self.version,
            template=self.template,
            condition=self.condition,
            condition_metadata=self.condition_metadata,
        )
        target = self.input_view_for(case)
        return (Message(role="user", content=Template(prompt.template).substitute(
            description=target.description
        )),)

    def rendered_prompt_sha256(self, case: BenchmarkCase) -> str:
        content = self.render(case)[0].content
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _protocol(name: str) -> LM4OptProtocol:
    if name == PROTOCOL_ZERO_SHOT:
        return LM4OptProtocol(
            name=name,
            condition="zero-shot",
            template_path="prompts/nl4opt/lm4opt/zero_shot_v1.txt",
            demonstration_included=False,
            condition_metadata={
                "paper_source": "Figure 2, Zero-shot Instruction",
                "example_response_format": True,
                "example_problem_solution_pair": False,
                "system_role": "not reported",
            },
        )
    if name == PROTOCOL_ONE_SHOT:
        return LM4OptProtocol(
            name=name,
            condition="one-shot",
            template_path="prompts/nl4opt/lm4opt/one_shot_v1.txt",
            demonstration_included=True,
            condition_metadata={
                "paper_source": "Figure 2, One-shot Instruction",
                "example_response_format": True,
                "example_problem_solution_pair": True,
                "system_role": "not reported",
            },
        )
    raise ValueError(f"unknown LM4OPT protocol: {name!r}")


def get_lm4opt_protocol(name: str) -> LM4OptProtocol:
    return _protocol(name)


def protocol_names() -> tuple[str, str]:
    return PROTOCOL_ZERO_SHOT, PROTOCOL_ONE_SHOT
