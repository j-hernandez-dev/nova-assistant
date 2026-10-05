"""S0 observations, updated for intentional S2 frontend behavior changes.

All execution is mocked. Historical S0 evidence remains unchanged. Binding
tests explicitly use the low-level gate without actor checking; S2 tests
exercise the production gate and human provenance.
"""

import ast
from contextlib import contextmanager
from dataclasses import fields, replace
from datetime import datetime, timedelta, timezone
import io
from pathlib import Path
import re
import subprocess
import sys
from threading import Event, Thread
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import local_cli
from local_cli.application.cancellation import CancellationController
from local_cli.application.commands import ApplicationCommand, CommandKind, CommandReceipt
from local_cli.application.interactions import ApprovalGate, InteractionError, UserInputGate
from local_cli.application.tool_runtime import ToolPolicyAction, ToolRegistry, ToolRuntime
from local_cli.cli import build_parser
from local_cli.core.contracts import (
    EffectState, EventEnvelope, EventKind, ExecutionContext,
    RuntimeCapabilitySnapshot, ToolInvocation, ToolStatus, Visibility,
    new_command_id, new_event_id, new_operation_id, new_session_id,
    new_tool_call_id, new_turn_id,
)
from local_cli.interfaces.cli_application import CliApplicationClient
from local_cli.interfaces.jsonl_application import JsonlApplicationAdapter
from local_cli.shell_executor import ShellDescriptor
from local_cli.tools.ask_user_tool import AskUserTool
from local_cli.tools.bash_tool import BashTool
from tests.security_v12.process_fixtures import bind_mock_shell


REPO_ROOT = Path(local_cli.__file__).resolve().parents[1]
RISKY = "Remove-Item .\\s0-fixture -Recurse"
BLOCKED = "Invoke-Expression $s0_fixture"


def _shell(tmp_path):
    executor = Mock()
    executor.run.return_value = subprocess.CompletedProcess([], 0, "s0-mock\n", "")
    shell = BashTool(
        descriptor=ShellDescriptor("Windows", "powershell", "s0-unused-pwsh", "mock"),
        executor=executor, cwd=tmp_path, environment={},
    )
    bind_mock_shell(shell, executor)
    return shell, executor


def _invocation(tmp_path, *, name="bash", arguments=None, session_id=None,
                turn_id=None, deadline=None):
    operation_id = new_operation_id()
    context = ExecutionContext(
        workspace=tmp_path, cwd=tmp_path, environment={},
        session_id=session_id or new_session_id(), turn_id=turn_id or new_turn_id(),
        operation_id=operation_id, cancellation_token=CancellationController(),
        deadline=deadline,
        capabilities=RuntimeCapabilitySnapshot(
            captured_at=datetime.now(timezone.utc), source="security_v12_s0_mock"),
        policy_revision=1,
    )
    return ToolInvocation(
        name=name, arguments=arguments if arguments is not None else {"command": RISKY},
        tool_call_id=new_tool_call_id(), operation_id=operation_id, context=context,
    )


def _response(request, approved=True):
    return dict(
        session_id=request.session_id, approval_id=request.approval_id,
        tool_call_id=request.tool_call_id, request_digest=request.request_digest,
        cwd=request.cwd, policy_revision=request.policy_revision, approved=approved,
    )


@contextmanager
def _pending_shell(tmp_path, *, deadline=None):
    """Bounded worker with cancellation cleanup, even if an assertion fails."""
    shell, executor = _shell(tmp_path)
    required, resolved, results, errors = [], [], [], []
    available = Event()

    def on_required(request):
        required.append(request)
        available.set()

    gate = ApprovalGate(on_required=on_required,
                        on_resolved=lambda *args: resolved.append(args), require_actor=False)
    runtime = ToolRuntime(ToolRegistry([shell]), approval_gate=gate)
    invocation = _invocation(tmp_path, deadline=deadline)

    def run():
        try:
            results.append(runtime.execute(invocation))
        except BaseException as exc:
            errors.append(exc)

    worker = Thread(target=run, daemon=True, name="security-v12-s0-mock-approval")
    worker.start()
    try:
        assert available.wait(2), "mock approval did not become pending"
        yield SimpleNamespace(
            gate=gate, request=required[0], invocation=invocation,
            runtime=runtime, executor=executor, results=results,
            errors=errors, worker=worker, resolved=resolved,
        )
    finally:
        invocation.context.cancellation_token.request()
        worker.join(2)
        assert not worker.is_alive(), "mock approval worker did not stop"
        assert not errors, errors


def _envelope(request, *, approval):
    payload = (
        {"arguments": dict(request.arguments), "cwd": request.cwd,
         "policyRevision": request.policy_revision, "requestDigest": request.request_digest,
         "deadline": request.deadline.isoformat() if request.deadline else None}
        if approval else
        {"inputRequestId": request.input_request_id, "question": request.question}
    )
    return EventEnvelope(
        schema_version=1, event_id=new_event_id(), sequence=1,
        session_id=request.session_id, timestamp=datetime.now(timezone.utc),
        kind=EventKind.APPROVAL_REQUIRED if approval else EventKind.USER_INPUT_REQUIRED,
        payload=payload, state_revision=0, visibility=Visibility.SENSITIVE,
        turn_id=request.turn_id, operation_id=request.operation_id,
        tool_call_id=request.tool_call_id,
        approval_id=request.approval_id if approval else None,
    )


class _InteractionApplication:
    """Mock outer API; typed commands resolve the real Application gates."""

    def __init__(self, session_id, approval_gate, input_gate=None):
        self.session_id = session_id
        self.approval_gate, self.input_gate = approval_gate, input_gate
        self.commands = []
        self.cursor = Mock()

    def get_snapshot(self, session_id):
        assert session_id == self.session_id
        return SimpleNamespace(last_sequence=0)

    def register_approval_actor(self, kind, verify):
        return self.approval_gate.register_actor(kind, verify)

    def subscribe_events(self, session_id, **kwargs):
        assert session_id == self.session_id
        return self.cursor

    def handle(self, command):
        assert isinstance(command, ApplicationCommand)
        assert command.session_id == self.session_id
        self.commands.append(command)
        payload = command.payload
        if command.kind is CommandKind.RESOLVE_APPROVAL:
            self.approval_gate.resolve(
                command.session_id, payload["approvalId"], payload["toolCallId"],
                payload["requestDigest"], cwd=payload["cwd"],
                policy_revision=payload["policyRevision"], approved=payload["approved"],
                actor=command.approval_actor,
            )
        elif command.kind is CommandKind.RESOLVE_USER_INPUT:
            self.input_gate.resolve(command.session_id, payload["inputRequestId"], payload["response"])
        else:
            raise AssertionError(f"unexpected command {command.kind}")
        return CommandReceipt(command.command_id, True, session_id=command.session_id,
                              state_revision=0)


def _cli_runtime(tmp_path, *, read=None):
    session_id, turn_id = new_session_id(), new_turn_id()
    gate = ApprovalGate(on_required=lambda request: client._render(_envelope(request, approval=True)))
    input_gate = UserInputGate(on_required=lambda request: client._render(_envelope(request, approval=False)))
    app = _InteractionApplication(session_id, gate, input_gate)
    client = CliApplicationClient(app, session_id, read=read, write=lambda _text: None,
                                  write_error=lambda _text: None)
    shell, executor = _shell(tmp_path)
    runtime = ToolRuntime(ToolRegistry([shell, AskUserTool()]), approval_gate=gate,
                          user_input_gate=input_gate)
    return SimpleNamespace(runtime=runtime, client=client, app=app, executor=executor,
                           session_id=session_id, turn_id=turn_id)


def test_yes_does_not_confirm_human_required_actions_or_skip_deny(tmp_path):
    """S2 removes S0's autoapproval bypass."""
    parsed = build_parser().parse_args(["--yes"])
    assert parsed.auto_approve is True
    shell, executor = _shell(tmp_path)
    required = []
    runtime = ToolRuntime(ToolRegistry([shell]), auto_approve=parsed.auto_approve)
    assert runtime.policy_for("bash", {"command": RISKY}).action is ToolPolicyAction.REQUIRE_APPROVAL
    assert runtime.execute(_invocation(tmp_path)).status is ToolStatus.DENIED
    assert required == []
    executor.run.assert_not_called()
    assert runtime.policy_for("bash", {"command": BLOCKED}).action is ToolPolicyAction.DENY
    denied = runtime.execute(_invocation(tmp_path, arguments={"command": BLOCKED}))
    assert denied.status is ToolStatus.DENIED
    assert denied.effect_state is EffectState.NONE
    assert required == []
    executor.run.assert_not_called()


@pytest.mark.parametrize("field", [
    "session_id", "approval_id", "tool_call_id", "request_digest", "cwd", "policy_revision",
])
def test_approval_response_must_match_existing_binding(tmp_path, field):
    with _pending_shell(tmp_path) as pending:
        response = _response(pending.request)
        response[field] = {
            "session_id": new_session_id(), "approval_id": "s0-missing-approval",
            "tool_call_id": new_tool_call_id(), "request_digest": "0" * 64,
            "cwd": str(tmp_path / "s0-other"), "policy_revision": 2,
        }[field]
        with pytest.raises(InteractionError, match="REQUEST_MISMATCH"):
            pending.gate.resolve(**response)
        assert pending.gate.pending() == (pending.request,)
        pending.executor.run.assert_not_called()
        pending.gate.resolve(**_response(pending.request, approved=False))
        pending.worker.join(2)
        assert pending.results[0].status is ToolStatus.DENIED


def test_identical_replay_is_idempotent_and_cannot_repeat_the_effect(tmp_path):
    with _pending_shell(tmp_path) as pending:
        assert pending.gate.resolve(**_response(pending.request)) is True
        pending.worker.join(2)
        assert pending.results[0].status is ToolStatus.COMPLETED
        assert pending.gate.resolve(**_response(pending.request)) is True
        with pytest.raises(InteractionError, match="ALREADY_RESOLVED"):
            pending.gate.resolve(**_response(pending.request, approved=False))
        assert len(pending.resolved) == 1
        assert pending.gate.pending() == ()
        assert pending.runtime.execute(pending.invocation) is pending.results[0]
        with pytest.raises(ValueError, match="IDEMPOTENCY_CONFLICT"):
            pending.runtime.execute(replace(pending.invocation, arguments={"command": "Write-Output changed"}))
        pending.executor.run.assert_called_once()


@pytest.mark.parametrize("reason", ["cancelled", "expired"])
def test_late_positive_response_after_cancel_or_expiry_has_no_effect(tmp_path, monkeypatch, reason):
    deadline = datetime.now(timezone.utc) + timedelta(minutes=1)
    with _pending_shell(tmp_path, deadline=deadline) as pending:
        if reason == "cancelled":
            pending.invocation.context.cancellation_token.request()
        else:
            class ExpiredClock:
                @staticmethod
                def now(_timezone):
                    return deadline + timedelta(seconds=1)

            monkeypatch.setattr("local_cli.application.interactions.datetime", ExpiredClock)
        with pytest.raises(InteractionError, match="ALREADY_RESOLVED"):
            pending.gate.resolve(**_response(pending.request))
        pending.worker.join(2)
        assert pending.results[0].status is ToolStatus.CANCELLED
        assert pending.resolved[0][1:] == (False, reason)
        assert pending.gate.pending() == ()
        pending.executor.run.assert_not_called()


def test_redirected_cli_input_cannot_approve_without_a_tty(tmp_path, monkeypatch):
    """S2 closes S0's redirected-input approval path."""
    redirected = io.StringIO("yes\n")
    assert redirected.isatty() is False
    monkeypatch.setattr(sys, "stdin", redirected)
    frontend = _cli_runtime(tmp_path)
    try:
        result = frontend.runtime.execute(_invocation(
            tmp_path, session_id=frontend.session_id, turn_id=frontend.turn_id))
        assert result.status is ToolStatus.DENIED
        assert frontend.app.commands[0].payload["approved"] is False
        frontend.executor.run.assert_not_called()
    finally:
        frontend.client.close()


@pytest.mark.parametrize("input_exception", [EOFError, KeyboardInterrupt])
def test_cli_eof_or_interrupt_denies_approval_but_answers_ask_user_empty(tmp_path, input_exception):
    def unavailable(_prompt):
        raise input_exception()

    frontend = _cli_runtime(tmp_path, read=unavailable)
    try:
        denied = frontend.runtime.execute(_invocation(
            tmp_path, session_id=frontend.session_id, turn_id=frontend.turn_id))
        answer = frontend.runtime.execute(_invocation(
            tmp_path, name="ask_user", arguments={"question": "S0 fixture?"},
            session_id=frontend.session_id, turn_id=frontend.turn_id))
        assert denied.status is ToolStatus.DENIED
        assert answer.status is ToolStatus.COMPLETED
        assert answer.legacy_text == ""
        assert [command.kind for command in frontend.app.commands] == [
            CommandKind.RESOLVE_APPROVAL, CommandKind.RESOLVE_USER_INPUT]
        assert frontend.app.commands[0].payload["approved"] is False
        assert frontend.app.commands[1].payload["response"] == ""
        frontend.executor.run.assert_not_called()
    finally:
        frontend.client.close()


def test_ask_user_yes_does_not_resolve_a_later_shell_approval(tmp_path):
    answers = iter(["sí", "no"])
    frontend = _cli_runtime(tmp_path, read=lambda _prompt: next(answers))
    try:
        answer = frontend.runtime.execute(_invocation(
            tmp_path, name="ask_user", arguments={"question": "S0 fixture?"},
            session_id=frontend.session_id, turn_id=frontend.turn_id))
        denied = frontend.runtime.execute(_invocation(
            tmp_path, session_id=frontend.session_id, turn_id=frontend.turn_id))
        assert answer.legacy_text == "sí"
        assert denied.status is ToolStatus.DENIED
        assert [command.kind for command in frontend.app.commands] == [
            CommandKind.RESOLVE_USER_INPUT, CommandKind.RESOLVE_APPROVAL]
        frontend.executor.run.assert_not_called()
    finally:
        frontend.client.close()


def test_ask_user_without_interface_gate_fails_noninteractive(tmp_path):
    runtime = ToolRuntime(ToolRegistry([AskUserTool()]))
    result = runtime.execute(_invocation(
        tmp_path, name="ask_user", arguments={"question": "S0 fixture?"}))
    assert result.status is ToolStatus.FAILED
    assert result.effect_state is EffectState.NONE
    assert "non-interactive" in result.legacy_text


def test_versioned_jsonl_exact_response_is_rejected_without_host_proof(tmp_path):
    """S2 requires host provenance in addition to correlation."""
    with _pending_shell(tmp_path) as pending:
        request = pending.request
        app = _InteractionApplication(request.session_id, pending.gate)
        sent = []
        adapter = JsonlApplicationAdapter(app, request.session_id, sent.append)
        command = ApplicationCommand(
            new_command_id(), CommandKind.RESOLVE_APPROVAL,
            {"approvalId": request.approval_id, "toolCallId": request.tool_call_id,
             "requestDigest": request.request_digest, "cwd": request.cwd,
             "policyRevision": request.policy_revision, "approved": True},
            session_id=request.session_id,
        )
        assert 'approval_actor' not in command.to_dict()
        try:
            assert adapter.handle({"id": "s0", "type": "application_command", "command": command.to_dict()})
            assert sent[0]["type"] == "error"
            assert sent[0]["code"] == 'APPROVAL_ACTOR_INVALID'
            pending.invocation.context.cancellation_token.request()
            pending.worker.join(2)
            assert pending.results[0].status is ToolStatus.CANCELLED
            pending.executor.run.assert_not_called()
        finally:
            adapter.close()


def test_desktop_ipc_source_validates_sender_and_uses_host_confirmation():
    """S2 source inspection; native dialog behavior has separate Node tests."""
    main = (REPO_ROOT / "desktop/electron/main.ts").read_text(encoding="utf-8")
    preload = (REPO_ROOT / "desktop/electron/preload.ts").read_text(encoding="utf-8")
    assert 'event.sender === mainWindow.webContents' in main
    assert 'event.senderFrame === mainWindow.webContents.mainFrame' in main
    assert "data.type === 'confirm_response'" in main
    assert 'return confirmApproval(applicationClient' in main
    assert 'dialog.showMessageBox' in main
    assert "ipcRenderer.send('send-to-python', data)" in preload
    assert "nodeIntegration: false" in main
    assert "contextIsolation: true" in main


def test_jsonl_stdin_source_has_no_frame_size_gate_before_json_parse():
    """AST evidence of current whole-line ingestion, not a transport protection."""
    source = (REPO_ROOT / "local_cli/server.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    server = next(node for node in module.body if isinstance(node, ast.ClassDef)
                  and node.name == "JsonLineServer")
    run = next(node for node in server.body if isinstance(node, ast.FunctionDef) and node.name == "run")
    loop = next(node for node in ast.walk(run) if isinstance(node, ast.For)
                and isinstance(node.iter, ast.Attribute)
                and isinstance(node.iter.value, ast.Name)
                and (node.iter.value.id, node.iter.attr) == ("sys", "stdin"))
    parses = [node for node in ast.walk(loop) if isinstance(node, ast.Call)
              and isinstance(node.func, ast.Attribute)
              and isinstance(node.func.value, ast.Name)
              and (node.func.value.id, node.func.attr) == ("json", "loads")]
    assert len(parses) == 1
    assert isinstance(parses[0].args[0], ast.Name) and parses[0].args[0].id == "line"
    preceding = [node for node in ast.walk(loop) if isinstance(node, ast.Call)
                 and node.lineno < parses[0].lineno]
    assert not any(isinstance(node.func, ast.Name) and node.func.id == "len" for node in preceding)
