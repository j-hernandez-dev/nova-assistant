"""Legacy interfaces delegate provider state and enforce OD-04 before effects."""

import json
from threading import Event
from unittest.mock import Mock

import pytest

from local_cli.application.providers import ProviderTransitionError
from tests.cli_application_fixture import _ReplContext, _handle_slash_command
from local_cli.config import Config
from local_cli.orchestrator import Orchestrator
from local_cli.session import SessionManager
from tests.test_server import _make_server
from tests.test_nova_core_phase8_providers import Provider, manager
from tests.test_nova_core_phase7_server_legacy import _server_stub


@pytest.mark.parametrize("method,args", [
    ("_handle_switch_model", ("new",)),
    ("_handle_command", ("/model new",)),
    ("_handle_switch_provider", ("claude",)),
    ("_handle_claude_logout", ()),
])
def test_server_change_handlers_reject_active_turn_without_side_effects(monkeypatch, method, args):
    import os
    from local_cli.application.legacy_runtime import LegacyAgentRuntime
    from tests.test_nova_core_phase11_adapter import _wait_for
    server,sent=_server_stub(monkeypatch)
    entered,release=Event(),Event()
    def run(*_args,**_kwargs):
        entered.set();assert release.wait(5);return "done"
    server._application._runtime=LegacyAgentRuntime(run)
    monkeypatch.setenv("ANTHROPIC_API_KEY","keep-secret")
    try:
        server._app_adapter.handle({"id":1,"type":"chat","content":"task"})
        assert entered.wait(2)
        before=server._application.get_snapshot(server._app_adapter.session_id)
        getattr(server,method)(47,*args)
        assert next(m for m in sent if m.get("id")==47)["code"]=="CONFLICT_ACTIVE_TURN"
        after=server._application.get_snapshot(server._app_adapter.session_id)
        assert after.turns[0]["status"]=="running" and not after.turns[0]["cancelRequested"]
        assert after.model_runtime==before.model_runtime
        assert os.environ["ANTHROPIC_API_KEY"]=="keep-secret"
    finally:
        release.set();server._application._session.turns[0].done.wait(3)


@pytest.mark.parametrize("change_request", [
    {"type":"switch_model","model":"new"},
    {"type":"switch_provider","provider":"claude"},
    {"type":"command","command":"/model new"},
    {"type":"command","command":"/provider claude"},
])
def test_jsonl_reader_rejects_without_joining_or_interrupting_turn(monkeypatch,change_request):
    from local_cli.application.legacy_runtime import LegacyAgentRuntime
    server,sent=_server_stub(monkeypatch)
    before=server._application.get_snapshot(server._app_adapter.session_id).model_runtime
    entered,release=Event(),Event()
    def run(*_args,**_kwargs):
        entered.set();assert release.wait(5),"reader blocked";return "done"
    server._application._runtime=LegacyAgentRuntime(run)
    monkeypatch.setattr("local_cli.updater.check_for_updates",lambda:(False,""))
    def requests():
        yield json.dumps({"id":1,"type":"chat","content":"task"})
        assert entered.wait(2)
        yield json.dumps({"id":47,**change_request})
        assert next(m for m in sent if m.get("id")==47)["code"]=="CONFLICT_ACTIVE_TURN"
        assert not server._application.get_snapshot(server._app_adapter.session_id).turns[0]["cancelRequested"]
        release.set()
    monkeypatch.setattr("local_cli.server.sys.stdin",requests())
    try: server.run()
    finally:
        release.set();assert server._application._session.turns[0].done.wait(3)
        server._app_adapter.close()
    assert server._application.get_snapshot(server._app_adapter.session_id).model_runtime==before
    assert not hasattr(server,"_pending_switch")


def test_server_valid_transition_and_models_use_active_manager(monkeypatch):
    provider = Provider()
    server = _make_server(provider, [])
    server._chat_active = False
    server._provider_manager = manager(provider)
    server._system_prompt = "sys"
    sent = []
    monkeypatch.setattr("local_cli.server._send", sent.append)
    server._handle_switch_provider(47, "llama-server", "new")
    assert server._provider.name == "llama-server" and server._config.model == "new"
    assert sent[-1]["providerRevision"] == 2
    server._client.list_models.side_effect = AssertionError("must use active provider")
    server._handle_models(48)
    assert sent[-1]["type"] == "models" and sent[-1]["data"][1]["name"] == "new"


def test_cli_and_orchestrator_share_one_manager(tmp_path, capsys):
    config = Config()
    config.model = "old"
    state = manager()
    orchestrator = Orchestrator(config)
    orchestrator.bind_provider_manager(state)
    ctx = _ReplContext(config, Mock(), [], [], SessionManager(tmp_path), "sys",
                       orchestrator=orchestrator, provider_manager=state)
    assert _handle_slash_command("/provider llama-server", ctx)
    assert state.snapshot().name == orchestrator.get_active_provider_name() == "llama-server"
    assert orchestrator.get_provider() is state.snapshot()
    assert orchestrator.get_active_provider() is state.snapshot()
    assert _handle_slash_command("/model new", ctx)
    assert config.model == state.snapshot().snapshot.model_id == "new"
    state.begin_turn("turn-1")
    try:
        _handle_slash_command("/model old", ctx)
        assert "CONFLICT_ACTIVE_TURN" in capsys.readouterr().out
        with pytest.raises(ProviderTransitionError):
            orchestrator.switch_provider("claude")
        assert state.snapshot().name == "llama-server" and config.model == "new"
    finally:
        state.end_turn("turn-1")


def test_jsonl_invalid_model_or_command_does_not_break_reader(monkeypatch):
    server = _make_server(Provider(), [])
    server._chat_active = False
    server._config.model = "old"
    server._provider_manager = manager()
    server._git_ops = Mock()
    sent = []
    monkeypatch.setattr("local_cli.server._send", sent.append)
    monkeypatch.setattr("local_cli.updater.check_for_updates", lambda: (False, ""))
    commands = [{"id": 1, "type": "switch_model", "model": {"unexpected": 47}},
                {"id": 2, "type": "command", "command": None},
                {"id": 3, "type": "models"}]
    monkeypatch.setattr("local_cli.server.sys.stdin", iter(json.dumps(c) for c in commands))
    server.run()
    assert next(m for m in sent if m.get("id") == 1)["code"] == "INVALID_MODEL"
    assert next(m for m in sent if m.get("id") == 2)["type"] == "error"
    assert next(m for m in sent if m.get("id") == 3)["type"] == "models"
    assert server._provider_manager.snapshot().snapshot.provider_revision == 1
