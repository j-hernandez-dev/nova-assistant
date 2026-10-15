"""Freeze observable compatibility before retiring obsolete composers."""

from types import SimpleNamespace
from unittest.mock import Mock

from local_cli.cli import _handle_application_slash_command
from tests.test_nova_core_phase11_adapter import _adapter, _wait_for
from tests.test_nova_core_phase4_session import ScriptedProvider


def test_cli_help_and_exit_need_only_visual_configuration(capsys):
    ctx = SimpleNamespace(config=SimpleNamespace(mascot="off"), current_mode="agent")
    assert _handle_application_slash_command("/help", None, ctx)
    output = capsys.readouterr().out
    for name in ("/rag", "/model", "/knowledge", "/plan", "/exit"):
        assert name in output
    assert not _handle_application_slash_command("/exit", None, ctx)
    assert capsys.readouterr().out == "Goodbye!\n"


def test_legacy_jsonl_chat_clear_resume_and_model_share_application(tmp_path):
    adapter, app, sent = _adapter(tmp_path, ScriptedProvider(["hola"]))
    try:
        assert adapter.handle({"id": 1, "type": "chat", "content": "hello"})
        _wait_for(sent, "done", request_id=1)
        before = app.get_snapshot(adapter.session_id)
        assert len(before.turns) == 1
        assert before.transcript[-1]["content"] == "hola"
        assert adapter.handle({"id": 2, "type": "command", "command": "/status"})
        assert _wait_for(sent, "status", request_id=2)["data"]["messages"] == 1
        assert adapter.handle({"id": 3, "type": "command", "command": "/clear"})
        assert _wait_for(sent, "cleared", request_id=3)
        assert not any(m["role"] == "user" for m in app.get_snapshot(adapter.session_id).transcript)
    finally:
        adapter.close()


def test_legacy_empty_input_is_error_without_turn(tmp_path):
    adapter, app, sent = _adapter(tmp_path, ScriptedProvider([]))
    try:
        assert adapter.handle({"id": 1, "type": "chat", "content": "   "})
        assert sent[-1]["type"] == "error"
        assert not app.get_snapshot(adapter.session_id).turns
    finally:
        adapter.close()


def test_legacy_model_admin_keeps_progress_and_delete_frames(monkeypatch):
    from tests.test_server import _make_server
    provider = Mock(name="provider")
    provider.name = "test"
    server = _make_server(provider, [])
    server._client.pull_model.return_value = iter([
        {"status": "starting"}, {"status": "downloading", "completed": 2, "total": 8}])
    frames = []
    monkeypatch.setattr("local_cli.server._send", frames.append)
    try:
        server._handle_pull_model(4, "local:7b")
        server._handle_delete_model(5, "local:7b")
        assert frames == [
            {"id": 4, "type": "pull_start", "model": "local:7b"},
            {"id": 4, "type": "pull_progress", "model": "local:7b",
             "status": "starting", "completed": None, "total": None},
            {"id": 4, "type": "pull_progress", "model": "local:7b",
             "status": "downloading", "completed": 2, "total": 8},
            {"id": 4, "type": "pull_done", "model": "local:7b"},
            {"id": 5, "type": "delete_done", "model": "local:7b"}]
        server._client.pull_model.assert_called_once_with("local:7b")
        server._client.delete_model.assert_called_once_with("local:7b")
    finally:
        server._app_adapter.close()


def test_legacy_updater_admin_keeps_check_and_perform_separate(monkeypatch):
    from tests.test_server import _make_server
    provider = Mock(name="provider")
    provider.name = "test"
    check, perform = Mock(return_value=(True, "available")), Mock(return_value=(True, "updated"))
    monkeypatch.setattr("local_cli.updater.check_for_updates", check)
    monkeypatch.setattr("local_cli.updater.perform_update", perform)
    server = _make_server(provider, [])
    frames = []
    monkeypatch.setattr("local_cli.server._send", frames.append)
    try:
        server._handle_check_update(6)
        perform.assert_not_called()
        server._handle_do_update(7)
        assert frames == [
            {"id": 6, "type": "update_status", "has_updates": True, "message": "available"},
            {"id": 7, "type": "updating"},
            {"id": 7, "type": "update_done", "success": True, "message": "updated"}]
        check.assert_called_once()
        perform.assert_called_once()
    finally:
        server._app_adapter.close()


def test_shared_admin_rejects_effects_during_turn_without_interrupting_it(tmp_path):
    from threading import Event
    import pytest
    from local_cli.application.auxiliary import AuxiliaryConflict, AuxiliaryServices
    entered, release = Event(), Event()
    def runner(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return "done"
    adapter, app, sent = _adapter(tmp_path, object(), runner=runner)
    manager, check, perform = Mock(), Mock(return_value=(False, "no update")), Mock()
    app._auxiliary_services = AuxiliaryServices(model_manager=manager,
        updater_check=check, updater_perform=perform)
    try:
        adapter.handle({"id": 8, "type": "chat", "content": "work"})
        assert entered.wait(2)
        before = app.get_snapshot(adapter.session_id)
        for name in ("model_install", "model_delete", "update_perform"):
            with pytest.raises(AuxiliaryConflict):
                app.execute_auxiliary(adapter.session_id, name, {"model": "local:7b"})
        assert app.execute_auxiliary(adapter.session_id, "update_check").data["available"] is False
        manager.install_model.assert_not_called()
        manager.delete_model.assert_not_called()
        perform.assert_not_called()
        assert app.get_snapshot(adapter.session_id) == before
        release.set()
        _wait_for(sent, "done", request_id=8)
    finally:
        release.set()
        adapter.close()
