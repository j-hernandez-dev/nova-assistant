"""Session-owned provider state, atomic transitions and pinned inference views.

Only Application owns the manager. AgentLoop receives BoundModelRuntime through
the existing ModelInferencePort. Factories are injected by composition roots.
"""

from dataclasses import dataclass, field, replace
from threading import RLock
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit

from local_cli.core.models import ModelRuntimeSnapshot
from local_cli.application.secrets import SecretRedactor
from local_cli.core.contracts import json_safe_copy
from local_cli.providers.base import ProviderConnectionError, LLMProvider


class ProviderTransitionError(ValueError):
    def __init__(self, code: str, message: str, category: str = "PROVIDER"):
        super().__init__(message)
        self.code, self.category = code, category


def _endpoint(provider):
    value = (getattr(getattr(provider, "client", None), "base_url", None)
             or getattr(provider, "_base_url", None))
    if not isinstance(value, str):
        return None
    # Public snapshots never contain endpoint credentials, query strings or fragments.
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    if ":" in host:
        host = "[" + host + "]"
    authority = host + (f":{parsed.port}" if parsed.port else "")
    return urlunsplit((parsed.scheme, authority, parsed.path, "", ""))


def provider_clone_factory(provider):
    """Capture exact adapter configuration, including private credentials.

    This callable is private and never serialized. It must not re-read credentials
    or endpoints from a later environment when an older snapshot spawns a worker.
    """
    from local_cli.providers.ollama_provider import OllamaProvider
    from local_cli.providers.claude_provider import ClaudeProvider
    from local_cli.providers.llama_server_provider import LlamaServerProvider
    if isinstance(provider, OllamaProvider):
        endpoint = provider.client.base_url
        return lambda: OllamaProvider(base_url=endpoint)
    if isinstance(provider, ClaudeProvider):
        params = dict(api_key=provider._api_key, base_url=provider._base_url,
                      default_max_tokens=provider._default_max_tokens,
                      timeout=provider._timeout, stream_timeout=provider._stream_timeout)
        return lambda: ClaudeProvider(**params)
    if isinstance(provider, LlamaServerProvider):
        endpoint = provider._base_url
        return lambda: LlamaServerProvider(base_url=endpoint)
    return None  # Legacy/test adapters can inject their own fresh-instance factory.


def configured_provider_factory(*, ollama_client=None, ollama_host="http://localhost:11434",
                                llama_server_url="http://localhost:8090"):
    """Composition adapter shared by legacy clients; no switching policy here."""
    def create(name):
        from local_cli.providers import get_provider
        if name == "ollama":
            return get_provider(name, **({"client": ollama_client} if ollama_client is not None
                                        else {"base_url": ollama_host}))
        if name == "llama-server":
            return get_provider(name, base_url=llama_server_url)
        return get_provider(name)
    return create


@dataclass(frozen=True)
class BoundModelRuntime:
    snapshot: ModelRuntimeSnapshot
    _provider: Any = field(repr=False, compare=False)
    _fresh_factory: Callable[[], Any] | None = field(repr=False, compare=False)
    _context: Any = field(default=None, repr=False, compare=False)
    _redactor: Any = field(default=None, repr=False, compare=False)

    @property
    def name(self):
        return self.snapshot.provider_id

    @property
    def context_managed(self):
        return self._context is not None

    def fresh(self):
        if self._fresh_factory is None:
            raise ProviderTransitionError("UNSUPPORTED_CLONE", "No fresh provider factory")
        # A child shares immutable policy/evidence, not its parent's event sink
        # or current-user identity. Its own prompt is budgeted independently.
        provider = self._fresh_factory()
        context = self._context
        if context is not None:
            from local_cli.application.context import InferenceContext
            from local_cli.core.context import ContextManager
            manager = context.manager
            method = getattr(type(provider), "count_tokens", None)
            tokenizer = (lambda text: provider.count_tokens(self.snapshot.model_id, text)) if callable(method) else None
            context = InferenceContext(ContextManager(manager.selection, policy=manager.policy,
                model_limit=manager.model_limit, provider_limit=manager.provider_limit,
                max_output_tokens=manager.max_output_tokens, tokenizer=tokenizer), context.capabilities)
        if self._redactor is not None:
            self._redactor.observe_provider(provider)
        return BoundModelRuntime(self.snapshot, provider, self._fresh_factory, context, self._redactor)

    def format_tools(self, tools):
        if hasattr(self._provider, "format_tools"):
            return self._provider.format_tools(tools)
        return [tool.to_ollama_tool() for tool in tools]

    def _kwargs(self, kwargs):
        merged = {**json_safe_copy(self.snapshot.inference_options), **kwargs}
        allowed = ({"tools", "max_tokens", "options", "think", "format", "keep_alive"}
                   if self.name == "ollama" else {"tools", "max_tokens"})
        if self.name in ProviderManager.SUPPORTED and set(merged) - allowed:
            raise ProviderTransitionError("UNSUPPORTED_INFERENCE_OPTION",
                                          "Inference option is not supported")
        return merged

    def chat_stream(self, model, messages, **kwargs):
        if model != self.snapshot.model_id:
            raise ProviderTransitionError("MODEL_SNAPSHOT_CONFLICT", "Model does not match snapshot", "MODEL")
        merged = self._kwargs(kwargs)
        messages = self._redactor.messages(messages) if self._redactor else messages
        prepared = self._prepare(messages, merged)
        stream = self._provider.chat_stream(model, prepared.messages if prepared else messages, **merged)
        streams = {key: self._redactor.stream() for key in ('content', 'thinking')} if self._redactor else {}
        try:
            for chunk in stream:
                if prepared is not None:
                    self._context.observe(chunk, prepared.budget)
                if self._redactor:
                    safe = self._redactor.value(chunk)
                    message = chunk.get('message') or {}
                    for key, scrub in streams.items():
                        if isinstance(message.get(key), str):
                            safe.setdefault('message', {})[key] = scrub.feed(message[key])
                        if chunk.get('done'):
                            tail = scrub.finish()
                            if tail:
                                safe.setdefault('message', {})[key] = safe.get('message', {}).get(key, '') + tail
                    chunk = safe
                yield chunk
            for key, scrub in streams.items():
                tail = scrub.finish()
                if tail:
                    yield {'message': {'role': 'assistant', key: tail}}
        except BaseException as exc:
            if self._redactor:
                self._redactor.exception(exc)
            raise
        finally:
            close = getattr(stream, "close", None)
            if close is not None:
                try:
                    close()
                except BaseException as exc:
                    if self._redactor:
                        self._redactor.exception(exc)
                    raise

    def chat(self, model, messages, **kwargs):
        if model != self.snapshot.model_id:
            raise ProviderTransitionError("MODEL_SNAPSHOT_CONFLICT", "Model does not match snapshot", "MODEL")
        merged = self._kwargs(kwargs)
        messages = self._redactor.messages(messages) if self._redactor else messages
        prepared = self._prepare(messages, merged)
        try:
            result = self._provider.chat(model, prepared.messages if prepared else messages, **merged)
        except BaseException as exc:
            if self._redactor:
                self._redactor.exception(exc)
            raise
        if prepared is not None:
            self._context.observe(result, prepared.budget)
        return self._redactor.value(result) if self._redactor else result

    def _prepare(self, messages, kwargs):
        if self._context is None:
            return None
        prepared = self._context.prepare(messages, kwargs.get("tools"))
        if self.name == "ollama":
            options = dict(kwargs.get("options") or {})
            options["num_ctx"] = prepared.budget.selected_context_window
            requested = options.get("num_predict")
            options["num_predict"] = min(requested, prepared.budget.output_reserve) if type(requested) is int and requested > 0 else prepared.budget.output_reserve
            kwargs["options"] = options
        elif self.name in ("claude", "llama-server"):
            kwargs["max_tokens"] = min(kwargs.get("max_tokens") or prepared.budget.output_reserve,
                                       prepared.budget.output_reserve)
        return prepared


# The legacy loop uses this ABC to choose native provider tool formatting.
# S6's redacting wrapper must preserve that compatibility discriminator.
LLMProvider.register(BoundModelRuntime)


class ProviderManager:
    """One provider/model/revision per session. OD-04: reject, never queue."""

    SUPPORTED = ("ollama", "claude", "llama-server")

    def __init__(self, provider, model: str, *,
                 provider_factory: Callable[[str], Any] | None = None,
                 clone_factory: Callable[[Any], Callable[[], Any] | None] = provider_clone_factory):
        self._lock = RLock()
        self._factory = provider_factory
        self._clone_factory = clone_factory
        self._active_turn = None
        self.redactor = SecretRedactor()
        self.redactor.observe_provider(provider)
        name = getattr(provider, "name", "legacy")
        name = name if isinstance(name, str) else "legacy"
        self._current = BoundModelRuntime(
            ModelRuntimeSnapshot(name, model, 1, endpoint=_endpoint(provider)),
            provider, clone_factory(provider), _redactor=self.redactor)

    def snapshot(self):
        with self._lock:
            return self._current

    def begin_turn(self, turn_id, *, inference_options=None):
        with self._lock:
            if self._active_turn is not None:
                raise ProviderTransitionError("CONFLICT_ACTIVE_TURN", "A main Turn is active")
            current = self._current
            if inference_options:
                current = replace(current, snapshot=replace(current.snapshot,
                                  inference_options=inference_options))
                current._kwargs({})  # Never silently accept unsupported options.
            self._active_turn = turn_id
            return current

    def end_turn(self, turn_id):
        with self._lock:
            if self._active_turn != turn_id:
                raise ProviderTransitionError("STALE_TURN", "Turn ownership does not match")
            self._active_turn = None

    def _guard(self, expected_revision):
        if self._active_turn is not None:
            raise ProviderTransitionError("CONFLICT_ACTIVE_TURN",
                                          "Provider/model cannot change during an active Turn")
        if expected_revision is not None and expected_revision != self._current.snapshot.provider_revision:
            raise ProviderTransitionError("PROVIDER_REVISION_CONFLICT", "Provider revision changed")

    @staticmethod
    def _observe(provider, model, revision, *, choose_model=False):
        name = provider.name
        try:
            models = provider.list_models()
            names = [item["name"] for item in models
                     if isinstance(item, dict) and isinstance(item.get("name"), str)]
            matches = [n for n in names if n == model or (name == "ollama" and n.split(":")[0] == model)]
            if not matches and choose_model and names:
                model = names[0]
            elif not matches:
                raise ProviderTransitionError("MODEL_UNAVAILABLE", "Model is not available on this provider", "MODEL")
            info = provider.get_model_info(model)
            if not isinstance(info, dict):
                raise ProviderTransitionError("INVALID_MODEL_INFO", "Provider returned invalid model information", "MODEL")
        except ProviderTransitionError:
            raise
        except ProviderConnectionError as exc:
            raise ProviderTransitionError("PROVIDER_UNAVAILABLE", "Provider is unreachable") from exc
        except Exception as exc:
            raise ProviderTransitionError("PROVIDER_VALIDATION_FAILED", "Could not validate provider/model") from exc
        caps = info.get("capabilities")
        def support(cap):
            return ("AVAILABLE" if cap in caps else "UNAVAILABLE") if isinstance(caps, list) else "UNKNOWN"
        raw_model_info = info.get("model_info", {})
        if not isinstance(raw_model_info, dict):
            raise ProviderTransitionError("INVALID_MODEL_INFO", "Provider returned invalid model information", "MODEL")
        contexts = [v for k, v in raw_model_info.items()
                    if k.endswith(".context_length") and type(v) is int and v > 0]
        for key in ("provider_context_window", "max_output_tokens"):
            value = info.get(key)
            if value is not None and (type(value) is not int or value < 1):
                raise ProviderTransitionError("INVALID_MODEL_INFO", "Provider reported an invalid resource limit", "MODEL")
        quantization = info.get("details", {}).get("quantization_level") if isinstance(info.get("details"), dict) else None
        if quantization is not None and (not isinstance(quantization, str) or not quantization.strip()):
            raise ProviderTransitionError("INVALID_MODEL_INFO", "Provider reported invalid quantization", "MODEL")
        digest = info.get("digest") or next((item.get("digest") for item in models
            if isinstance(item, dict) and item.get("name") == model), None)
        digest = digest if isinstance(digest, str) and digest.strip() else None
        return ModelRuntimeSnapshot(
            name, model, revision, endpoint=_endpoint(provider),
            health="UNKNOWN" if name == "claude" else "AVAILABLE",
            capability_source="adapter_catalog" if name == "claude" else "provider_model_info",
            model_context_window=min(contexts) if contexts else None,
            model_revision=digest,
            provider_context_window=info.get("provider_context_window"),
            max_output_tokens=info.get("max_output_tokens"),
            quantization=quantization,
            tool_support=support("tools"), thinking_support=support("thinking"),
            embedding_support=support("embedding"))

    def change_model(self, model, *, expected_revision=None):
        with self._lock:
            self._guard(expected_revision)
            if not isinstance(model, str) or not model.strip():
                raise ProviderTransitionError("INVALID_MODEL", "Model must be non-empty", "MODEL")
            current = self._current
            observed = self._observe(current._provider, model, current.snapshot.provider_revision + 1)
            self._current = BoundModelRuntime(observed, current._provider, current._fresh_factory, _redactor=self.redactor)
            return self._current

    def change_provider(self, name, *, model=None, expected_revision=None):
        with self._lock:
            self._guard(expected_revision)
            if name not in self.SUPPORTED or self._factory is None:
                raise ProviderTransitionError("UNSUPPORTED_PROVIDER", "Provider is not configured")
            if model is not None and (not isinstance(model, str) or not model.strip()):
                raise ProviderTransitionError("INVALID_MODEL", "Model must be non-empty", "MODEL")
            try:
                provider = self._factory(name)
                self.redactor.observe_provider(provider)
                if provider.name != name:
                    raise ValueError("factory returned another provider")
                observed = self._observe(provider, model or self._current.snapshot.model_id,
                    self._current.snapshot.provider_revision + 1, choose_model=model is None)
                candidate = BoundModelRuntime(observed, provider, self._clone_factory(provider), _redactor=self.redactor)
            except ProviderTransitionError:
                raise
            except Exception as exc:
                raise ProviderTransitionError("PROVIDER_CONFIGURATION_FAILED", "Provider is not configured or credentials are missing") from exc
            self._current = candidate
            return candidate

    def get_model_info(self, model=None):
        current = self.snapshot()
        try:
            return current._provider.get_model_info(model or current.snapshot.model_id)
        except ProviderConnectionError as exc:
            raise ProviderTransitionError("PROVIDER_UNAVAILABLE", "Provider is unreachable") from exc
        except Exception as exc:
            raise ProviderTransitionError("PROVIDER_VALIDATION_FAILED", "Could not read model information") from exc

    def refresh_status(self):
        """Refresh observations, not identity; in-flight views stay immutable.

        Claude's static catalog is configuration evidence, not an authenticated
        health probe. Unknown facts remain explicit rather than being invented.
        """
        with self._lock:
            current = self._current
            try:
                observed = self._observe(current._provider, current.snapshot.model_id,
                                         current.snapshot.provider_revision)
            except ProviderTransitionError as exc:
                observed = replace(current.snapshot,
                    health="UNAVAILABLE" if exc.code == "PROVIDER_UNAVAILABLE" else "UNKNOWN",
                    capability_source="probe_failed")
            self._current = replace(current, snapshot=observed)
            return observed

    def list_models(self):
        try:
            return self.snapshot()._provider.list_models()
        except ProviderConnectionError as exc:
            raise ProviderTransitionError("PROVIDER_UNAVAILABLE", "Provider is unreachable") from exc
        except Exception as exc:
            raise ProviderTransitionError("PROVIDER_VALIDATION_FAILED", "Could not read model catalog") from exc

    def chat_stream(self, model, messages, **kwargs):
        yield from self.snapshot().chat_stream(model, messages, **kwargs)
