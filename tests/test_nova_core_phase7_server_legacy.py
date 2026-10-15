"""Legacy JSONL names now resolve through Application gates exclusively."""
from datetime import datetime, timedelta, timezone
from threading import Event
from types import SimpleNamespace
import subprocess
from unittest.mock import Mock
import pytest
from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.events import EventBufferConfig
from local_cli.application.session import AgentSessionCoordinator
from local_cli.core.contracts import new_command_id
from local_cli.interfaces.jsonl_application import JsonlApplicationAdapter
from local_cli.shell_executor import ShellDescriptor
from local_cli.tools.bash_tool import BashTool
from local_cli.tools.ask_user_tool import AskUserTool
from tests.test_server import _make_server
from tests.test_nova_core_phase4_session import ScriptedProvider
from tests.test_nova_core_phase11_adapter import _adapter, _wait_for


def _server_stub(monkeypatch):
    server = _make_server(ScriptedProvider([]), [])
    server._git_ops = Mock(capability=Mock(return_value=SimpleNamespace(value="UNAVAILABLE")))
    sent = []
    monkeypatch.setattr("local_cli.server._send", sent.append)
    server._compose_test_application()
    return server, sent


def approval_adapter(tmp_path, *, auto=False, timeout=None):
    executor = Mock(run=Mock(return_value=subprocess.CompletedProcess([], 0, "ok", "")))
    shell = BashTool(descriptor=ShellDescriptor("Linux", "bash", "bash", "5"),
        executor=executor, cwd=tmp_path, environment={})
    call = {"role": "assistant", "content": "", "tool_calls": [{"function": {
        "name": "bash", "arguments": {"command": "sudo echo hi"}}}]}
    app = AgentSessionCoordinator(provider=ScriptedProvider([call, "done"]), model="local",
        tool_factory=lambda _: [shell], event_config=EventBufferConfig(), auto_approve=auto,
        human_response_deadline_factory=(lambda: datetime.now(timezone.utc)+timedelta(seconds=timeout)) if timeout else None)
    started = app.handle(ApplicationCommand(command_id=new_command_id(), kind=CommandKind.START_SESSION,
        payload={"workspace": str(tmp_path)}))
    sent=[]
    adapter=JsonlApplicationAdapter(app, started.session_id, sent.append)
    adapter.start()
    return adapter, app, sent, executor


def test_stale_confirm_response_cannot_approve_next_command(tmp_path):
    adapter, app, sent, executor = approval_adapter(tmp_path)
    try:
        adapter.handle({"id": 1, "type": "chat", "content": "run"})
        request = _wait_for(sent, "confirm_request")
        adapter.handle({"type": "confirm_response", "confirm_id": request["confirm_id"]+1, "approved": True})
        executor.run.assert_not_called()
        adapter.handle({"type": "confirm_response", "confirm_id": request["confirm_id"], "approved": False})
        _wait_for(sent, "done", request_id=1)
        adapter.handle({"type": "confirm_response", "confirm_id": request["confirm_id"], "approved": True})
        executor.run.assert_not_called()
    finally: adapter.close()


def test_server_ask_user_uses_jsonl_response_not_stdin(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: pytest.fail("domain read stdin"))
    ask={"role":"assistant","content":"","tool_calls":[{"function":{"name":"ask_user","arguments":{"question":"Question?"}}}]}
    adapter, app, sent=_adapter(tmp_path, ScriptedProvider([ask,"done"]),tools=[AskUserTool()])
    try:
        adapter.handle({"id":1,"type":"chat","content":"ask"})
        request=_wait_for(sent,"input_request")
        adapter.handle({"type":"input_response","input_request_id":request["input_request_id"]+1,"response":"wrong"})
        assert not any(x.get("type")=="done" for x in sent)
        adapter.handle({"type":"input_response","input_request_id":request["input_request_id"],"response":"answer"})
        _wait_for(sent,"done",request_id=1)
        assert len(app.get_snapshot(adapter.session_id).turns)==1
    finally: adapter.close()


def test_legacy_stop_ack_is_not_a_terminal_while_chat_thread_runs(tmp_path):
    entered,release=Event(),Event()
    def run(*args,**kwargs):
        entered.set(); assert release.wait(5); return ""
    adapter,app,sent=_adapter(tmp_path,object(),runner=run)
    try:
        adapter.handle({"id":1,"type":"chat","content":"run"}); assert entered.wait(2)
        adapter.handle({"id":42,"type":"stop"})
        _wait_for(sent,"stop_requested",request_id=42)
        assert not any(x.get("type")=="stopped" for x in sent)
        release.set(); _wait_for(sent,"stopped",request_id=42)
    finally: release.set();adapter.close()


def test_status_does_not_join_chat_waiting_for_confirmation(tmp_path):
    adapter,app,sent,executor=approval_adapter(tmp_path)
    try:
        adapter.handle({"id":1,"type":"chat","content":"run"})
        request=_wait_for(sent,"confirm_request")
        adapter.handle({"id":2,"type":"status"})
        _wait_for(sent,"status",request_id=2)
        adapter.handle({"type":"confirm_response","confirm_id":request["confirm_id"],"approved":True})
        _wait_for(sent,"done",request_id=1);executor.run.assert_called_once()
    finally:adapter.close()


def test_chat_setup_failure_finalizes_pending_stop(tmp_path):
    entered,release=Event(),Event()
    def fail(*args,**kwargs):
        entered.set();assert release.wait(5);raise RuntimeError("setup failed")
    adapter,app,sent=_adapter(tmp_path,object(),runner=fail)
    try:
        adapter.handle({"id":1,"type":"chat","content":"run"});assert entered.wait(2)
        adapter.handle({"id":42,"type":"stop"});_wait_for(sent,"stop_requested",request_id=42)
        release.set();_wait_for(sent,"stopped",request_id=42)
        assert app.get_snapshot(adapter.session_id).turns[0]["terminalCount"]==1
    finally:release.set();adapter.close()


def test_server_keeps_shell_timeout_separate_from_confirmation_timeout(tmp_path,monkeypatch):
    executor=Mock(run=Mock(return_value=subprocess.CompletedProcess([],0,"ok","")))
    shell=BashTool(descriptor=ShellDescriptor("Linux","bash","bash","5"),executor=executor,cwd=tmp_path,environment={})
    server=_make_server(SimpleNamespace(name="fake"),[shell]);server._cwd=tmp_path;server._environment={}
    monkeypatch.setattr("local_cli.server._send",lambda _:None)
    def run(_p,_m,tools,_messages,**kwargs):
        assert tools[0].execute(command="echo ok",timeout=600)=="ok"
    monkeypatch.setattr("local_cli.bootstrap_server.run_agent",run)
    server._handle_chat(1,"run")
    assert executor.run.call_args.args[1]==600
    assert executor.run.call_args.kwargs["deadline"] is None
