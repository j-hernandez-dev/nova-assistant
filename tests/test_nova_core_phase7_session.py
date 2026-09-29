"""Phase-7 Application API requests and terminal timing."""

import subprocess
from datetime import datetime, timedelta, timezone
from threading import Event
import time
from unittest.mock import Mock

from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.events import EventBufferConfig
from local_cli.application.session import AgentSessionCoordinator
from local_cli.core.contracts import EventKind, new_command_id
from local_cli.shell_executor import ShellDescriptor, ShellExecutionCancelled
from local_cli.tools.ask_user_tool import AskUserTool
from local_cli.tools.agent_tool import AgentTool
from local_cli.tools.bash_tool import BashTool
from local_cli.tools.read_tool import ReadTool
from local_cli.sub_agent import SubAgentRunner
from tests.test_nova_core_phase4_session import ScriptedProvider


def _command(kind, session_id=None, payload=None):
    return ApplicationCommand(command_id=new_command_id(), kind=kind,
                              session_id=session_id, payload=payload or {})


def _deadline():
    return datetime.now(timezone.utc) + timedelta(seconds=5)


def _start(coordinator, tmp_path):
    started = coordinator.handle(_command(CommandKind.START_SESSION,
                                          payload={"workspace": str(tmp_path)}))
    assert started.accepted
    return started.session_id


def _pending(gate):
    for _ in range(200):
        pending = gate.pending()
        if pending:
            return pending[0]
        time.sleep(0.005)
    raise AssertionError("interaction did not become pending")


def _events(coordinator, session_id):
    return coordinator.poll_events(coordinator.subscribe_events(
        session_id, after_sequence=0, include_internal=True))


def test_resolve_user_input_keeps_one_turn_and_emits_correlated_events(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: (_ for _ in ()).throw(
        AssertionError("domain read stdin")))
    ask = {"role": "assistant", "content": "", "tool_calls": [{
        "function": {"name": "ask_user", "arguments": {"question": "¿Continuar?"}},
    }]}
    coordinator = AgentSessionCoordinator(
        provider=ScriptedProvider([ask, "done"]), model="local",
        tool_factory=lambda _cwd: [AskUserTool()],
        event_config=EventBufferConfig(64, 64, 8),
        interaction_deadline_factory=_deadline,
    )
    session_id = _start(coordinator, tmp_path)
    turn = coordinator.handle(_command(CommandKind.SUBMIT_USER_INPUT,
                                       session_id, {"content": "pregunta"}))
    request = _pending(coordinator._session.user_input_gate)
    wrong = coordinator.handle(_command(CommandKind.RESOLVE_USER_INPUT,
                                        session_id, {"inputRequestId": "wrong",
                                                     "response": "sí"}))
    assert not wrong.accepted
    assert coordinator.handle(_command(CommandKind.RESOLVE_USER_INPUT,
                                       session_id, {"inputRequestId": request.input_request_id,
                                                    "response": "sí"})).accepted
    assert coordinator.wait_for_turn(turn.created_ids["turnId"], 5)
    snapshot = coordinator.get_snapshot(session_id)
    assert len(snapshot.turns) == 1
    assert snapshot.turns[0]["status"] == "completed"
    events = _events(coordinator, session_id)
    required = [e for e in events if e.kind is EventKind.USER_INPUT_REQUIRED]
    resolved = [e for e in events if e.kind is EventKind.USER_INPUT_RESOLVED]
    assert len(required) == len(resolved) == 1
    assert required[0].turn_id == resolved[0].turn_id == turn.created_ids["turnId"]


def test_application_subscription_receives_question_without_internal_debug_scope(tmp_path):
    ask = {"role": "assistant", "content": "", "tool_calls": [{
        "function": {"name": "ask_user", "arguments": {"question": "Question?"}},
    }]}
    coordinator = AgentSessionCoordinator(
        provider=ScriptedProvider([ask, "done"]), model="local",
        tool_factory=lambda _cwd: [AskUserTool()],
        event_config=EventBufferConfig(64, 64, 8),
        interaction_deadline_factory=_deadline,
    )
    session_id = _start(coordinator, tmp_path)
    cursor = coordinator.handle(_command(CommandKind.SUBSCRIBE_EVENTS, session_id))
    turn = coordinator.handle(_command(CommandKind.SUBMIT_USER_INPUT, session_id,
                                       {"content": "ask"}))
    request = _pending(coordinator._session.user_input_gate)
    try:
        events = coordinator.poll_events(cursor)
        questions = [e for e in events if e.kind is EventKind.USER_INPUT_REQUIRED]
        assert len(questions) == 1
        assert questions[0].payload["question"] == "Question?"
        assert not cursor.include_internal
        public_cursor = coordinator._events.subscribe(after_sequence=0)
        assert not [e for e in coordinator.poll_events(public_cursor)
                    if e.kind is EventKind.USER_INPUT_REQUIRED]
    finally:
        coordinator.handle(_command(CommandKind.RESOLVE_USER_INPUT, session_id,
                                    {"inputRequestId": request.input_request_id,
                                     "response": "answer"}))
        assert coordinator.wait_for_turn(turn.created_ids["turnId"], 5)


def test_approval_wrong_digest_is_rejected_and_stop_waits_for_terminal(tmp_path):
    executor = Mock()
    executor.run.return_value = subprocess.CompletedProcess([], 0, "ok\n", "")
    shell = BashTool(confirm=lambda _cmd: False,
                     descriptor=ShellDescriptor("Linux", "bash", "bash", "5"),
                     executor=executor, cwd=tmp_path, environment={})
    risky = {"role": "assistant", "content": "", "tool_calls": [{
        "function": {"name": "bash", "arguments": {"command": "sudo echo ok"}},
    }]}
    coordinator = AgentSessionCoordinator(
        provider=ScriptedProvider([risky, "done"]), model="local",
        tool_factory=lambda _cwd: [shell],
        event_config=EventBufferConfig(64, 64, 8),
        interaction_deadline_factory=_deadline,
    )
    session_id = _start(coordinator, tmp_path)
    turn = coordinator.handle(_command(CommandKind.SUBMIT_USER_INPUT,
                                       session_id, {"content": "run"}))
    request = _pending(coordinator._session.approval_gate)
    assert not coordinator.wait_for_turn(turn.created_ids["turnId"], 0.01)
    bad = coordinator.handle(_command(CommandKind.RESOLVE_APPROVAL, session_id, {
        "approvalId": request.approval_id, "toolCallId": request.tool_call_id,
        "requestDigest": "wrong", "cwd": request.cwd,
        "policyRevision": 1, "approved": True,
    }))
    assert not bad.accepted
    executor.run.assert_not_called()
    good = coordinator.handle(_command(CommandKind.RESOLVE_APPROVAL, session_id, {
        "approvalId": request.approval_id, "toolCallId": request.tool_call_id,
        "requestDigest": request.request_digest, "cwd": request.cwd,
        "policyRevision": 1, "approved": True,
    }))
    assert good.accepted
    assert coordinator.wait_for_turn(turn.created_ids["turnId"], 5)
    executor.run.assert_called_once()
    assert len([e for e in _events(coordinator, session_id)
                if e.kind is EventKind.APPROVAL_REQUIRED]) == 1


class _BlockingProvider:
    name = "fake"

    def __init__(self):
        self.started = Event()
        self.release = Event()

    def chat_stream(self, *_args, **_kwargs):
        self.started.set()
        yield {"message": {"content": "partial"}}
        self.release.wait(5)
        yield {"message": {"content": "late"}}


def test_cancel_turn_receipt_is_request_not_terminal(tmp_path):
    provider = _BlockingProvider()
    coordinator = AgentSessionCoordinator(
        provider=provider, model="local", tool_factory=lambda _cwd: [],
        event_config=EventBufferConfig(64, 64, 8),
    )
    session_id = _start(coordinator, tmp_path)
    turn = coordinator.handle(_command(CommandKind.SUBMIT_USER_INPUT,
                                       session_id, {"content": "hello"}))
    assert provider.started.wait(2)
    receipt = coordinator.handle(_command(CommandKind.CANCEL_TURN,
                                          session_id, {"turnId": turn.created_ids["turnId"]}))
    assert receipt.accepted
    assert not coordinator.wait_for_turn(turn.created_ids["turnId"], 0.01)
    provider.release.set()
    assert coordinator.wait_for_turn(turn.created_ids["turnId"], 5)
    assert coordinator.get_snapshot(session_id).turns[0]["status"] == "cancelled"
    assert len([e for e in _events(coordinator, session_id)
                if e.kind is EventKind.TURN_CANCELLED]) == 1


def test_stop_generation_does_not_cancel_turn(tmp_path):
    provider = _BlockingProvider()
    coordinator = AgentSessionCoordinator(
        provider=provider, model="local", tool_factory=lambda _cwd: [],
        event_config=EventBufferConfig(64, 64, 8),
    )
    session_id = _start(coordinator, tmp_path)
    turn = coordinator.handle(_command(CommandKind.SUBMIT_USER_INPUT,
                                       session_id, {"content": "hello"}))
    assert provider.started.wait(2)
    generation = next(e.generation_id for e in _events(coordinator, session_id)
                      if e.kind is EventKind.GENERATION_STARTED)
    receipt = coordinator.handle(_command(CommandKind.STOP_GENERATION,
                                          session_id, {"generationId": generation}))
    assert receipt.accepted
    provider.release.set()
    assert coordinator.wait_for_turn(turn.created_ids["turnId"], 5)
    assert coordinator.get_snapshot(session_id).turns[0]["status"] == "completed"
    events = _events(coordinator, session_id)
    assert len([e for e in events if e.kind is EventKind.GENERATION_CANCELLED]) == 1
    assert not [e for e in events if e.kind is EventKind.TURN_CANCELLED]


def test_stop_generation_without_event_subscriber(tmp_path):
    provider = _BlockingProvider()
    coordinator = AgentSessionCoordinator(
        provider=provider, model="local", tool_factory=lambda _cwd: [],
    )
    session_id = _start(coordinator, tmp_path)
    turn = coordinator.handle(_command(CommandKind.SUBMIT_USER_INPUT,
                                       session_id, {"content": "hello"}))
    assert provider.started.wait(2)
    generation_id = coordinator.get_snapshot(session_id).turns[0]["activeGenerationId"]
    assert generation_id is not None
    receipt = coordinator.handle(_command(CommandKind.STOP_GENERATION,
                                          session_id, {"generationId": generation_id}))
    assert receipt.accepted
    provider.release.set()
    assert coordinator.wait_for_turn(turn.created_ids["turnId"], 5)
    assert coordinator.get_snapshot(session_id).turns[0]["status"] == "completed"


def test_cached_read_keeps_one_terminal_per_tool_operation(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("hello", encoding="utf-8")
    read_call = {"role": "assistant", "content": "", "tool_calls": [{
        "function": {"name": "read", "arguments": {"file_path": str(path)}},
    }]}
    coordinator = AgentSessionCoordinator(
        provider=ScriptedProvider([read_call, read_call, "done"]), model="local",
        tool_factory=lambda cwd: [ReadTool(cwd=cwd)],
        event_config=EventBufferConfig(64, 64, 8),
    )
    session_id = _start(coordinator, tmp_path)
    turn = coordinator.handle(_command(CommandKind.SUBMIT_USER_INPUT,
                                       session_id, {"content": "read twice"}))
    assert coordinator.wait_for_turn(turn.created_ids["turnId"], 5)
    assert coordinator.get_snapshot(session_id).turns[0]["status"] == "completed"
    terminal = [e for e in _events(coordinator, session_id)
                if e.kind is EventKind.TOOL_COMPLETED]
    assert len(terminal) == 2
    assert sum(bool(event.payload["cached"]) for event in terminal) == 1


def test_cancel_started_shell_marks_unknown_effect_without_retry(tmp_path):
    started = Event()
    executor = Mock()

    def running_command(*_args, cancellation_token, **_kwargs):
        started.set()
        for _ in range(200):
            if cancellation_token.is_cancel_requested():
                raise ShellExecutionCancelled()
            time.sleep(0.005)
        raise AssertionError("shell cancellation was not delivered")

    executor.run.side_effect = running_command
    shell = BashTool(descriptor=ShellDescriptor("Linux", "bash", "bash", "5"),
                     executor=executor, cwd=tmp_path, environment={})
    call = {"role": "assistant", "content": "", "tool_calls": [{
        "function": {"name": "bash", "arguments": {"command": "echo begun"}},
    }]}
    coordinator = AgentSessionCoordinator(
        provider=ScriptedProvider([call, "done"]), model="local",
        tool_factory=lambda _cwd: [shell],
        event_config=EventBufferConfig(64, 64, 8),
    )
    session_id = _start(coordinator, tmp_path)
    turn = coordinator.handle(_command(CommandKind.SUBMIT_USER_INPUT,
                                       session_id, {"content": "run"}))
    assert started.wait(2)
    assert coordinator.handle(_command(CommandKind.CANCEL_TURN, session_id,
                                       {"turnId": turn.created_ids["turnId"]})).accepted
    assert coordinator.wait_for_turn(turn.created_ids["turnId"], 5)
    snapshot = coordinator.get_snapshot(session_id).turns[0]
    assert snapshot["status"] == "failed"
    assert snapshot["operationStatus"] == "outcome_unknown"
    assert snapshot["errorCode"] == "OUTCOME_UNKNOWN"
    assert executor.run.call_count == 1
    terminal = [event for event in _events(coordinator, session_id)
                if event.kind is EventKind.TOOL_FAILED]
    assert len(terminal) == 1
    assert terminal[0].payload["status"] == "outcome_unknown"


def test_cancel_operation_closes_pending_question_without_new_turn(tmp_path):
    ask = {"role": "assistant", "content": "", "tool_calls": [{
        "function": {"name": "ask_user", "arguments": {"question": "Wait?"}},
    }]}
    coordinator = AgentSessionCoordinator(
        provider=ScriptedProvider([ask, "done"]), model="local",
        tool_factory=lambda _cwd: [AskUserTool()],
        event_config=EventBufferConfig(64, 64, 8),
        interaction_deadline_factory=_deadline,
    )
    session_id = _start(coordinator, tmp_path)
    turn = coordinator.handle(_command(CommandKind.SUBMIT_USER_INPUT,
                                       session_id, {"content": "ask"}))
    request = _pending(coordinator._session.user_input_gate)
    receipt = coordinator.handle(_command(CommandKind.CANCEL_OPERATION,
                                          session_id,
                                          {"operationId": request.operation_id}))
    assert receipt.accepted
    assert coordinator.wait_for_turn(turn.created_ids["turnId"], 5)
    late = coordinator.handle(_command(CommandKind.RESOLVE_USER_INPUT,
                                       session_id,
                                       {"inputRequestId": request.input_request_id,
                                        "response": "late"}))
    assert not late.accepted
    events = _events(coordinator, session_id)
    failed = [e for e in events if e.kind is EventKind.TOOL_FAILED]
    assert len(failed) == 1 and failed[0].payload["status"] == "cancelled"
    assert coordinator.get_snapshot(session_id).turns[0]["status"] == "completed"


def test_cancel_turn_while_approval_pending_denies_execution(tmp_path):
    executor = Mock()
    shell = BashTool(confirm=lambda _cmd: False,
                     descriptor=ShellDescriptor("Linux", "bash", "bash", "5"),
                     executor=executor, cwd=tmp_path, environment={})
    risky = {"role": "assistant", "content": "", "tool_calls": [{
        "function": {"name": "bash", "arguments": {"command": "sudo echo ok"}},
    }]}
    coordinator = AgentSessionCoordinator(
        provider=ScriptedProvider([risky, "done"]), model="local",
        tool_factory=lambda _cwd: [shell],
        event_config=EventBufferConfig(64, 64, 8),
        interaction_deadline_factory=_deadline,
    )
    session_id = _start(coordinator, tmp_path)
    turn = coordinator.handle(_command(CommandKind.SUBMIT_USER_INPUT,
                                       session_id, {"content": "run"}))
    request = _pending(coordinator._session.approval_gate)
    assert coordinator.handle(_command(CommandKind.CANCEL_TURN, session_id,
                                       {"turnId": turn.created_ids["turnId"]})).accepted
    assert coordinator.wait_for_turn(turn.created_ids["turnId"], 5)
    executor.run.assert_not_called()
    late = coordinator.handle(_command(CommandKind.RESOLVE_APPROVAL, session_id, {
        "approvalId": request.approval_id, "toolCallId": request.tool_call_id,
        "requestDigest": request.request_digest, "cwd": request.cwd,
        "policyRevision": 1, "approved": True,
    }))
    assert not late.accepted
    assert coordinator.get_snapshot(session_id).turns[0]["status"] == "cancelled"


def test_cancel_background_subagent_waits_for_child_terminal(tmp_path, monkeypatch):
    child_provider = _BlockingProvider()
    runner = SubAgentRunner(max_workers=1)
    agent_tool = AgentTool(runner=runner, provider=child_provider,
                           model="local", sub_agent_tools=[], cwd=tmp_path)
    monkeypatch.setattr(agent_tool, "_create_fresh_provider", lambda: child_provider)
    call = {"role": "assistant", "content": "", "tool_calls": [{
        "function": {"name": "agent", "arguments": {
            "description": "child", "prompt": "work", "run_in_background": True,
        }},
    }]}
    coordinator = AgentSessionCoordinator(
        provider=ScriptedProvider([call, "done"]), model="local",
        tool_factory=lambda _cwd: [agent_tool],
        event_config=EventBufferConfig(64, 64, 8),
    )
    try:
        session_id = _start(coordinator, tmp_path)
        turn = coordinator.handle(_command(CommandKind.SUBMIT_USER_INPUT,
                                           session_id, {"content": "delegate"}))
        assert child_provider.started.wait(2)
        assert coordinator.wait_for_turn(turn.created_ids["turnId"], 5)
        started = [e for e in _events(coordinator, session_id)
                   if e.kind is EventKind.AGENT_STARTED]
        assert len(started) == 1
        agent_id = started[0].agent_id
        receipt = coordinator.handle(_command(CommandKind.CANCEL_SUB_AGENT,
                                              session_id, {"agentId": agent_id}))
        assert receipt.accepted
        assert not [e for e in _events(coordinator, session_id)
                    if e.kind is EventKind.AGENT_CANCELLED]
        child_provider.release.set()
        for _ in range(200):
            terminal = [e for e in _events(coordinator, session_id)
                        if e.kind is EventKind.AGENT_CANCELLED]
            if terminal:
                break
            time.sleep(0.005)
        assert len(terminal) == 1
        assert terminal[0].operation_id == started[0].operation_id
        assert not coordinator.handle(_command(CommandKind.CANCEL_SUB_AGENT,
                                               session_id, {"agentId": agent_id})).accepted
    finally:
        child_provider.release.set()
        runner.shutdown()


def test_subagent_submission_failure_has_one_terminal(tmp_path, monkeypatch):
    runner = SubAgentRunner(max_workers=1)
    agent_tool = AgentTool(runner=runner, provider=ScriptedProvider([]),
                           model="local", sub_agent_tools=[], cwd=tmp_path)
    monkeypatch.setattr(agent_tool, "_create_fresh_provider",
                        lambda: ScriptedProvider([]))
    monkeypatch.setattr(runner, "submit_background",
                        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("queue closed")))
    call = {"role": "assistant", "content": "", "tool_calls": [{
        "function": {"name": "agent", "arguments": {
            "description": "child", "prompt": "work", "run_in_background": True,
        }},
    }]}
    coordinator = AgentSessionCoordinator(
        provider=ScriptedProvider([call, "done"]), model="local",
        tool_factory=lambda _cwd: [agent_tool],
        event_config=EventBufferConfig(64, 64, 8),
    )
    try:
        session_id = _start(coordinator, tmp_path)
        turn = coordinator.handle(_command(CommandKind.SUBMIT_USER_INPUT,
                                           session_id, {"content": "delegate"}))
        assert coordinator.wait_for_turn(turn.created_ids["turnId"], 5)
        events = _events(coordinator, session_id)
        started = [e for e in events if e.kind is EventKind.AGENT_STARTED]
        failed = [e for e in events if e.kind is EventKind.AGENT_FAILED]
        assert len(started) == len(failed) == 1
        assert started[0].operation_id == failed[0].operation_id
    finally:
        runner.shutdown()


def test_cancel_turn_waits_for_background_child_terminal(tmp_path, monkeypatch):
    child_provider, main_provider = _BlockingProvider(), _BlockingProvider()
    runner = SubAgentRunner(max_workers=1)
    agent_tool = AgentTool(runner=runner, provider=child_provider,
                           model="local", sub_agent_tools=[], cwd=tmp_path)
    monkeypatch.setattr(agent_tool, "_create_fresh_provider", lambda: child_provider)
    call = {"role": "assistant", "content": "", "tool_calls": [{
        "function": {"name": "agent", "arguments": {
            "description": "child", "prompt": "work", "run_in_background": True,
        }},
    }]}

    class MainProvider:
        def __init__(self):
            self.calls = 0

        def chat_stream(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return iter([{"message": call, "done": True}])
            return main_provider.chat_stream()

    coordinator = AgentSessionCoordinator(
        provider=MainProvider(), model="local", tool_factory=lambda _cwd: [agent_tool],
        event_config=EventBufferConfig(64, 64, 8),
    )
    try:
        session_id = _start(coordinator, tmp_path)
        turn = coordinator.handle(_command(CommandKind.SUBMIT_USER_INPUT,
                                           session_id, {"content": "delegate"}))
        assert child_provider.started.wait(2)
        assert main_provider.started.wait(2)
        assert coordinator.handle(_command(CommandKind.CANCEL_TURN, session_id,
                                           {"turnId": turn.created_ids["turnId"]})).accepted
        main_provider.release.set()
        assert not coordinator.wait_for_turn(turn.created_ids["turnId"], 0.1)
        child_provider.release.set()
        assert coordinator.wait_for_turn(turn.created_ids["turnId"], 5)
        events = _events(coordinator, session_id)
        child_terminal = next(e for e in events if e.kind is EventKind.AGENT_CANCELLED)
        turn_terminal = next(e for e in events if e.kind is EventKind.TURN_CANCELLED)
        assert child_terminal.sequence < turn_terminal.sequence
    finally:
        child_provider.release.set()
        main_provider.release.set()
        runner.shutdown()
