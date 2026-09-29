"""Text input/output adapter for the one-session Application API."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import Any, Callable

from local_cli.application.commands import ApplicationCommand, CommandKind, CommandReceipt
from local_cli.application.events import SubscriptionOutOfSync
from local_cli.core.contracts import EventKind, new_command_id


_TURN_TERMINALS = frozenset((EventKind.TURN_COMPLETED, EventKind.TURN_CANCELLED,
                             EventKind.TURN_FAILED))
_OPERATION_TERMINALS = frozenset((EventKind.OPERATION_COMPLETED,
                                  EventKind.OPERATION_CANCELLED,
                                  EventKind.OPERATION_FAILED,
                                  EventKind.OPERATION_OUTCOME_UNKNOWN))


def _stdout(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def render_ideation_delta(kind: str, text: str) -> None:
    if kind == "thinking":
        for line in text.splitlines(keepends=True):
            _stdout(f"> {line}")
    else:
        _stdout(text)


@dataclass(frozen=True)
class CliWaitOutcome:
    """Adapter view of canonical state; never a reconstructed domain event."""
    status: str
    payload: dict[str, Any]
    recovered_from_snapshot: bool = False


class CliApplicationClient:
    """A CLI projection; it never constructs tools, providers or Turns itself."""

    def __init__(self, application: Any, session_id: str, *,
                 write: Callable[[str], Any] | None = None,
                 write_error: Callable[[str], Any] | None = None,
                 read: Callable[[str], str] | None = None,
                 on_event: Callable[[Any], Any] | None = None,
                 on_command: Callable[[CommandKind, dict[str, Any], CommandReceipt], Any] | None = None,
                 on_submit: Callable[[str], Any] | None = None,
                 on_turn_complete: Callable[[bool], Any] | None = None) -> None:
        self.application = application
        self.session_id = session_id
        self._write = write or _stdout
        self._write_error = write_error or sys.stderr.write
        self._read = read or input
        self._on_event = on_event or (lambda _event: None)
        self._on_command = on_command or (lambda _kind, _payload, _receipt: None)
        self._on_submit = on_submit or (lambda _content: None)
        self._on_turn_complete = on_turn_complete or (lambda _error: None)
        state = application.get_snapshot(session_id)
        self._cursor = application.subscribe_events(
            session_id, after_sequence=state.last_sequence,
            include_internal=True)

    def close(self) -> None:
        self._cursor._stream.close(self._cursor)

    def snapshot(self):
        return self.application.get_snapshot(self.session_id)

    def execute_auxiliary(self, name: str, arguments: dict[str, Any] | None = None):
        return self.application.execute_auxiliary(self.session_id, name, arguments or {})

    def command(self, kind: CommandKind, payload: dict[str, Any] | None = None,
                *, command_id: str | None = None) -> CommandReceipt:
        command_payload = payload or {}
        receipt = self.application.handle(ApplicationCommand(
            command_id=command_id or new_command_id(), kind=kind,
            payload=command_payload, session_id=self.session_id))
        if isinstance(receipt, CommandReceipt):
            self._on_command(kind, command_payload, receipt)
        return receipt

    def submit_user_input(self, content: str) -> CommandReceipt:
        self._on_submit(content)
        receipt = self.command(CommandKind.SUBMIT_USER_INPUT, {"content": content})
        if not receipt.accepted:
            self._write(f"{receipt.error.code}: {receipt.error.safe_message}\n")
            self._on_turn_complete(True)
            return receipt
        turn_id = receipt.created_ids["turnId"]
        try:
            terminal = self._wait_for_terminal(turn_id, turn=True)
        except KeyboardInterrupt:
            # Ctrl+C requests cancellation; it is not itself a terminal.
            self.command(CommandKind.CANCEL_TURN, {"turnId": turn_id})
            terminal = self._wait_for_terminal(turn_id, turn=True)
        self._on_turn_complete(terminal.status != "completed")
        return receipt

    def wait_for_operation(self, operation_id: str) -> Any:
        return self._wait_for_terminal(operation_id, turn=False)

    def _poll(self):
        try:
            return self.application.poll_events(self._cursor)
        except SubscriptionOutOfSync:
            # A local terminal client can re-subscribe from its last cursor.
            # Expired replay is represented explicitly by EventGap + snapshot.
            position = self._cursor.position
            self._cursor = self.application.subscribe_events(
                self.session_id, after_sequence=position,
                include_internal=True)
            return self.application.poll_events(self._cursor)

    def _wait_for_terminal(self, target_id: str, *, turn: bool) -> Any:
        while True:
            events = self._poll()
            for event in events:
                self._render(event)
                if turn and event.turn_id == target_id and event.kind in _TURN_TERMINALS:
                    if event.kind is EventKind.TURN_FAILED:
                        self._write(f"Error: {event.payload.get('errorCode', 'Turn failed')}\n")
                    elif event.kind is EventKind.TURN_CANCELLED:
                        self._write("\nInterrupted.\n")
                    else:
                        self._write("\n")
                    return CliWaitOutcome(event.payload["status"], dict(event.payload))
                if (not turn and event.operation_id == target_id
                        and event.kind in _OPERATION_TERMINALS):
                    return CliWaitOutcome(event.payload["status"], dict(event.payload))
                if event.kind is EventKind.SESSION_SNAPSHOT:
                    state = event.payload
                    entries = (state.get("turns", ()) if turn else
                               state.get("services", {}).get("operations", ()))
                    key = "turnId" if turn else "operationId"
                    item = next((entry for entry in entries
                                 if entry.get(key) == target_id), None)
                    if item is not None and item.get("status") in (
                            "completed", "failed", "cancelled", "outcome_unknown"):
                        if turn and item.get("finalContent"):
                            self._write(f"\n{item['finalContent']}\n")
                        return CliWaitOutcome(item["status"], dict(item), True)
            time.sleep(0.02)

    def _render(self, event) -> None:
        self._on_event(event)
        if event.kind is EventKind.ASSISTANT_DELTA:
            self._write(event.payload["text"])
        elif event.kind is EventKind.THINKING_DELTA:
            for line in event.payload["text"].splitlines(keepends=True):
                self._write(f"> {line}")
        elif event.kind is EventKind.LEGACY_AGENT_EVENT:
            kind, data = event.payload["legacyKind"], event.payload["data"]
            if kind == "tool_result":
                if data.get("unknown"):
                    self._write_error(f"  Unknown tool: {data['tool_name']}\n")
                else:
                    preview = str(data.get("result", "")).replace("\n", " ").strip()
                    self._write_error(f"  Result: {preview[:200]}{'...' if len(preview) > 200 else ''}\n")
            elif kind == "error":
                self._write_error(f"{data.get('message', 'Tool error')}\n")
            elif kind == "debug":
                self._write_error(str(data.get("text", "")) + "\n")
        elif event.kind is EventKind.HARNESS_INTERVENTION:
            rule = event.payload.get("rule")
            if rule not in ("context_budget", "context_usage"):
                self._write_error(f"  [harness] {rule}\n")
        elif event.kind is EventKind.OPERATION_PROGRESS:
            self._write(f"RAG {event.payload.get('action', '')}: {event.payload.get('phase', '')}\n")
        elif event.kind is EventKind.APPROVAL_REQUIRED:
            arguments = event.payload["arguments"]
            try:
                answer = self._read(f"\nAllow command '{arguments.get('command', '')}'? [y/N] ")
            except (EOFError, KeyboardInterrupt):
                answer = ""
            approved = answer.strip().lower() in ("y", "yes", "s", "sí")
            self.command(CommandKind.RESOLVE_APPROVAL, {
                "approvalId": event.approval_id,
                "toolCallId": event.tool_call_id,
                "requestDigest": event.payload["requestDigest"],
                "cwd": event.payload["cwd"],
                "policyRevision": event.payload["policyRevision"],
                "approved": approved,
            })
        elif event.kind is EventKind.USER_INPUT_REQUIRED:
            try:
                answer = self._read(f"\n{event.payload['question']}\n> ")
            except (EOFError, KeyboardInterrupt):
                answer = ""
            self.command(CommandKind.RESOLVE_USER_INPUT, {
                "inputRequestId": event.payload["inputRequestId"],
                "response": answer,
            })
        elif event.kind is EventKind.EVENT_GAP:
            self._write("\nEvent history expired; continuing from the current session snapshot.\n")
