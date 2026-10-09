"""Observable JSONL behavior before replacing the server's agentic path."""

import json
from types import SimpleNamespace

from local_cli.server import JsonLineServer
from tests.test_nova_core_phase7_server_legacy import _server_stub


def test_legacy_reader_keeps_ready_shape_and_recovers_after_bad_json(monkeypatch):
    server, sent = _server_stub(monkeypatch)
    server._config.model = "local"
    server._config.provider = "ollama"
    server._tools = [SimpleNamespace(name="bash"), SimpleNamespace(name="read")]
    server._git_ops = SimpleNamespace(capability=lambda: SimpleNamespace(value="UNAVAILABLE"))
    server._conversation_store = SimpleNamespace(info=lambda: {"message_count": 2})
    monkeypatch.setattr("local_cli.updater.check_for_updates", lambda: (False, ""))
    monkeypatch.setattr("local_cli.server.sys.stdin", iter((
        "{broken", json.dumps({"id": 17, "type": "unknown"}),
    )))

    server.run()

    assert sent[0]["type"] == "ready"
    assert sent[0]["tools"] == ["bash", "read"]
    assert sent[0]["git_capability"] == "UNAVAILABLE"
    assert sent[0]["resumable"] == {"message_count": 2}
    assert sent[1] == {"type": "error", "message": "Invalid JSON"}
    assert sent[2] == {"id": 17, "type": "error", "message": "Unknown type: unknown"}


def test_legacy_chat_empty_input_is_error_without_done(monkeypatch):
    from tests.test_server import _make_server
    from unittest.mock import MagicMock

    server = _make_server(MagicMock(name="provider"), [])
    sent = []
    monkeypatch.setattr("local_cli.server._send", sent.append)

    server._handle_chat(23, "   ")

    assert sent == [{"id": 23, "type": "error", "message": "Empty message"}]
    assert [item["role"] for item in server._messages] == ["system"]


def test_application_adapter_failure_is_typed_and_reader_continues(monkeypatch):
    server, sent = _server_stub(monkeypatch)
    server._config.model = "local"
    server._config.provider = "ollama"
    server._tools = [SimpleNamespace(name="bash")]
    server._git_ops = SimpleNamespace(capability=lambda: SimpleNamespace(value="UNAVAILABLE"))
    server._conversation_store = SimpleNamespace(info=lambda: {})
    class FailingAdapter:
        session_id = "active"
        closed = False
        def start(self):
            pass
        def handle(self, _request):
            raise RuntimeError("provider secret must not leak")
        def close(self):
            self.closed = True
    server._app_adapter = FailingAdapter()
    monkeypatch.setattr("local_cli.updater.check_for_updates", lambda: (False, ""))
    monkeypatch.setattr("local_cli.server.sys.stdin", iter((
        json.dumps({"id": 1, "type": "get_snapshot"}),
        json.dumps({"id": 2, "type": "status"}),
    )))
    server.run()
    assert server._app_adapter.closed is True
    errors = [frame for frame in sent if frame.get("type") == "error"]
    assert [frame["id"] for frame in errors] == [1, 2]
    assert all(frame["code"] == "APPLICATION_ADAPTER_FAILED" and
               "secret" not in frame["message"] for frame in errors)
