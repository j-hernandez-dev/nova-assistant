"""Temporary composition of common interactions for the legacy CLI/JSONL loop.

This bridge does not replace the session coordinator. It lets the existing
interfaces act as response adapters to the same gates and tool runtime while
their remaining orchestration is migrated in later phases.
"""

from datetime import datetime, timezone
from pathlib import Path
from threading import Event, RLock
from typing import Callable, Mapping

from local_cli.application.cancellation import CancellationController
from local_cli.application.interactions import ApprovalGate, UserInputGate
from local_cli.application.tool_runtime import LegacyToolAdapter, ToolRegistry, ToolRuntime
from local_cli.core.contracts import (
    ExecutionContext, RuntimeCapabilitySnapshot, new_operation_id,
    new_session_id, new_turn_id,
)
from local_cli.security import get_sanitized_env
from local_cli.tools.base import Tool
from local_cli.tools.shell_tool import ShellTool


class _StopToken:
    def __init__(self, should_stop: Callable[[], bool]) -> None:
        self._should_stop = should_stop

    def is_cancel_requested(self) -> bool:
        return self._should_stop()


class LegacyInteractionBridge:
    def __init__(self, tools: list[Tool], *, cwd: Path,
                 environment: Mapping[str, str] | None = None,
                 should_stop: Callable[[], bool] | None = None,
                 deadline_factory: Callable[[], datetime | None] | None = None,
                 auto_approve: bool = False,
                 provider_revision: int | None = None,
                 capabilities: RuntimeCapabilitySnapshot | None = None) -> None:
        shell = next((tool for tool in tools if isinstance(tool, ShellTool)), None)
        ask = next((tool for tool in tools if tool.name == "ask_user"), None)
        token = self._cancellation = CancellationController(
            _StopToken(should_stop or (lambda: False)))
        self._lock = RLock()
        self._children: dict[str, Event] = {}
        self.has_unknown_effect = False
        session_id, turn_id = new_session_id(), new_turn_id()
        environment = dict(environment if environment is not None else
                           shell.environment if shell is not None else get_sanitized_env())
        capability = capabilities or RuntimeCapabilitySnapshot(
            captured_at=datetime.now(timezone.utc), source="legacy_interaction_unprobed")

        def confirm(request) -> None:
            callback = shell._confirm if shell is not None else None
            approved = bool(callback(request.arguments["command"])) if callback else False
            self.approval_gate.resolve(
                request.session_id, request.approval_id, request.tool_call_id,
                request.request_digest, cwd=request.cwd,
                policy_revision=request.policy_revision, approved=approved,
            )

        def answer(request) -> None:
            responder = getattr(ask, "_responder", None)
            if responder is None:
                raise EOFError("no interface input adapter")
            self.user_input_gate.resolve(request.session_id, request.input_request_id,
                                         responder(request.question))

        self.approval_gate = ApprovalGate(on_required=confirm)
        self.user_input_gate = UserInputGate(on_required=answer)
        self.runtime = ToolRuntime(
            ToolRegistry(tools), approval_gate=self.approval_gate,
            user_input_gate=self.user_input_gate, auto_approve=auto_approve,
            on_agent_started=self._agent_started,
            on_agent_completed=self._agent_completed,
            publish=self._tool_event,
        )

        def context() -> ExecutionContext:
            return ExecutionContext(
                workspace=cwd, cwd=cwd, environment=environment,
                session_id=session_id, turn_id=turn_id,
                operation_id=new_operation_id(), cancellation_token=token.child(),
                deadline=deadline_factory() if deadline_factory else None,
                capabilities=capability, policy_revision=1,
                provider_revision=provider_revision,
            )

        self.tools = [LegacyToolAdapter(tool, self.runtime, context) for tool in tools]

    def _tool_event(self, event) -> None:
        result = event[2]
        if result is not None and result.operation_outcome.value == "outcome_unknown":
            with self._lock:
                self.has_unknown_effect = True

    def _agent_started(self, _agent, operation_id, _context, _runner) -> None:
        with self._lock:
            self._children[operation_id] = Event()

    def _agent_completed(self, result, operation_id, _context) -> None:
        with self._lock:
            if result.status in ("timeout", "outcome_unknown"):
                self.has_unknown_effect = True
            self._children[operation_id].set()

    def cancel(self) -> None:
        self._cancellation.request()

    def wait_for_children(self) -> None:
        with self._lock:
            children = tuple(self._children.values())
        for child in children:
            child.wait()
