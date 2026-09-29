"""Phase-7 application interactions: one-shot approvals, input and cancellation."""

from datetime import datetime, timedelta, timezone
from threading import Thread
from threading import Event
import time
import subprocess
import sys
import os
from unittest.mock import Mock

import pytest

from local_cli.application.cancellation import CancellationController
from local_cli.application.interactions import (
    ApprovalGate, InteractionError, UserInputGate,
)
from local_cli.application.tool_runtime import ToolRegistry, ToolRuntime
from local_cli.core.contracts import (
    ExecutionContext, RuntimeCapabilitySnapshot, ToolInvocation,
    new_operation_id, new_session_id, new_tool_call_id, new_turn_id,
    ToolStatus,
)
from local_cli.shell_executor import ShellDescriptor, detect_shell
from local_cli.tools.ask_user_tool import AskUserTool
from local_cli.tools.bash_tool import BashTool


def _invocation(tmp_path, token=None, deadline=None):
    operation_id = new_operation_id()
    context = ExecutionContext(
        workspace=tmp_path, cwd=tmp_path, environment={},
        session_id=new_session_id(), turn_id=new_turn_id(),
        operation_id=operation_id,
        cancellation_token=token or CancellationController(),
        deadline=deadline or datetime.now(timezone.utc) + timedelta(seconds=5),
        capabilities=RuntimeCapabilitySnapshot(
            captured_at=datetime.now(timezone.utc), source="test"),
        policy_revision=1,
    )
    return ToolInvocation(
        name="bash", arguments={"command": "sudo echo ok"},
        tool_call_id=new_tool_call_id(), operation_id=operation_id,
        context=context,
    )


def _wait_pending(gate):
    for _ in range(200):
        pending = gate.pending()
        if pending:
            return pending[0]
        time.sleep(0.005)
    raise AssertionError("request did not become pending")


def test_child_cancel_inherits_parent_without_cancelling_sibling():
    parent = CancellationController()
    first = parent.child()
    second = parent.child()
    first.request()
    assert first.is_cancel_requested()
    assert not second.is_cancel_requested()
    parent.request()
    assert second.is_cancel_requested()


def test_approval_is_bound_to_digest_cwd_revision_and_one_shot(tmp_path):
    required, resolved = [], []
    gate = ApprovalGate(on_required=required.append,
                        on_resolved=lambda *items: resolved.append(items))
    invocation = _invocation(tmp_path)
    output = []
    worker = Thread(target=lambda: output.append(gate.request(
        invocation, dict(invocation.arguments), policy_revision=1)))
    worker.start()
    request = _wait_pending(gate)
    assert request.approval_id and request.tool_call_id == invocation.tool_call_id
    assert request.request_digest and request.cwd == str(tmp_path)
    with pytest.raises(InteractionError, match="REQUEST_MISMATCH"):
        gate.resolve(invocation.context.session_id, request.approval_id,
                     request.tool_call_id, request.request_digest,
                     cwd=str(tmp_path / "elsewhere"), policy_revision=1,
                     approved=True)
    assert not output
    gate.resolve(invocation.context.session_id, request.approval_id,
                 request.tool_call_id, request.request_digest,
                 cwd=request.cwd, policy_revision=1, approved=True)
    worker.join(2)
    assert output == [True]
    assert len(required) == len(resolved) == 1
    assert gate.resolve(invocation.context.session_id, request.approval_id,
                        request.tool_call_id, request.request_digest,
                        cwd=request.cwd, policy_revision=1, approved=True)
    with pytest.raises(InteractionError, match="ALREADY_RESOLVED"):
        gate.resolve(invocation.context.session_id, request.approval_id,
                     request.tool_call_id, request.request_digest,
                     cwd=request.cwd, policy_revision=1, approved=False)


def test_approval_expiry_and_cancellation_never_authorize(tmp_path):
    expired = _invocation(tmp_path, deadline=datetime.now(timezone.utc) - timedelta(seconds=1))
    gate = ApprovalGate()
    assert gate.request(expired, dict(expired.arguments), policy_revision=1) is False
    token = CancellationController()
    invocation = _invocation(tmp_path, token=token)
    output = []
    worker = Thread(target=lambda: output.append(gate.request(
        invocation, dict(invocation.arguments), policy_revision=1)))
    worker.start()
    request = _wait_pending(gate)
    token.request()
    worker.join(2)
    assert output == [False]
    with pytest.raises(InteractionError, match="ALREADY_RESOLVED"):
        gate.resolve(invocation.context.session_id, request.approval_id,
                     request.tool_call_id, request.request_digest,
                     cwd=request.cwd, policy_revision=1, approved=True)


def test_pending_approval_expiry_rejects_late_response(tmp_path):
    gate = ApprovalGate()
    invocation = _invocation(tmp_path, deadline=datetime.now(timezone.utc)
                             + timedelta(milliseconds=80))
    output = []
    worker = Thread(target=lambda: output.append(gate.request(
        invocation, dict(invocation.arguments), policy_revision=1)))
    worker.start()
    request = _wait_pending(gate)
    worker.join(2)
    assert output == [False]
    with pytest.raises(InteractionError, match="ALREADY_RESOLVED"):
        gate.resolve(invocation.context.session_id, request.approval_id,
                     request.tool_call_id, request.request_digest,
                     cwd=request.cwd, policy_revision=1, approved=True)


@pytest.mark.parametrize("field,value", [
    ("tool_call_id", "other-tool-call"), ("request_digest", "tampered"),
    ("policy_revision", 2), ("cwd", "."), ("approved", "yes"),
])
def test_approval_rejects_mismatched_authority_inputs(tmp_path, field, value):
    gate = ApprovalGate()
    invocation = _invocation(tmp_path)
    output = []
    worker = Thread(target=lambda: output.append(gate.request(
        invocation, dict(invocation.arguments), policy_revision=1)))
    worker.start()
    request = _wait_pending(gate)
    response = dict(session_id=invocation.context.session_id,
                    approval_id=request.approval_id, tool_call_id=request.tool_call_id,
                    request_digest=request.request_digest, cwd=request.cwd,
                    policy_revision=1, approved=True)
    response[field] = value
    try:
        with pytest.raises(InteractionError):
            gate.resolve(**response)
        assert worker.is_alive()
    finally:
        invocation.context.cancellation_token.request()
        worker.join(2)
    assert output == [False]


def test_ask_user_resolves_without_input_or_new_turn(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: pytest.fail("input called"))
    gate = UserInputGate()
    invocation = _invocation(tmp_path)
    output = []
    worker = Thread(target=lambda: output.append(gate.ask(invocation, "¿Continuar?")))
    worker.start()
    request = _wait_pending(gate)
    assert request.turn_id == invocation.context.turn_id
    with pytest.raises(InteractionError, match="REQUEST_MISMATCH"):
        gate.resolve(invocation.context.session_id, "wrong-id", "sí")
    gate.resolve(invocation.context.session_id, request.input_request_id, "sí")
    worker.join(2)
    assert output == ["sí"]
    assert gate.resolve(invocation.context.session_id, request.input_request_id, "sí") == "sí"
    with pytest.raises(InteractionError, match="ALREADY_RESOLVED"):
        gate.resolve(invocation.context.session_id, request.input_request_id, "no")


def test_tool_runtime_approval_executes_once_without_legacy_callback(tmp_path):
    executor = Mock()
    executor.run.return_value = subprocess.CompletedProcess([], 0, "ok\n", "")
    shell = BashTool(confirm=lambda _command: pytest.fail("legacy callback called"),
                     descriptor=ShellDescriptor("Linux", "bash", "bash", "5"),
                     executor=executor, cwd=tmp_path, environment={})
    gate = ApprovalGate()
    runtime = ToolRuntime(ToolRegistry([shell]), approval_gate=gate)
    invocation = _invocation(tmp_path)
    output = []
    worker = Thread(target=lambda: output.append(runtime.execute(invocation)))
    worker.start()
    request = _wait_pending(gate)
    executor.run.assert_not_called()
    gate.resolve(invocation.context.session_id, request.approval_id,
                 request.tool_call_id, request.request_digest,
                 cwd=request.cwd, policy_revision=1, approved=True)
    worker.join(2)
    assert output[0].status is ToolStatus.COMPLETED
    executor.run.assert_called_once()
    assert runtime.execute(invocation) is output[0]
    executor.run.assert_called_once()


def test_tool_runtime_ask_user_never_reads_stdin(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: pytest.fail("input called"))
    gate = UserInputGate()
    runtime = ToolRuntime(ToolRegistry([AskUserTool()]), user_input_gate=gate)
    original = _invocation(tmp_path)
    invocation = ToolInvocation(
        name="ask_user", arguments={"question": "¿Continuar?"},
        tool_call_id=original.tool_call_id, operation_id=original.operation_id,
        context=original.context,
    )
    output = []
    worker = Thread(target=lambda: output.append(runtime.execute(invocation)))
    worker.start()
    request = _wait_pending(gate)
    assert request.turn_id == invocation.context.turn_id
    gate.resolve(invocation.context.session_id, request.input_request_id, "sí")
    worker.join(2)
    assert output[0].status is ToolStatus.COMPLETED
    assert output[0].legacy_text == "sí"


def test_cancelled_tool_before_start_has_no_effect(tmp_path):
    token = CancellationController()
    token.request()
    shell = BashTool(descriptor=ShellDescriptor("Linux", "bash", "bash", "5"),
                     executor=Mock(), cwd=tmp_path, environment={})
    runtime = ToolRuntime(ToolRegistry([shell]))
    result = runtime.execute(_invocation(tmp_path, token=token))
    assert result.status is ToolStatus.CANCELLED
    shell._executor.run.assert_not_called()


def test_native_shell_cancellation_terminates_started_process(tmp_path, monkeypatch):
    descriptor = detect_shell()
    if descriptor is None:
        pytest.skip("no supported native shell")
    shell = BashTool(descriptor=descriptor, cwd=tmp_path)
    command = ("Start-Sleep -Seconds 10" if descriptor.kind == "powershell"
               else "sleep 10")
    original_popen = subprocess.Popen
    started = Event()
    captured = []

    def capture_popen(*args, **kwargs):
        process = original_popen(*args, **kwargs)
        captured.append(process)
        started.set()
        return process

    monkeypatch.setattr(subprocess, "Popen", capture_popen)
    token = CancellationController()
    output = []
    worker = Thread(target=lambda: output.append(shell.execute_with_context(
        cancellation_token=token,
        deadline=datetime.now(timezone.utc) + timedelta(seconds=10),
        command=command,
    )))
    worker.start()
    assert started.wait(5)
    token.request()
    worker.join(5)
    assert not worker.is_alive()
    assert output[0].status is ToolStatus.OUTCOME_UNKNOWN
    assert captured[0].poll() is not None


def test_expired_shell_deadline_never_creates_process(tmp_path):
    executor = Mock()
    shell = BashTool(descriptor=ShellDescriptor("Linux", "bash", "bash", "5"),
                     executor=executor, cwd=tmp_path, environment={})
    result = shell.execute_with_context(
        cancellation_token=CancellationController(),
        deadline=datetime.now(timezone.utc) - timedelta(seconds=1),
        command="echo should-not-run",
    )
    assert result.status is ToolStatus.CANCELLED
    assert result.effect_state.value == "none"
    executor.run.assert_not_called()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process-tree smoke")
def test_windows_cancellation_terminates_native_child_process(tmp_path):
    import ctypes
    from local_cli.shell_executor import create_executor

    descriptor = detect_shell()
    if descriptor is None:
        pytest.skip("no native shell")
    child_pid_path = tmp_path / "child_pid.txt"
    script = ("from pathlib import Path; import os, time; "
              f"Path({str(child_pid_path)!r}).write_text(str(os.getpid())); time.sleep(10)")
    command = "& '{}' -c '{}'".format(sys.executable.replace("'", "''"),
                                    script.replace("'", "''"))
    token = CancellationController()
    failures = []

    def run():
        try:
            create_executor(descriptor).run(command, 15, str(tmp_path), dict(os.environ),
                                            cancellation_token=token)
        except Exception as exc:
            failures.append(exc)

    worker = Thread(target=run)
    worker.start()
    try:
        for _ in range(500):
            if child_pid_path.exists() and child_pid_path.read_text():
                break
            time.sleep(0.01)
        assert child_pid_path.exists(), "child process never started"
        child_pid = int(child_pid_path.read_text())
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x100000, False, child_pid)
        assert handle, "child exited before cancellation"
        try:
            token.request()
            worker.join(5)
            assert not worker.is_alive()
            assert kernel.WaitForSingleObject(handle, 0) == 0, "child survived cancellation"
        finally:
            kernel.CloseHandle(handle)
        assert failures and type(failures[0]).__name__ == "ShellExecutionCancelled"
    finally:
        token.request()
        worker.join(5)
