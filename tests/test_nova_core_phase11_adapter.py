"""JSONL adapter contracts over the one-session Application API."""

import time
import subprocess
import json
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.events import EventBufferConfig
from local_cli.application.session import AgentSessionCoordinator
from local_cli.core.contracts import new_command_id
from local_cli.core.contracts import EventKind
from local_cli.harness import AgentEvent
from local_cli.interfaces.jsonl_application import JsonlApplicationAdapter
from local_cli.tools.ask_user_tool import AskUserTool
from local_cli.tools.bash_tool import BashTool
from local_cli.shell_executor import ShellDescriptor
from local_cli.server import JsonLineServer
from local_cli.config import Config
from local_cli.application.legacy_runtime import LegacyAgentRuntime
from tests.test_nova_core_phase4_session import ScriptedProvider


def _wait_for(sent, kind, *, request_id=None):
    for _ in range(500):
        match = [item for item in sent if item.get("type") == kind and
                 (request_id is None or item.get("id") == request_id)]
        if match:
            return match[-1]
        time.sleep(0.005)
    raise AssertionError(f"missing JSONL frame {kind}")


def _adapter(tmp_path, provider, *, tools=(), runner=None, event_config=None):
    coordinator = AgentSessionCoordinator(
        provider=provider, model="local", tool_factory=lambda _cwd: list(tools),
        run_agent_fn=runner, event_config=event_config or EventBufferConfig())
    started = coordinator.handle(ApplicationCommand(
        command_id=new_command_id(), kind=CommandKind.START_SESSION,
        payload={"workspace": str(tmp_path)}))
    assert started.accepted
    sent = []
    adapter = JsonlApplicationAdapter(coordinator, started.session_id, sent.append)
    adapter.start()
    return adapter, coordinator, sent


def test_chat_and_status_are_nonblocking_and_project_legacy_stream(tmp_path):
    entered, release = Event(), Event()

    def runner(provider, model, tools, messages, **kwargs):
        kwargs["emit"](AgentEvent("llm_start", {"iteration": 1}))
        kwargs["emit"](AgentEvent("content_delta", {"text": "hola"}))
        entered.set()
        assert release.wait(5)
        kwargs["emit"](AgentEvent("assistant_message", {"content": "hola"}))
        messages.append({"role": "assistant", "content": "hola"})
        return "hola"

    adapter, coordinator, sent = _adapter(tmp_path, object(), runner=runner)
    try:
        assert adapter.handle({"id": 1, "type": "chat", "content": "saluda"})
        assert entered.wait(2)
        assert adapter.handle({"id": 2, "type": "status"})
        assert _wait_for(sent, "status", request_id=2)["data"]["messages"] == 1
        assert _wait_for(sent, "stream", request_id=1)["content"] == "hola"
        assert not any(item.get("type") == "done" for item in sent)
        release.set()
        assert _wait_for(sent, "done", request_id=1)
        assert len(coordinator.get_snapshot(adapter.session_id).turns) == 1
    finally:
        release.set()
        adapter.close()


def test_versioned_snapshot_and_replay_are_correlated(tmp_path):
    adapter, coordinator, sent = _adapter(tmp_path, ScriptedProvider(["hola"]))
    try:
        adapter.handle({"id": 4, "type": "chat", "content": "saluda"})
        _wait_for(sent, "done", request_id=4)
        adapter.handle({"id": 5, "type": "get_snapshot", "sessionId": adapter.session_id})
        snapshot = _wait_for(sent, "snapshot", request_id=5)["data"]
        assert snapshot["turns"][0]["status"] == "completed"
        adapter.handle({"id": 6, "type": "subscribe_events", "sessionId": adapter.session_id,
                        "afterSequence": 0})
        assert _wait_for(sent, "subscribed", request_id=6)["schemaVersion"] == 1
        _wait_for(sent, "event", request_id=6)
        events = [item["event"] for item in sent if item.get("id") == 6 and item["type"] == "event"]
        assert events[0]["sequence"] == 1
        assert all(e["sessionId"] == adapter.session_id for e in events)
        assert len({e["eventId"] for e in events}) == len(events)
    finally:
        adapter.close()


def test_ask_user_jsonl_response_resolves_existing_turn(tmp_path):
    ask = {"role": "assistant", "content": "", "tool_calls": [{
        "function": {"name": "ask_user", "arguments": {"question": "¿Continuar?"}},
    }]}
    adapter, coordinator, sent = _adapter(
        tmp_path, ScriptedProvider([ask, "listo"]), tools=[AskUserTool()])
    try:
        adapter.handle({"id": 10, "type": "chat", "content": "pregunta"})
        request = _wait_for(sent, "input_request")
        adapter.handle({"type": "input_response",
                        "input_request_id": request["input_request_id"] + 1,
                        "response": "incorrecta"})
        assert not any(item.get("type") == "done" for item in sent)
        adapter.handle({"type": "input_response",
                        "input_request_id": request["input_request_id"],
                        "response": "sí"})
        _wait_for(sent, "done", request_id=10)
        state = coordinator.get_snapshot(adapter.session_id)
        assert len(state.turns) == 1
        assert any(m.get("role") == "tool" and "sí" in m.get("content", "")
                   for m in state.transcript)
    finally:
        adapter.close()


def test_stop_is_requested_before_terminal_and_never_creates_turn(tmp_path):
    entered, release = Event(), Event()

    def runner(provider, model, tools, messages, **kwargs):
        entered.set()
        assert release.wait(5)
        return ""

    adapter, coordinator, sent = _adapter(tmp_path, object(), runner=runner)
    try:
        adapter.handle({"id": 20, "type": "chat", "content": "work"})
        assert entered.wait(2)
        adapter.handle({"id": 21, "type": "stop"})
        assert _wait_for(sent, "stop_requested", request_id=21)
        assert not any(item.get("type") == "stopped" for item in sent)
        release.set()
        assert _wait_for(sent, "stopped", request_id=21)["status"] == "cancelled"
        assert len(coordinator.get_snapshot(adapter.session_id).turns) == 1
    finally:
        release.set()
        adapter.close()


def test_reconnect_from_previous_backend_receives_gap_then_snapshot(tmp_path):
    adapter, coordinator, sent = _adapter(tmp_path, ScriptedProvider(["hola"]))
    try:
        adapter.handle({"id": 30, "type": "subscribe_events",
                        "sessionId": "previous-backend", "afterSequence": 900})
        subscribed = _wait_for(sent, "subscribed", request_id=30)
        events = [item["event"] for item in sent if item.get("id") == 30
                  and item["type"] == "event"]
        assert [event["kind"] for event in events[:2]] == ["EventGap", "SessionSnapshot"]
        assert events[0]["payload"]["requestedAfter"] == 900
        assert events[1]["payload"]["sessionId"] == adapter.session_id
        assert subscribed["afterSequence"] == events[1]["sequence"]
        adapter.handle({"id": 31, "type": "chat", "content": "saluda"})
        _wait_for(sent, "done", request_id=31)
        for _ in range(500):
            if any(item.get("id") == 30 and item.get("type") == "event" and
                   item["event"]["sequence"] > subscribed["afterSequence"]
                   for item in sent):
                break
            time.sleep(0.005)
        assert any(item.get("id") == 30 and item.get("type") == "event" and
                   item["event"]["sequence"] > subscribed["afterSequence"]
                   for item in sent)
    finally:
        adapter.close()


def test_jsonl_approval_is_one_shot_and_status_does_not_block(tmp_path):
    executor = Mock()
    executor.run.return_value = subprocess.CompletedProcess([], 0, "ok\n", "")
    shell = BashTool(confirm=lambda _command: False,
                     descriptor=ShellDescriptor("Linux", "bash", "bash", "5"),
                     executor=executor, cwd=tmp_path, environment={})
    risky = {"role": "assistant", "content": "", "tool_calls": [{
        "function": {"name": "bash", "arguments": {"command": "sudo echo ok"}},
    }]}
    adapter, coordinator, sent = _adapter(
        tmp_path, ScriptedProvider([risky, "done"]), tools=[shell])
    try:
        adapter.handle({"id": 40, "type": "chat", "content": "run"})
        confirm = _wait_for(sent, "confirm_request")
        adapter.handle({"id": 41, "type": "status"})
        assert _wait_for(sent, "status", request_id=41)
        adapter.handle({"type": "confirm_response",
                        "confirm_id": confirm["confirm_id"] + 1,
                        "approved": True})
        executor.run.assert_not_called()
        adapter.handle({"type": "confirm_response",
                        "confirm_id": confirm["confirm_id"],
                        "approved": True})
        assert _wait_for(sent, "done", request_id=40)
        executor.run.assert_called_once()
        adapter.handle({"type": "confirm_response",
                        "confirm_id": confirm["confirm_id"],
                        "approved": True})
        executor.run.assert_called_once()
    finally:
        adapter.close()


def test_jsonl_denied_approval_never_executes_command(tmp_path):
    executor = Mock()
    shell = BashTool(confirm=lambda _command: True,
                     descriptor=ShellDescriptor("Linux", "bash", "bash", "5"),
                     executor=executor, cwd=tmp_path, environment={})
    risky = {"role": "assistant", "content": "", "tool_calls": [{
        "function": {"name": "bash", "arguments": {"command": "sudo echo denied"}},
    }]}
    adapter, _, sent = _adapter(tmp_path, ScriptedProvider([risky, "done"]),
                                tools=[shell])
    try:
        adapter.handle({"id": 45, "type": "chat", "content": "run"})
        confirm = _wait_for(sent, "confirm_request")
        adapter.handle({"type": "confirm_response",
                        "confirm_id": confirm["confirm_id"], "approved": False})
        assert _wait_for(sent, "done", request_id=45)
        executor.run.assert_not_called()
    finally:
        adapter.close()


def test_server_folder_change_updates_application_owned_workspace(tmp_path, monkeypatch):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    monkeypatch.chdir(first)
    monkeypatch.setattr("local_cli.bootstrap_server.Config", lambda: Config(
        cli_args=SimpleNamespace(state_dir=str(tmp_path / "state"))))
    sent = []
    monkeypatch.setattr("local_cli.server._send", sent.append)
    server = JsonLineServer()
    try:
        session_id = server._app_adapter.session_id
        server._handle_set_cwd(51, str(second))
        assert sent[-1]["type"] == "cwd_changed"
        snapshot = server._application.get_snapshot(session_id)
        assert snapshot.workspace == str(second)
        assert snapshot.transcript[0]["content"] == server._system_prompt
        assert server._application._session.base_transcript[0]["content"] == server._system_prompt
        assert server._application._persistence.workspace == second
        assert server._application._session.tools[0].cwd == second
        assert server._application._events.last_sequence == snapshot.last_sequence
        receipt = server._application.handle(ApplicationCommand(
            command_id=new_command_id(), kind=CommandKind.EXECUTE_COMMAND,
            session_id=session_id, payload={"name": "clear"}))
        assert receipt.accepted
        assert server._application.get_snapshot(session_id).transcript == tuple(
            server._application._session.base_transcript)
    finally:
        server._app_adapter.close()
        server._session_log.close()


def test_jsonl_slow_subscription_disconnects_then_reconnects_with_gap(tmp_path):
    adapter, coordinator, sent = _adapter(
        tmp_path, ScriptedProvider([]), event_config=EventBufferConfig(
            journal_capacity=3, consumer_queue_capacity=2,
            delivery_batch_size=2))
    try:
        initial = coordinator.get_snapshot(adapter.session_id).last_sequence
        adapter.handle({"id": 60, "type": "subscribe_events",
                        "sessionId": adapter.session_id,
                        "afterSequence": initial})
        with adapter._lock:
            for n in range(4):
                coordinator._events.publish(EventKind.OPERATION_PROGRESS,
                                            {"step": n}, state_revision=1)
        assert _wait_for(sent, "subscription_out_of_sync", request_id=60)
        adapter.handle({"id": 61, "type": "get_snapshot"})
        assert _wait_for(sent, "snapshot", request_id=61)["data"]["lastSequence"] >= 5
        adapter.handle({"id": 62, "type": "subscribe_events",
                        "sessionId": adapter.session_id,
                        "afterSequence": initial})
        _wait_for(sent, "event", request_id=62)
        replay = [item["event"]["kind"] for item in sent
                  if item.get("id") == 62 and item["type"] == "event"]
        assert replay[:2] == ["EventGap", "SessionSnapshot"]
    finally:
        adapter.close()


def test_versioned_transport_rejects_invalid_cursor_and_command(tmp_path):
    adapter, _, sent = _adapter(tmp_path, ScriptedProvider([]))
    try:
        adapter.handle({"id": 70, "type": "subscribe_events", "afterSequence": "bad"})
        adapter.handle({"id": 71, "type": "application_command", "command": {"kind": "unknown"}})
        assert _wait_for(sent, "error", request_id=70)["code"] == "INVALID_EVENT_CURSOR"
        assert _wait_for(sent, "error", request_id=71)["code"] == "INVALID_APPLICATION_COMMAND"
    finally:
        adapter.close()


def test_jsonl_server_reader_uses_application_turn_and_stream(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("local_cli.bootstrap_server.Config", lambda: Config(
        cli_args=SimpleNamespace(state_dir=str(tmp_path / "state"))))
    monkeypatch.setattr("local_cli.updater.check_for_updates", lambda: (False, ""))
    sent = []
    monkeypatch.setattr("local_cli.server._send", sent.append)
    server = JsonLineServer()

    def runner(provider, model, tools, messages, **kwargs):
        kwargs["emit"](AgentEvent("llm_start", {"iteration": 1}))
        kwargs["emit"](AgentEvent("content_delta", {"text": "hola"}))
        kwargs["emit"](AgentEvent("assistant_message", {"content": "hola"}))
        messages.append({"role": "assistant", "content": "hola"})
        return "hola"

    server._application._runtime = LegacyAgentRuntime(runner)
    def lines():
        yield json.dumps({"id": 80, "type": "chat", "content": "saluda"})
        yield json.dumps({"id": 81, "type": "status"})
        _wait_for(sent, "done", request_id=80)
    monkeypatch.setattr("local_cli.server.sys.stdin", lines())
    try:
        server.run()
        assert _wait_for(sent, "status", request_id=81)
        assert _wait_for(sent, "stream", request_id=80)["content"] == "hola"
        assert len(server._application.get_snapshot(server._app_adapter.session_id).turns) == 1
    finally:
        server._app_adapter.close()
        server._session_log.close()


def test_server_rejects_folder_change_during_active_application_turn(tmp_path, monkeypatch):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    monkeypatch.chdir(first)
    monkeypatch.setattr("local_cli.bootstrap_server.Config", lambda: Config(
        cli_args=SimpleNamespace(state_dir=str(tmp_path / "state"))))
    sent = []
    monkeypatch.setattr("local_cli.server._send", sent.append)
    server = JsonLineServer()
    entered, release = Event(), Event()
    def runner(provider, model, tools, messages, **kwargs):
        entered.set()
        assert release.wait(5)
        return "done"
    server._application._runtime = LegacyAgentRuntime(runner)
    try:
        server._app_adapter.handle({"id": 90, "type": "chat", "content": "work"})
        assert entered.wait(2)
        server._handle_set_cwd(91, str(second))
        assert sent[-1]["code"] == "CONFLICT_ACTIVE_OPERATION"
        assert server._cwd == first
        assert server._application.get_snapshot(server._app_adapter.session_id).workspace == str(first)
    finally:
        release.set()
        server._app_adapter.close()
        server._session_log.close()
