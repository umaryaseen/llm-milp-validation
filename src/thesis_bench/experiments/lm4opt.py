"""Offline LM4OPT protocol dry runs using the deterministic MockLLMProvider."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from thesis_bench.benchmarks.base import BenchmarkCase
from thesis_bench.evaluation.lm4opt import (
    PARSER_ID,
    PARSER_VERSION,
    LM4OptPaperReconstructedParser,
    to_phase2_xml,
)
from thesis_bench.evaluation.nl4opt import EVALUATOR_VERSION, evaluate_nl4opt
from thesis_bench.experiments.storage import ArtifactConflictError, write_model_new, write_text_new
from thesis_bench.models import FileID, NonEmptyStr, SchemaModel
from thesis_bench.prompts.lm4opt import LM4OptProtocol, get_lm4opt_protocol
from thesis_bench.providers.base import GenerationConfig, LLMRequest
from thesis_bench.providers.mock import MockLLMProvider


class LM4OptMockRecord(SchemaModel):
    experiment_id: FileID
    run_id: FileID
    benchmark: NonEmptyStr
    benchmark_version: NonEmptyStr
    case_id: NonEmptyStr
    split: NonEmptyStr | None
    protocol: NonEmptyStr
    protocol_version: NonEmptyStr
    provider: NonEmptyStr
    model_id: NonEmptyStr
    generation: GenerationConfig
    parser_id: NonEmptyStr
    parser_version: NonEmptyStr
    template_sha256: NonEmptyStr
    rendered_prompt_sha256: NonEmptyStr
    evaluator_sha: NonEmptyStr
    status: Literal["completed", "failed"]
    response_path: str
    raw_response_path: str | None
    parsed_response_path: str
    canonical_path: str | None
    evaluation_result_path: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime
    error: str | None = None


def _format(value: float) -> str:
    return str(float(value))


def gold_like_response(case: BenchmarkCase) -> str:
    """Create a deterministic paper-format response from the frozen reference only."""
    if case.raw_record is None:
        raise ValueError("mock response generation requires the raw NL4Opt record")
    from thesis_bench._vendor.nl4opt import parsers

    order = case.raw_record["order_mapping"]
    parsed = parsers.JSONFormulationParser(False).parse({case.case_id: case.raw_record}, order)
    canonical = parsers.convert_to_canonical(parsed)
    source_variables = case.raw_record.get("vars")
    if isinstance(source_variables, list) and source_variables:
        variables = tuple(str(name) for name in source_variables)
    else:
        variables = tuple(name for name, _ in sorted(order.items(), key=lambda item: int(item[1])))
    objective = canonical.objective.tolist()
    lines = [f"Variables: {', '.join(variables)}", "Constraints:"]
    for row in canonical.constraints.tolist():
        terms = " + ".join(
            f"({_format(coefficient)}) * {variable}"
            for variable, coefficient in zip(variables, row[:-1], strict=True)
        )
        lines.append(f"{terms} <= {_format(row[-1])}")
    terms = " + ".join(
        f"({_format(coefficient)}) * {variable}"
        for variable, coefficient in zip(variables, objective, strict=True)
    )
    lines.extend(["Objective Function:", f"minimize {terms}"])
    return "\n".join(lines)


def run_lm4opt_mock(
    root: Path,
    case: BenchmarkCase,
    protocol_name: str,
    raw_response: str,
    *,
    run_id: str,
) -> Path:
    protocol: LM4OptProtocol = get_lm4opt_protocol(protocol_name)
    messages = protocol.render(case)
    request = LLMRequest(
        model_id="mock-lm4opt-v1",
        messages=messages,
        generation=GenerationConfig(temperature=0.0),
    )
    run_dir = root / "experiments" / "lm4opt-protocol-mock" / "runs" / run_id
    try:
        run_dir.mkdir(parents=True)
    except FileExistsError as exc:
        raise ArtifactConflictError(
            f"Run already exists at {run_dir}; refusing to overwrite"
        ) from exc
    write_model_new(run_dir / "request.json", request)
    provider = MockLLMProvider(raw_text=raw_response)
    response = None
    parsed = None
    evaluation = None
    error: str | None = None
    try:
        prompt_text = messages[0].content
        write_text_new(run_dir / "raw_prompt.txt", prompt_text)
        response = provider.generate(request)
        write_text_new(run_dir / "raw_response.txt", response.raw_text)
        write_model_new(run_dir / "response.json", response)
        parsed = LM4OptPaperReconstructedParser().parse(response.raw_text)
        evaluation_input = (
            to_phase2_xml(parsed.canonical)
            if parsed.canonical is not None
            else response.raw_text
        )
        write_model_new(run_dir / "parsed.json", parsed)
        canonical_payload = {
            "parser_id": parsed.parser_id,
            "parser_version": parsed.parser_version,
            "canonical": (
                parsed.canonical.model_dump(mode="json")
                if parsed.canonical is not None
                else None
            ),
            "errors": list(parsed.errors),
            "notes": list(parsed.notes),
        }
        write_text_new(run_dir / "canonical.json", json.dumps(canonical_payload, indent=2) + "\n")
        evaluation = evaluate_nl4opt(case, evaluation_input)
        write_model_new(run_dir / "evaluation.json", evaluation)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    record = LM4OptMockRecord(
        experiment_id="lm4opt-protocol-mock",
        run_id=run_id,
        benchmark=case.benchmark_id,
        benchmark_version=case.benchmark_version,
        case_id=case.case_id,
        split=case.split,
        protocol=protocol.name,
        protocol_version=protocol.version,
        provider=response.provider if response is not None else provider.name,
        model_id=response.model_id if response is not None else request.model_id,
        generation=request.generation,
        parser_id=PARSER_ID,
        parser_version=PARSER_VERSION,
        template_sha256=protocol.template_sha256,
        rendered_prompt_sha256=protocol.rendered_prompt_sha256(case),
        evaluator_sha=evaluation.evaluator_version if evaluation is not None else EVALUATOR_VERSION,
        status="failed" if error else "completed",
        response_path="response.json" if response is not None else "",
        raw_response_path="raw_response.txt" if response is not None else None,
        parsed_response_path="parsed.json" if parsed is not None else "",
        canonical_path="canonical.json" if parsed is not None else None,
        evaluation_result_path="evaluation.json" if evaluation is not None else "",
        metrics={
            "official_score": evaluation.official_score if evaluation is not None else None,
            "parse_errors": parsed.errors if parsed is not None else [],
        },
        timestamp=datetime.now(UTC),
        error=error,
    )
    write_model_new(run_dir / "record.json", record)
    if error:
        raise RuntimeError(f"LM4OPT dry run failed; observation retained at {run_dir}")
    return run_dir
