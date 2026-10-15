"""Compatibility adapter preserving the existing loop and harness."""

from __future__ import annotations

from typing import Any, Callable

from local_cli.agent import run_agent
from local_cli.core.contracts import TurnStatus
from local_cli.core.runtime import TurnOutcome
from local_cli.harness import HarnessConfig


class LegacyAgentRuntime:
    def __init__(self, run_agent_fn: Callable[..., str] = run_agent,
                 harness: HarnessConfig | None = None, *,
                 cache: Any = None, tracker: Any = None) -> None:
        self._run_agent = run_agent_fn
        self._harness = harness
        self._cache = cache
        self._tracker = tracker

    def run_turn(self, *, provider: Any, model: str, tools: list[Any],
                 messages: list[dict[str, Any]],
                 emit: Callable[[Any], None],
                 should_stop: Callable[[], bool] | None = None) -> TurnOutcome:
        try:
            options = {} if self._harness is None else {"harness": self._harness}
            if should_stop is not None:
                options["should_stop"] = should_stop
            if self._cache is not None:
                options["cache"] = self._cache
            if self._tracker is not None:
                options["tracker"] = self._tracker
            final = self._run_agent(provider, model, tools, messages,
                                    emit=emit, raise_provider_errors=True,
                                    **options)
        except Exception as exc:
            # The type is safe to expose; provider details/credentials are not.
            return TurnOutcome(TurnStatus.FAILED, error_code=getattr(exc, "code", type(exc).__name__))
        return TurnOutcome(TurnStatus.COMPLETED, final_content=final)
