"""The model modal distinguishes library failure from an empty owned result."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from local_cli import model_catalog, model_search
from local_cli.server import JsonLineServer


def test_search_failure_preserves_legacy_fallback_and_strict_error(monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise OSError("private endpoint: do not publish this")

    monkeypatch.setattr(model_search.urllib.request, "urlopen", unavailable)
    assert model_search.search_models(query="owned") == []
    with pytest.raises(model_search.ModelSearchUnavailable) as failure:
        model_search.search_models(query="owned", raise_on_error=True)
    assert str(failure.value) == "Model library is unavailable."


def test_search_successful_empty_result_is_not_an_outage(monkeypatch):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b"<html><body>No matches.</body></html>"
    monkeypatch.setattr(model_search.urllib.request, "urlopen", lambda *_args, **_kwargs: response)
    assert model_search.search_models(query="owned", raise_on_error=True) == []


def _cache(monkeypatch, tmp_path):
    cache = tmp_path / "model_catalog.json"
    monkeypatch.setattr(model_catalog, "_CACHE_DIR", tmp_path)
    monkeypatch.setattr(model_catalog, "_CACHE_FILE", cache)
    return cache


def test_catalog_all_queries_unavailable_does_not_overwrite_cache(monkeypatch, tmp_path):
    cache = _cache(monkeypatch, tmp_path)
    original = b'{"updated_at": 1, "models": []}\n'
    cache.write_bytes(original)
    calls = []

    def unavailable(**arguments):
        calls.append(arguments)
        raise model_search.ModelSearchUnavailable("owned unavailable")

    monkeypatch.setattr(model_search, "search_models", unavailable)
    with pytest.raises(model_search.ModelSearchUnavailable):
        model_catalog.update_catalog(raise_on_error=True)
    assert len(calls) == 4
    assert all(call["raise_on_error"] is True for call in calls)
    assert cache.read_bytes() == original


def test_catalog_partial_response_can_refresh_without_fabricating_models(monkeypatch, tmp_path):
    cache = _cache(monkeypatch, tmp_path)
    calls = []

    def partial(**arguments):
        calls.append(arguments)
        if arguments.get("sort") != "hot":
            raise model_search.ModelSearchUnavailable("owned unavailable")
        return [{"name": "owned-model:1b", "description": "Owned fixture.",
                 "tags": ["tools"], "sizes": ["1b"], "pulls": 10}]

    monkeypatch.setattr(model_search, "search_models", partial)
    result = model_catalog.update_catalog(raise_on_error=True)
    stored = json.loads(cache.read_text(encoding="utf-8"))
    assert len(calls) == 4
    assert result["added"] == 1
    assert any(model["name"] == "owned-model:1b" for model in stored["models"])


def test_catalog_empty_valid_response_is_success(monkeypatch, tmp_path):
    cache = _cache(monkeypatch, tmp_path)
    monkeypatch.setattr(model_search, "search_models", lambda **_arguments: [])
    result = model_catalog.update_catalog(raise_on_error=True)
    assert result["added"] == 0
    assert cache.is_file()


def test_catalog_legacy_call_does_not_force_strict_search(monkeypatch, tmp_path):
    _cache(monkeypatch, tmp_path)
    calls = []

    def legacy(**arguments):
        calls.append(arguments)
        return []

    monkeypatch.setattr(model_search, "search_models", legacy)
    model_catalog.update_catalog()
    assert calls == [{"sort": "popular"}, {"sort": "hot"},
                     {"capability": "tools"}, {"capability": "code"}]


@pytest.mark.parametrize("operation,expected_code", [
    ("search", "MODEL_SEARCH_FAILED"),
    ("update", "MODEL_CATALOG_UPDATE_FAILED"),
])
def test_server_model_errors_are_correlated_and_sanitized(monkeypatch, operation, expected_code):
    def fail(**_arguments):
        raise RuntimeError("private-provider-response-secret")

    frames = []
    monkeypatch.setattr("local_cli.server._send", frames.append)
    monkeypatch.setattr("local_cli.server.search_models", fail)
    monkeypatch.setattr("local_cli.server.update_catalog", fail)
    server = JsonLineServer.__new__(JsonLineServer)
    if operation == "search":
        server._handle_search_models(37, "owned", "popular", "tools")
    else:
        server._handle_update_catalog(37)
    assert frames[-1]["id"] == 37
    assert frames[-1]["type"] == "error"
    assert frames[-1]["code"] == expected_code
    assert "secret" not in json.dumps(frames)


@pytest.mark.parametrize("operation", ["search", "update"])
def test_server_library_unavailable_is_not_empty_success(monkeypatch, operation):
    seen = []
    frames = []

    def unavailable(**arguments):
        seen.append(arguments)
        raise model_search.ModelSearchUnavailable("private internal detail")

    monkeypatch.setattr("local_cli.server._send", frames.append)
    monkeypatch.setattr("local_cli.server.search_models", unavailable)
    monkeypatch.setattr("local_cli.server.update_catalog", unavailable)
    server = JsonLineServer.__new__(JsonLineServer)
    if operation == "search":
        server._handle_search_models(59, "owned", "popular", "tools")
    else:
        server._handle_update_catalog(59)
    assert seen[0]["raise_on_error"] is True
    assert frames[-1] == {"id": 59, "type": "error", "code": "MODEL_LIBRARY_UNAVAILABLE",
                          "message": "The model library is unavailable. Try again."}
    assert not any(frame["type"] in ("search_results", "catalog_updated") for frame in frames)


def test_server_empty_search_response_is_a_correlated_success(monkeypatch):
    frames = []
    monkeypatch.setattr("local_cli.server._send", frames.append)
    monkeypatch.setattr("local_cli.server.search_models", lambda **_arguments: [])
    server = JsonLineServer.__new__(JsonLineServer)
    server._client = SimpleNamespace(list_models=lambda: [])
    server._handle_search_models(61, "owned", "popular", "")
    assert frames == [{"id": 61, "type": "search_results", "data": []}]
