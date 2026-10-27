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
                 on_turn_complete: Callable[[bool], Any] | None = None,
                 debug: bool = False) -> None:
        self.application = application
        self.session_id = session_id
        self._write = write or _stdout
        self._write_error = write_error or sys.stderr.write
        self._read = read or input
        self._debug = debug
        self._turn_text = {}
        self._generation_text = {}
        self._working_turns = set()
        self._seen_events = set()
        self._on_event = on_event or (lambda _event: None)
        self._on_command = on_command or (lambda _kind, _payload, _receipt: None)
        self._on_submit = on_submit or (lambda _content: None)
        self._on_turn_complete = on_turn_complete or (lambda _error: None)
        self._approval_actor = application.register_approval_actor(
            'cli_tty', self._human_tty)
        self._memory_closed = False
        browser_register = getattr(application, 'register_browser_actor', None)
        self._browser_actor = browser_register('cli_tty', lambda: not self._memory_closed and self._human_tty()) if browser_register else None
        self._memory_actor = application.register_memory_actor('cli_tty',
            lambda: not self._memory_closed and self._human_tty())
        register = getattr(application, 'register_knowledge_actor', None)
        self._knowledge_actor = register('cli_tty', lambda: not self._memory_closed and self._human_tty()) if register else None
        self._attachment_refs = []
        state = application.get_snapshot(session_id)
        self._cursor = application.subscribe_events(
            session_id, after_sequence=state.last_sequence,
            include_internal=True)

    @staticmethod
    def _human_tty() -> bool:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())

    def close(self) -> None:
        self._memory_closed = True
        self._cursor._stream.close(self._cursor)
        close = getattr(self.application, 'close_knowledge', None)
        if close: close()
        close_browser = getattr(self.application, 'close_browser', None)
        if close_browser: close_browser()

    def snapshot(self):
        return self.application.get_snapshot(self.session_id)

    def execute_auxiliary(self, name: str, arguments: dict[str, Any] | None = None):
        return self.application.execute_auxiliary(self.session_id, name, arguments or {})

    def memory(self, name, arguments=None, *, command_id=None):
        from local_cli.application.memory import MemoryCommand
        snapshot=self.snapshot()
        return self.application.execute_memory(MemoryCommand(command_id or new_command_id(),
            self.session_id,name,arguments or {},snapshot.state_revision),actor=self._memory_actor)

    def knowledge(self, name, arguments=None, *, command_id=None):
        from local_cli.application.knowledge_host import KnowledgeCommand
        return self.application.execute_knowledge(KnowledgeCommand(command_id or new_command_id(),
            self.session_id,name,arguments or {},self.snapshot().state_revision),actor=self._knowledge_actor)

    def command(self, kind: CommandKind, payload: dict[str, Any] | None = None,
                *, command_id: str | None = None) -> CommandReceipt:
        command_payload = payload or {}
        receipt = self.application.handle(ApplicationCommand(
            command_id=command_id or new_command_id(), kind=kind,
            payload=command_payload, session_id=self.session_id,
            approval_actor=self._approval_actor if kind is CommandKind.RESOLVE_APPROVAL else self._browser_actor if kind is CommandKind.BROWSER_CONTROL else None))
        if isinstance(receipt, CommandReceipt):
            self._on_command(kind, command_payload, receipt)
        return receipt

    def submit_user_input(self, content: str, *, attachment_refs=None) -> CommandReceipt:
        self._on_submit(content)
        refs = self._attachment_refs if attachment_refs is None else attachment_refs
        receipt = self.command(CommandKind.SUBMIT_USER_INPUT, {"content": content,
            **({'attachmentRefs': refs} if refs else {})})
        if receipt.accepted: self._attachment_refs = []
        if not receipt.accepted:
            self._write((f"{receipt.error.code}: " if self._debug else '') + f"{receipt.error.safe_message}\n")
            self._on_turn_complete(True)
            return receipt
        turn_id = receipt.created_ids["turnId"]
        try:
            terminal = self._wait_for_terminal(turn_id, turn=True)
        except KeyboardInterrupt:
            # Ctrl+C requests cancellation; it is not itself a terminal.
            try:
                self.command(CommandKind.CANCEL_TURN, {"turnId": turn_id})
                terminal = self._wait_for_terminal(turn_id, turn=True)
            except KeyboardInterrupt:
                self._write("\nCancellation is still pending. The turn and any effects are not confirmed stopped.\n")
                self._on_turn_complete(True)
                return receipt
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
                    final = event.payload.get('finalContent', '')
                    if not final:
                        # Runtime ports may return a final answer without deltas.
                        # The Application snapshot remains the source of truth.
                        state = self.snapshot()
                        item = next((entry for entry in getattr(state, 'turns', ())
                                     if entry.get('turnId') == target_id), {})
                        final = item.get('finalContent', '')
                    self._final_once(target_id, final)
                    self._terminal_status(event.payload)
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
                        if turn:
                            self._final_once(target_id, item.get('finalContent', ''))
                            self._terminal_status(item)
                        return CliWaitOutcome(item["status"], dict(item), True)
            time.sleep(0.02)

    def _terminal_status(self, payload):
        if payload['status'] == 'failed':
            self._write(f"Error: {payload.get('errorCode') or 'Turn failed'}\n" if self._debug else
                        'The turn could not complete. Any unconfirmed effects remain unconfirmed.\n')
        elif payload['status'] == 'cancelled':
            self._write("\nInterrupted.\n")
        else:
            self._write("\n")

    def _final_once(self, turn_id, text):
        printed = self._turn_text.get(turn_id, '')
        if not text or printed.rstrip().endswith(text.rstrip()):
            return
        generation = getattr(self, '_generation_text', {}).get(turn_id, printed)
        missing = text[len(generation):] if generation and text.startswith(generation) else text
        self._write(missing)
        self._turn_text[turn_id] = printed + missing

    def _render(self, event) -> None:
        event_id = getattr(event, 'event_id', None)
        seen = getattr(self, '_seen_events', None)
        if event_id and seen is not None:
            if event_id in seen: return
            if len(seen) >= 4096: seen.clear()
            seen.add(event_id)
        self._on_event(event)
        if event.payload.get('securityAudit', {}).get('gap'):
            self._write_error('Warning: SECURITY_AUDIT_DELIVERY_FAILED; audit gap. Observed result retained; no retry/rollback.\n')
        if event.kind is EventKind.GENERATION_STARTED:
            if not hasattr(self, '_generation_text'): self._generation_text = {}
            self._generation_text[getattr(event, 'turn_id', None)] = ''
            working = getattr(self, '_working_turns', set())
            turn = getattr(event, 'turn_id', None)
            if not self._debug and turn not in working:
                self._write_error('Working…\n')
                if len(working) >= 1024: working.clear()
                working.add(turn)
                self._working_turns = working
        elif event.kind is EventKind.ASSISTANT_DELTA:
            self._write(event.payload["text"])
            if hasattr(self, '_turn_text'):
                turn = getattr(event, 'turn_id', None)
                self._turn_text[turn] = self._turn_text.get(turn, '') + event.payload['text']
                if not hasattr(self, '_generation_text'): self._generation_text = {}
                self._generation_text[turn] = self._generation_text.get(turn, '') + event.payload['text']
        elif event.kind is EventKind.THINKING_DELTA:
            if getattr(self, '_debug', False):
                for line in event.payload["text"].splitlines(keepends=True): self._write(f"> {line}")
        elif event.kind is EventKind.TOOL_REQUESTED:
            if not self._debug:
                from local_cli.application.browser_ux import PROGRESS
                name = event.payload.get('name', '')
                label = PROGRESS.get(name)
                if label: self._write_error(label + '\n')
        elif event.kind is EventKind.LEGACY_AGENT_EVENT:
            kind, data = event.payload["legacyKind"], event.payload["data"]
            if not self._debug: return  # Canonical results remain in audit/backend/model context.
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
            if rule == 'memory_recall':
                if event.payload.get('errorCode'):
                    mode=event.payload.get('retrievalMode','none')
                    continuing=f'with {mode} recall' if mode!='none' else 'without recall'
                    self._write_error(f"  [memory] {event.payload['errorCode']}; continuing {continuing}.\n" if self._debug else
                                      'Memory recall is unavailable; continuing without it.\n')
            elif self._debug and rule not in ("context_budget", "context_usage"):
                self._write_error(f"  [harness] {rule}\n")
        elif event.kind is EventKind.OPERATION_PROGRESS:
            self._write(f"RAG {event.payload.get('action', '')}: {event.payload.get('phase', '')}\n")
        elif event.kind is EventKind.APPROVAL_REQUIRED:
            if event.payload.get('arguments', {}).get('environment'):
                import json
                self._write('Environment: ' + json.dumps(
                    dict(event.payload['arguments']['environment']), ensure_ascii=False) + '\n')
            arguments = event.payload["arguments"]
            try:
                name = event.payload.get('name', '')
                if name.startswith('browser_') and not self._debug:
                    target = arguments.get('pageLabel') or arguments.get('origin') or 'the current page'
                    detail = (str(arguments.get('fileName', 'the selected file')) + ' to ' + target if name == 'browser_upload' else
                              arguments.get('url', '') if name == 'browser_download' else target)
                    label = {'browser_upload': 'file upload', 'browser_download': 'file download',
                             'browser_click': 'page click', 'browser_type': 'text disclosure',
                             'browser_press_key': 'page key press'}.get(name, 'browser action')
                    prompt = f'\nAllow {label}: {detail}? [y/N] '
                else:
                    operation = ('Launch applications and keep them open with your account permissions'
                                 if arguments.get('keep_open') else 'Run with your account permissions')
                    prompt = (f"\nAllow {name} with {arguments}? [y/N] " if name.startswith('browser_') else
                          f"\n{operation} in {event.payload['cwd']}: "
                          f"'{arguments.get('command', '')}'? [y/N] ")
                answer = (self._read(prompt)
                          if self._human_tty() else '')
            except (EOFError, KeyboardInterrupt):
                answer = ""
            approved = self._human_tty() and answer.strip().lower() in ("y", "yes", "s", "sí")
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
