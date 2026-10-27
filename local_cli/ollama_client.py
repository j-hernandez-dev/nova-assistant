"""Ollama HTTP client for local-cli.

Provides a zero-dependency client for communicating with the Ollama REST API
using only ``urllib.request`` from the standard library.  Supports streaming
chat completions (NDJSON), embeddings, model management, and version queries.
"""

import json
import socket
import urllib.error
import urllib.request
from typing import Any, Generator

from local_cli.providers.base import (
    ProviderConnectionError,
    ProviderRequestError,
    ProviderStreamError,
)
from local_cli.security import validate_model_name, validate_ollama_host
from local_cli.providers.stream_control import open_stream, StreamCancelled, StreamTimedOut, ResponseDeadline

# ---------------------------------------------------------------------------
# Default timeouts (seconds)
# ---------------------------------------------------------------------------

# Simple API calls (version, tags, etc.).
_DEFAULT_TIMEOUT = 30

# Streaming chat completions (model may take time to start generating).
# CPU-only inference with large models + tools can take several minutes
# before the first token is emitted; allow up to 15 minutes without a response.
_STREAM_TIMEOUT = 15 * 60
# Managed chat calls separate TCP setup from cold-load/prefill and output stalls.
_FIRST_RESPONSE_TIMEOUT = _STREAM_TIMEOUT
_RESPONSE_IDLE_TIMEOUT = _STREAM_TIMEOUT


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class OllamaConnectionError(ProviderConnectionError):
    """Raised when the client cannot connect to Ollama.

    Inherits from :class:`~local_cli.providers.base.ProviderConnectionError`
    so that ``except ProviderConnectionError`` catches this as well.
    """
    code = "OLLAMA_CONNECTION_FAILED"


class OllamaResponseTimeout(ProviderStreamError):
    """The service connected, but model output exceeded its response deadline."""
    code = "OLLAMA_RESPONSE_TIMEOUT"


class OllamaRequestError(ProviderRequestError):
    """Raised when the Ollama API returns an error response.

    Inherits from :class:`~local_cli.providers.base.ProviderRequestError`
    so that ``except ProviderRequestError`` catches this as well.
    """


class OllamaStreamError(ProviderStreamError):
    """Raised when an error is encountered mid-stream.

    Inherits from :class:`~local_cli.providers.base.ProviderStreamError`
    so that ``except ProviderStreamError`` catches this as well.
    """


# ---------------------------------------------------------------------------
# Error formatting
# ---------------------------------------------------------------------------


def _format_http_error(exc: urllib.error.HTTPError, url: str) -> str:
    """Build an error message including the server's error detail.

    Ollama puts the actual failure reason (e.g. ``"<model>" does not
    support tools``) in the JSON response body; ``exc.reason`` is just
    the bare HTTP phrase ("Bad Request").  Reading the body makes 4xx
    errors diagnosable — and lets the agent loop detect the
    tools-unsupported case and fall back to text-driven tool calls.

    Args:
        exc: The HTTP error (its body is consumed here).
        url: The request URL, for context.

    Returns:
        A message like ``Ollama API error 400 at <url>: Bad Request
        (<server detail>)``.
    """
    message = f"Ollama API error {exc.code} at {url}: {exc.reason}"
    try:
        raw = exc.read().decode("utf-8", errors="replace").strip()
    except Exception:
        return message
    if not raw:
        return message
    detail = raw
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict) and payload.get("error"):
            detail = str(payload["error"])
    except (json.JSONDecodeError, ValueError):
        pass
    return f"{message} ({detail[:300]})"


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class OllamaClient:
    """HTTP client for the Ollama REST API.

    Uses ``urllib.request`` for all HTTP communication.  Each request opens a
    new TCP connection (no connection pooling).

    Args:
        base_url: Base URL for the Ollama API.  Must point to localhost.
            Defaults to ``http://localhost:11434``.

    Raises:
        ValueError: If *base_url* does not point to a localhost address.
    """

    def __init__(self, base_url: str = "http://localhost:11434", *, usage_recorder=None) -> None:
        base_url = base_url.rstrip("/")

        if not validate_ollama_host(base_url):
            raise ValueError(
                f"Ollama host must be a localhost address, got: {base_url}"
            )

        self.base_url: str = base_url
        self.usage_recorder = usage_recorder

    def _begin_usage(self, path, data, should_stop=None):
        if self.usage_recorder is None or path not in ('/api/chat', '/api/generate') or (should_stop is not None and should_stop()):
            return None
        return self.usage_recorder.begin((data or {}).get('model', ''))

    def _finish_usage(self, identity, data, outcome):
        if self.usage_recorder is not None:
            self.usage_recorder.finish(identity, data, outcome)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> dict[str, Any]:
        """Send an HTTP request to the Ollama API and return parsed JSON.

        Args:
            method: HTTP method (``GET``, ``POST``, etc.).
            path: API path (e.g. ``/api/version``).
            data: Optional JSON body for the request.
            timeout: Socket timeout in seconds.

        Returns:
            Parsed JSON response as a dictionary.

        Raises:
            OllamaConnectionError: On connection failure or timeout.
            OllamaRequestError: On HTTP error responses.
        """
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode("utf-8") if data else None
        headers: dict[str, str] = {}
        if body is not None:
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(
            url, data=body, headers=headers, method=method,
        )

        usage_id = self._begin_usage(path, data)
        usage_data, outcome = {}, 'failed'
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                result = json.loads(raw)
                if isinstance(result, dict):
                    usage_data = result
                    outcome = 'completed'
                return result
        except urllib.error.HTTPError as exc:
            raise OllamaRequestError(
                _format_http_error(exc, url)
            ) from exc
        except urllib.error.URLError as exc:
            raise OllamaConnectionError(
                f"Failed to connect to Ollama at {url}: {exc}"
            ) from exc
        except socket.timeout as exc:
            raise OllamaConnectionError(
                f"Request to Ollama timed out ({timeout}s): {url}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise OllamaRequestError(
                f"Invalid JSON response from Ollama: {exc}"
            ) from exc
        finally:
            self._finish_usage(usage_id, usage_data, outcome)

    def _stream_request(
        self,
        path: str,
        data: dict[str, Any],
        timeout: int = _STREAM_TIMEOUT,
        should_stop=None,
    ) -> Generator[dict[str, Any], None, None]:
        """Send a POST request and yield parsed NDJSON lines.

        Each line of the response is parsed as a separate JSON object and
        yielded.  Mid-stream ``{"error": ...}`` objects raise
        :class:`OllamaStreamError`.

        Args:
            path: API path (e.g. ``/api/chat``).
            data: JSON body for the POST request.
            timeout: Socket timeout in seconds.

        Yields:
            Parsed JSON chunks from the NDJSON response stream.

        Raises:
            OllamaConnectionError: On connection failure or timeout.
            OllamaStreamError: If the server sends an error object mid-stream.
        """
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        saw_done = False
        usage_id = self._begin_usage(path, data, should_stop)
        usage_data, outcome = {}, 'failed'
        deadline = (ResponseDeadline(_FIRST_RESPONSE_TIMEOUT, _RESPONSE_IDLE_TIMEOUT)
                    if path in ("/api/chat", "/api/generate") and should_stop is not None else None)
        stream_options = {"response_deadline": deadline} if deadline is not None else {}
        try:
            with open_stream(req, timeout, should_stop, **stream_options) as resp:
                for line in resp:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if "error" in chunk:
                        raise OllamaStreamError(f"Ollama error: {chunk['error']}")
                    for key in ('prompt_eval_count', 'eval_count'):
                        if key in chunk:
                            usage_data[key] = chunk[key]
                    saw_done = saw_done or chunk.get("done") is True
                    if saw_done:
                        outcome = 'completed'
                    message = chunk.get("message") or {}
                    if deadline is not None and (saw_done or chunk.get("response") or
                            message.get("content") or message.get("thinking") or message.get("tool_calls")):
                        deadline.progress()
                    yield chunk
                if should_stop is not None and not should_stop() and not saw_done:
                    raise OllamaStreamError("Ollama closed the stream before its terminal response")
        except StreamCancelled:
            outcome = 'interrupted'
            return
        except StreamTimedOut as exc:
            raise OllamaResponseTimeout("Ollama connected but did not respond within the allowed time") from exc
        except urllib.error.HTTPError as exc:
            detail = _format_http_error(exc, url)
            error = OllamaRequestError(detail)
            if exc.code == 404 and "model" in detail.lower() and "not found" in detail.lower():
                error.code = "OLLAMA_MODEL_UNAVAILABLE"
            raise error from exc
        except urllib.error.URLError as exc:
            if deadline is not None and deadline.started is not None and isinstance(exc.reason, socket.timeout):
                raise OllamaResponseTimeout("Ollama connected but its response timed out") from exc
            error = OllamaConnectionError(f"Failed to connect to Ollama at {url}: {exc}")
            if isinstance(exc.reason, socket.timeout):
                error.code = "OLLAMA_CONNECT_TIMEOUT"
            raise error from exc
        except socket.timeout as exc:
            if deadline is not None and deadline.started is not None:
                raise OllamaResponseTimeout("Ollama connected but its response timed out") from exc
            error = OllamaConnectionError(f"Ollama connection timed out: {url}")
            error.code = "OLLAMA_CONNECT_TIMEOUT"
            raise error from exc
        except OSError as exc:
            raise OllamaConnectionError(f"Ollama stream connection failed: {url}") from exc
        finally:
            if should_stop is not None and should_stop() and not saw_done:
                outcome = 'interrupted'
            self._finish_usage(usage_id, usage_data, outcome)

    def _request_no_content(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        """Send an HTTP request that returns no JSON body (HTTP 200 OK).

        Used by endpoints like ``DELETE /api/delete`` and ``POST /api/copy``
        that return an empty or status-only response.

        Args:
            method: HTTP method (``DELETE``, ``POST``, etc.).
            path: API path (e.g. ``/api/delete``).
            data: Optional JSON body for the request.
            timeout: Socket timeout in seconds.

        Raises:
            OllamaConnectionError: On connection failure or timeout.
            OllamaRequestError: On HTTP error responses.
        """
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode("utf-8") if data else None
        headers: dict[str, str] = {}
        if body is not None:
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(
            url, data=body, headers=headers, method=method,
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp.read()  # consume body without parsing
        except urllib.error.URLError as exc:
            raise OllamaConnectionError(
                f"Failed to connect to Ollama at {url}: {exc}"
            ) from exc
        except socket.timeout as exc:
            raise OllamaConnectionError(
                f"Request to Ollama timed out ({timeout}s): {url}"
            ) from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_version(self) -> dict[str, Any]:
        """Get the Ollama server version.

        Returns:
            Version information dict (e.g. ``{"version": "0.5.1"}``).

        Raises:
            OllamaConnectionError: On connection failure.
            OllamaRequestError: On unexpected response.
        """
        return self._request("GET", "/api/version")

    def list_models(self) -> list[dict[str, Any]]:
        """List models available on the Ollama server.

        Returns:
            A list of model info dicts from the ``models`` key of the
            ``/api/tags`` response.

        Raises:
            OllamaConnectionError: On connection failure.
            OllamaRequestError: On unexpected response.
        """
        result = self._request("GET", "/api/tags")
        return result.get("models", [])

    def _validate_model(self, model: str) -> None:
        """Validate a model name before sending to the API.

        Args:
            model: Model name to validate.

        Raises:
            ValueError: If the model name is invalid.
        """
        if not validate_model_name(model):
            raise ValueError(f"Invalid model name: {model!r}")

    def chat_stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        options: dict[str, Any] | None = None,
        think: bool | None = None,
        format: str | dict[str, Any] | None = None,
        keep_alive: str | int | None = None,
        *, _should_stop=None,
    ) -> Generator[dict[str, Any], None, None]:
        """Stream a chat completion from Ollama.

        Sends a ``POST /api/chat`` request with ``stream: true`` and yields
        each NDJSON chunk as a parsed dictionary.  Token content appears in
        ``chunk["message"]["content"]`` for most chunks.  Tool calls
        typically appear in the final chunk (``done: true``), but callers
        should accumulate them across chunks for robustness.

        Args:
            model: Ollama model name (e.g. ``qwen3:8b``).
            messages: Conversation messages list.
            tools: Optional list of tool definitions in Ollama format.
            options: Optional dict of inference parameters (e.g.
                ``{"num_ctx": 8192, "temperature": 0.6}``).  Passed as
                the nested ``options`` key in the Ollama request body.
                When *None*, a default of ``{"num_ctx": 8192}`` is used.
            think: Optional flag to enable thinking mode (e.g. for Qwen3).
                Sent as a top-level ``think`` key in the request body.
            format: Optional response format specification (e.g. ``"json"``
                or a JSON schema dict).  Sent as a top-level ``format`` key.
            keep_alive: Optional duration to keep the model loaded (e.g.
                ``"5m"`` or ``300``).  Sent as a top-level ``keep_alive`` key.

        Yields:
            Parsed JSON chunks from the streaming response.

        Raises:
            OllamaConnectionError: On connection failure or timeout.
            OllamaStreamError: If an error is received mid-stream.
            ValueError: If the model name is invalid.
        """
        self._validate_model(model)
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
        # Inference options: use caller-provided options or sensible defaults.
        payload["options"] = options if options is not None else {"num_ctx": 8192}
        if think is not None:
            payload["think"] = think
        if format is not None:
            payload["format"] = format
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive

        yield from self._stream_request(
            "/api/chat", payload, timeout=_STREAM_TIMEOUT,
            **({"should_stop": _should_stop} if _should_stop is not None else {}),
        )

    def chat_stream_cancellable(self, model, messages, *, should_stop, **kwargs):
        """Keep cancellation local to this one inference request."""
        yield from self.chat_stream(model, messages, _should_stop=should_stop, **kwargs)

    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        options: dict[str, Any] | None = None,
        think: bool | None = None,
        format: str | dict[str, Any] | None = None,
        keep_alive: str | int | None = None,
    ) -> dict[str, Any]:
        """Send a non-streaming chat completion request.

        Args:
            model: Ollama model name.
            messages: Conversation messages list.
            tools: Optional list of tool definitions in Ollama format.
            options: Optional dict of inference parameters (e.g.
                ``{"num_ctx": 8192, "temperature": 0.6}``).  Passed as
                the nested ``options`` key in the Ollama request body.
                When *None*, a default of ``{"num_ctx": 8192}`` is used.
            think: Optional flag to enable thinking mode (e.g. for Qwen3).
                Sent as a top-level ``think`` key in the request body.
            format: Optional response format specification (e.g. ``"json"``
                or a JSON schema dict).  Sent as a top-level ``format`` key.
            keep_alive: Optional duration to keep the model loaded (e.g.
                ``"5m"`` or ``300``).  Sent as a top-level ``keep_alive`` key.

        Returns:
            The full response dict from Ollama.

        Raises:
            OllamaConnectionError: On connection failure or timeout.
            OllamaRequestError: On error response.
            ValueError: If the model name is invalid.
        """
        self._validate_model(model)
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        # Inference options: use caller-provided options or sensible defaults.
        payload["options"] = options if options is not None else {"num_ctx": 8192}
        if think is not None:
            payload["think"] = think
        if format is not None:
            payload["format"] = format
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive

        return self._request("POST", "/api/chat", data=payload, timeout=_STREAM_TIMEOUT)

    def generate_stream(
        self,
        model: str,
        prompt: str,
        **kwargs: Any,
    ) -> Generator[dict[str, Any], None, None]:
        """Stream a raw text generation from Ollama.

        Sends a ``POST /api/generate`` request with ``stream: true`` and
        yields each NDJSON chunk as a parsed dictionary.  Token content
        appears in ``chunk["response"]`` for most chunks.

        This is useful for single-shot generation without chat context
        (e.g. ideation mode).

        Args:
            model: Ollama model name (e.g. ``qwen3:8b``).
            prompt: The prompt string for generation.
            **kwargs: Additional parameters forwarded to the Ollama API
                (e.g. ``think=True``, ``keep_alive="5m"``).

        Yields:
            Parsed JSON chunks from the streaming response.

        Raises:
            OllamaConnectionError: On connection failure or timeout.
            OllamaStreamError: If an error is received mid-stream.
            ValueError: If the model name is invalid.
        """
        self._validate_model(model)
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            **kwargs,
        }
        yield from self._stream_request(
            "/api/generate", payload, timeout=_STREAM_TIMEOUT
        )

    def embed(
        self,
        model: str,
        input: str | list[str],
    ) -> list[list[float]]:
        """Generate embeddings using Ollama.

        Args:
            model: Embedding model name (e.g. ``all-minilm``).
            input: A single string or list of strings to embed.

        Returns:
            A list of embedding vectors (each a list of floats).

        Raises:
            OllamaConnectionError: On connection failure or timeout.
            OllamaRequestError: On error response.
            ValueError: If the model name is invalid.
        """
        self._validate_model(model)
        payload: dict[str, Any] = {
            "model": model,
            "input": input,
        }
        result = self._request("POST", "/api/embed", data=payload)
        return result.get("embeddings", [])

    def pull_model(
        self,
        model: str,
    ) -> Generator[dict[str, Any], None, None]:
        """Pull (download) a model from the Ollama registry.

        Streams progress updates as NDJSON chunks.  Each chunk typically
        contains ``status`` and may include ``completed`` / ``total`` byte
        counts for download progress.

        Args:
            model: Model name to pull (e.g. ``qwen3:8b``).

        Yields:
            Progress update dicts from the streaming response.

        Raises:
            OllamaConnectionError: On connection failure.
            OllamaStreamError: If an error is received mid-stream.
            ValueError: If the model name is invalid.
        """
        self._validate_model(model)
        payload: dict[str, Any] = {
            "model": model,
            "stream": True,
        }
        # Model pulls can take a very long time; use a generous timeout
        # for the initial connection but rely on the streaming keep-alive
        # for ongoing progress.
        yield from self._stream_request(
            "/api/pull", payload, timeout=_STREAM_TIMEOUT
        )

    def show_model(self, model: str, *, timeout=None) -> dict[str, Any]:
        """Show detailed information about a model.

        Calls ``POST /api/show`` to retrieve model metadata including
        template, parameters, license, and capabilities.

        Args:
            model: Model name to inspect (e.g. ``qwen3:8b``).

        Returns:
            A dict with model details.  Typically includes keys such as
            ``modelfile``, ``parameters``, ``template``, ``details``,
            and ``capabilities`` (if the model advertises them).

        Raises:
            OllamaConnectionError: On connection failure.
            OllamaRequestError: On error response.
            ValueError: If the model name is invalid.
        """
        self._validate_model(model)
        payload: dict[str, Any] = {"model": model}
        return self._request("POST", "/api/show", data=payload, **({"timeout":timeout} if timeout is not None else {}))

    def list_running_models(self) -> list[dict[str, Any]]:
        """List models currently loaded in VRAM.

        Calls ``GET /api/ps`` to retrieve information about models that
        are currently loaded and ready for inference.

        Returns:
            A list of running model info dicts from the ``models`` key.

        Raises:
            OllamaConnectionError: On connection failure.
            OllamaRequestError: On error response.
        """
        result = self._request("GET", "/api/ps")
        return result.get("models", [])

    def delete_model(self, model: str) -> None:
        """Delete a model from Ollama.

        Calls ``DELETE /api/delete`` with a JSON body.  The API returns
        HTTP 200 with no JSON body on success.

        Args:
            model: Model name to delete (e.g. ``phi4-mini``).

        Raises:
            OllamaConnectionError: On connection failure.
            OllamaRequestError: On error response (e.g. model not found).
            ValueError: If the model name is invalid.
        """
        self._validate_model(model)
        payload: dict[str, Any] = {"model": model}
        self._request_no_content("DELETE", "/api/delete", data=payload)

    def copy_model(self, source: str, destination: str) -> None:
        """Copy a model to a new name.

        Calls ``POST /api/copy`` with source and destination names.
        The API returns HTTP 200 with no JSON body on success.

        Args:
            source: Source model name.
            destination: Destination model name.

        Raises:
            OllamaConnectionError: On connection failure.
            OllamaRequestError: On error response (e.g. source not found).
            ValueError: If either model name is invalid.
        """
        self._validate_model(source)
        self._validate_model(destination)
        payload: dict[str, Any] = {
            "source": source,
            "destination": destination,
        }
        self._request_no_content("POST", "/api/copy", data=payload)

    def create_model(
        self,
        name: str,
        from_model: str | None = None,
        modelfile: str | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Create a new model or variant.

        Calls ``POST /api/create`` with streaming progress updates.  At
        least one of *from_model* or *modelfile* must be provided.

        Args:
            name: Name for the new model.
            from_model: Base model to derive from (Ollama API ``from``
                parameter).
            modelfile: Full Modelfile content as a string.

        Yields:
            Progress update dicts from the streaming response.

        Raises:
            OllamaConnectionError: On connection failure.
            OllamaStreamError: If an error is received mid-stream.
            ValueError: If the model name is invalid, or if neither
                *from_model* nor *modelfile* is provided.
        """
        self._validate_model(name)
        if from_model is not None:
            self._validate_model(from_model)

        if from_model is None and modelfile is None:
            raise ValueError(
                "At least one of 'from_model' or 'modelfile' must be provided"
            )

        payload: dict[str, Any] = {
            "model": name,
            "stream": True,
        }
        if from_model is not None:
            payload["from"] = from_model
        if modelfile is not None:
            payload["modelfile"] = modelfile

        yield from self._stream_request(
            "/api/create", payload, timeout=_STREAM_TIMEOUT
        )
