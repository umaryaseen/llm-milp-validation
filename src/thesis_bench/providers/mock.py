import hashlib
import json

from thesis_bench.providers.base import LLMRequest, LLMResponse


class MockLLMProvider:
    """Deterministic fixture, including synthetic latency and unknown token usage."""

    name = "mock"

    def __init__(self, *, raw_text: str | None = None) -> None:
        self._raw_text = raw_text

    def generate(self, request: LLMRequest) -> LLMResponse:
        canonical = json.dumps(
            request.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        raw_text = self._raw_text
        if raw_text is None:
            raw_text = json.dumps({"mock": True, "request_sha256": fingerprint}, sort_keys=True)
        return LLMResponse(
            raw_text=raw_text,
            provider=self.name,
            model_id=request.model_id,
            latency_seconds=0.0,
            raw_metadata={
                "synthetic": True,
                "latency_is_synthetic": True,
                "request_sha256": fingerprint,
            },
        )
