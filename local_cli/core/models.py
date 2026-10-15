"""Immutable model observations; Core never imports a provider manager."""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from local_cli.core.contracts import json_safe_copy


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class ModelRuntimeSnapshot:
    provider_id: str
    model_id: str
    provider_revision: int
    endpoint: str | None = None
    health: str = "UNKNOWN"
    capability_source: str = "unprobed"
    model_context_window: int | None = None
    model_revision: str | None = None
    provider_context_window: int | None = None
    max_output_tokens: int | None = None
    quantization: str | None = None
    tool_support: str = "UNKNOWN"
    thinking_support: str = "UNKNOWN"
    embedding_support: str = "UNKNOWN"
    concurrency_limit: int | None = None
    inference_options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if (not isinstance(self.provider_id, str) or not self.provider_id.strip()
                or not isinstance(self.model_id, str) or not self.model_id.strip()
                or type(self.provider_revision) is not int or self.provider_revision < 1):
            raise ValueError("invalid model runtime identity")
        if any(value not in ("UNKNOWN", "AVAILABLE", "UNAVAILABLE") for value in (
                self.health, self.tool_support, self.thinking_support, self.embedding_support)):
            raise ValueError("invalid model observation")
        if any(value is not None and (type(value) is not int or value < 1)
               for value in (self.model_context_window, self.provider_context_window,
                             self.max_output_tokens, self.concurrency_limit)):
            raise ValueError("invalid model resource observation")
        if self.quantization is not None and (not isinstance(self.quantization, str) or not self.quantization.strip()):
            raise ValueError("invalid quantization observation")
        if self.model_revision is not None and (not isinstance(self.model_revision, str) or not self.model_revision.strip()):
            raise ValueError("invalid model revision observation")
        object.__setattr__(self, "inference_options",
                           _freeze(json_safe_copy(self.inference_options)))

    def to_dict(self):
        return {"providerId": self.provider_id, "modelId": self.model_id,
                "providerRevision": self.provider_revision, "endpoint": self.endpoint,
                "health": self.health, "capabilitySource": self.capability_source,
                "modelContextWindow": self.model_context_window,
                "modelRevision": self.model_revision,
                "providerContextWindow": self.provider_context_window,
                "maxOutputTokens": self.max_output_tokens, "quantization": self.quantization,
                "toolSupport": self.tool_support, "thinkingSupport": self.thinking_support,
                "embeddingSupport": self.embedding_support,
                "concurrencyLimit": self.concurrency_limit,
                "inferenceOptions": json_safe_copy(self.inference_options)}
