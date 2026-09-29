"""Adapt the existing ideation history to provider-neutral, sink-based output.

This preserves the isolated legacy brainstorming workflow. It creates no
additional chat or AgentSession and never writes to process stdout/stderr.
"""

from __future__ import annotations

from typing import Any, Callable

from local_cli.providers.base import ProviderRequestError


class LegacyIdeationAdapter:
    def __init__(self, history: Any, inference: Callable[..., Any], *,
                 output: Callable[[str, str], None] | None = None) -> None:
        self._history, self._inference = history, inference
        self._output = output or (lambda _kind, _text: None)

    @property
    def has_session(self) -> bool:
        return self._history.has_session

    def start_session(self) -> None:
        self._history.start_session()

    def clear_history(self) -> None:
        self._history.clear_history()

    def _collect(self, messages: list[dict[str, Any]], *, think: bool | None) -> str:
        parts = []
        try:
            stream = self._inference(messages, think=think)
            for chunk in stream:
                message = chunk.get("message", {})
                for kind in ("thinking", "content"):
                    text = message.get(kind, "")
                    if text:
                        self._output(kind, text)
                        if kind == "content":
                            parts.append(text)
        except ProviderRequestError:
            # Retry a rejected thinking option only before any visible output.
            if think is not None and not parts:
                return self._collect(messages, think=None)
            raise
        return "".join(parts)

    def chat_turn(self, *, user_input: str, model: str) -> str:
        if not self.has_session:
            self.start_session()
        messages = self._history.get_history()
        messages.append({"role": "user", "content": user_input})
        try:
            content = self._collect(messages, think=True)
        except BaseException:
            messages.pop()
            raise
        messages.append({"role": "assistant", "content": content})
        return content

    def single_shot(self, *, prompt: str, model: str) -> str:
        # A private prompt without tools works across the active providers;
        # an Ollama-only /api/generate client would retain a stale provider.
        return self._collect([{"role": "user", "content": prompt}], think=None)
