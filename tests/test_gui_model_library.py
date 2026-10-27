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


def test_server_update_errors_are_correlated_and_sanitized(monkeypatch):
    def fail(**_arguments):
        raise RuntimeError("private-provider-response-secret")

    frames = []
    monkeypatch.setattr("local_cli.server._send", frames.append)
    monkeypatch.setattr("local_cli.server.update_catalog", fail)
    server = JsonLineServer.__new__(JsonLineServer)
    server._handle_update_catalog(37)
    assert frames[-1]["id"] == 37
    assert frames[-1]["type"] == "error"
    assert frames[-1]["code"] == "MODEL_CATALOG_UPDATE_FAILED"
    assert "secret" not in json.dumps(frames)


def test_server_update_unavailable_is_not_empty_success(monkeypatch):
    seen, frames = [], []

    def unavailable(**arguments):
        seen.append(arguments)
        raise model_search.ModelSearchUnavailable("private internal detail")

    monkeypatch.setattr("local_cli.server._send", frames.append)
    monkeypatch.setattr("local_cli.server.update_catalog", unavailable)
    server = JsonLineServer.__new__(JsonLineServer)
    server._handle_update_catalog(59)
    assert seen[0]["raise_on_error"] is True
    assert frames[-1] == {"id": 59, "type": "error", "code": "MODEL_LIBRARY_UNAVAILABLE",
                          "message": "The model library is unavailable. Try again."}
    assert not any(frame["type"] == "catalog_updated" for frame in frames)


def test_retired_category_is_folded_in_builtins_classification_and_legacy_cache(monkeypatch, tmp_path):
    import time

    cache = _cache(monkeypatch, tmp_path)
    old = {"updated_at": int(time.time()), "models": [
        {"name": "owned-language:1b", "category": "Japanese"},
        {"name": "owned-legacy:2b", "category": "日本語"},
        {"name": "owned-unknown:3b", "category": "Future category"},
    ]}
    original = json.dumps(old).encode()
    cache.write_bytes(original)
    merged, categories = model_catalog.get_merged_catalog()
    assert "Japanese" not in categories and "日本語" not in categories
    assert len(model_catalog.get_categories()) == len(set(model_catalog.get_categories()))
    assert all(entry["category"] not in ("Japanese", "日本語") for entry in model_catalog.get_catalog())
    assert {entry["name"]: entry["category"] for entry in merged if entry["name"].startswith("owned-")} == {
        "owned-language:1b": "Multilingual", "owned-legacy:2b": "Multilingual", "owned-unknown:3b": "Future category"}
    assert cache.read_bytes() == original  # Opening the catalog does not rewrite a user cache.
    assert model_catalog._classify_model("elyza-owned", [], "") == "Multilingual"
    assert model_catalog._classify_model("owned", ["japanese"], "") == "Multilingual"
    monkeypatch.setattr(model_search, "search_models", lambda **_arguments: [])
    model_catalog.update_catalog(raise_on_error=True)
    stored = json.loads(cache.read_text(encoding="utf-8"))
    assert all(entry["category"] not in ("Japanese", "日本語") for entry in stored["models"])


def test_retired_category_never_hides_a_locally_installed_model(monkeypatch, tmp_path):
    import time

    cache = _cache(monkeypatch, tmp_path)
    cache.write_text(json.dumps({"updated_at": int(time.time()), "models": [
        {"name": "owned-language:1b", "display": "Owned language", "category": "Japanese"}]}), encoding="utf-8")
    frames = []
    monkeypatch.setattr("local_cli.server._send", frames.append)
    server = JsonLineServer.__new__(JsonLineServer)
    server._client = SimpleNamespace(list_models=lambda: [{"name": "owned-language:1b"}, {"name": "other:2b"}])
    server._handle_catalog(71)
    data = frames[-1]["data"]
    model = next(entry for entry in data["models"] if entry["name"] == "owned-language:1b")
    assert model["installed"] is True and model["category"] == "Multilingual"
    assert any(entry["name"] == "other:2b" and entry["installed"] for entry in data["models"])
    assert "Japanese" not in data["categories"]
