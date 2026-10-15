"""Phase-4 runtime boundary; the legacy agent loop is an adapter of it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from local_cli.core.contracts import TurnStatus


@dataclass(frozen=True)
class TurnOutcome:
    status: TurnStatus
    final_content: str = ""
    error_code: str | None = None

    def __post_init__(self) -> None:
        if (not isinstance(self.status, TurnStatus) or
                self.status not in (TurnStatus.COMPLETED, TurnStatus.CANCELLED,
                                    TurnStatus.FAILED)):
            raise ValueError("runtime outcome must be terminal")


class AgentRuntimePort(Protocol):
    """Application depends on this contract, not on a frontend."""

    def run_turn(self, *, provider: Any, model: str, tools: list[Any],
                 messages: list[dict[str, Any]],
                 emit: Callable[[Any], None],
                 should_stop: Callable[[], bool] | None = None) -> TurnOutcome: ...
