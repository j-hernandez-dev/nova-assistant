from unittest.mock import Mock

import pytest

from local_cli.ollama_client import OllamaConnectionError
from local_cli.server import JsonLineServer


@pytest.mark.parametrize("models", [[], [{"name": "target:8b", "size": 32}]])
def test_catalog_includes_exact_authoritative_inventory_once(monkeypatch, models):
    server = JsonLineServer.__new__(JsonLineServer)
    server._client = Mock()
    server._client.list_models.return_value = models
    frames = []
    monkeypatch.setattr("local_cli.server._send", frames.append)
    monkeypatch.setattr("local_cli.server.get_merged_catalog", lambda: ([{"name": "target", "category": "Test"}], ["Test"]))
    server._handle_catalog("owned-inventory")
    assert frames[-1]["data"]["installedModels"] == models
    assert frames[-1]["id"] == "owned-inventory"
    server._client.list_models.assert_called_once()


def test_unavailable_inventory_is_not_presented_as_successful_empty_list(monkeypatch):
    server = JsonLineServer.__new__(JsonLineServer)
    server._client = Mock()
    server._client.list_models.side_effect = OllamaConnectionError("offline")
    frames = []
    monkeypatch.setattr("local_cli.server._send", frames.append)
    monkeypatch.setattr("local_cli.server.get_merged_catalog", lambda: ([], []))
    server._handle_catalog("owned-inventory")
    assert frames[-1]["data"]["installedModels"] is None
    server._client.list_models.assert_called_once()
