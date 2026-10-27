"""Public catalog pagination, offline retention, and exact variant identities."""
import json
import time
from urllib.parse import parse_qs, urlparse
from unittest.mock import MagicMock

import pytest

from local_cli import model_library as library
from local_cli.model_search import ModelSearchUnavailable
from local_cli.server import JsonLineServer


def card(name, tags="tools", sizes="3b", description="Owned fixture"):
    return f'<li class="border"><a href="/library/{name}"><h2>{name}</h2><p>{description}</p>' + ''.join(
        f'<span>{s}</span>' for s in [*tags.split(), *sizes.split()]) + '</a></li>'


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "_CACHE_DIR", tmp_path)


def test_current_markup_capabilities_cloud_and_embedding_not_name_guesses():
    html = card("owned", "tools vision") + card("owned-vector", "embedding", "") + card("owned-cloud", "cloud", "")
    html += '<li hx-get="/search?page=2&amp;q=owned"></li>'
    result = library.parse_search_page(html)
    assert result["nextPage"] == 2
    assert [m["kind"] for m in result["models"]] == ["llm", "embedding", "llm"]
    assert [m["cloud_only"] for m in result["models"]] == [False, False, True]
    assert result["models"][0]["size_gb"] == 0  # Family size is not fabricated.
    assert result["models"][1]["category"] == "Embedding"
    assert library.parse_search_page('<p data-result-count="0">No models</p>')["models"] == []
    with pytest.raises(ModelSearchUnavailable):
        library.parse_search_page('<html>A changed website or proxy error</html>')


def test_http_uses_actual_fragment_pagination_and_fixed_origin(monkeypatch):
    requests = []
    response = MagicMock()
    response.__enter__.return_value.geturl.return_value = "https://ollama.com/search"
    response.__enter__.return_value.read.return_value = card("owned").encode()
    def open_url(request, timeout):
        requests.append((request, timeout))
        return response
    monkeypatch.setattr(library.urllib.request, "urlopen", open_url)
    result = library.search_library("a & b", page=3, kind="embedding", local=True)
    request, timeout = requests[0]
    assert request.get_header("Hx-request") == "true"
    assert urlparse(request.full_url).hostname == "ollama.com"
    assert parse_qs(urlparse(request.full_url).query) == {"q": ["a & b"], "page": ["3"], "o": ["popular"], "c": ["local", "embedding"]}
    assert result["page"] == 3 and result["models"] == []
    assert timeout <= 20


def test_variants_keep_exact_tags_and_real_sizes_with_cloud_disabled():
    html = '''<a href="/library/owned:3b-q4_K_M">owned:3b-q4_K_M • 1.8GB • 32K context window • Text input</a>
      <a href="/library/owned:3b-q4_K_M">owned:3b-q4_K_M</a>
      <a href="/library/owned:tiny-fp16">owned:tiny-fp16 • 700MB • 512 context window</a>
      <a href="/library/owned:cloud">owned:cloud Cloud</a>
      <a href="/library/other:1b">other:1b 2GB</a>
      <a href="/library/owned:../../escape">bad</a>'''
    variants = library.parse_variants(html, "owned")
    assert len(variants) == 3
    assert variants[0] == dict(name="owned:3b-q4_K_M", size_gb=1.8, size_label="1.8GB", cloud_only=False, context_length=32768)
    assert variants[1]["size_gb"] == .7 and variants[1]["context_length"] == 512
    assert variants[2]["cloud_only"] is True and variants[2]["size_gb"] == 0


def test_invalid_requests_never_fetch_or_select_arbitrary_urls(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Network must not be reached")
    monkeypatch.setattr(library, "_fetch", forbidden)
    for family in ("../secret", "https://other.test", "owner/model", "owned:1b", None):
        with pytest.raises(ValueError):
            library.model_variants(family)
    for args in (dict(page=0), dict(page=True), dict(page=1001), dict(local=1), dict(kind="unknown"), dict(capability="http://other"), dict(query="x" * 201)):
        with pytest.raises(ValueError):
            library.search_library(**args)


def test_page_cache_survives_age_outage_and_failed_refresh(monkeypatch):
    monkeypatch.setattr(library, "_fetch", lambda *args: card("owned"))
    first = library.search_library()
    paths = list((library._CACHE_DIR / "library/pages").glob("*.json"))
    assert len(paths) == 1
    cached = json.loads(paths[0].read_text(encoding="utf-8"))
    cached["syncedAt"] = 1
    paths[0].write_text(json.dumps(cached), encoding="utf-8")
    original = paths[0].read_bytes()
    def offline(*args):
        raise ModelSearchUnavailable("private response")
    monkeypatch.setattr(library, "_fetch", offline)
    second = library.search_library(refresh=True)
    assert first["models"] == second["models"]
    assert second["offline"] and second["stale"]
    assert paths[0].read_bytes() == original


def test_full_sync_walks_to_end_and_can_search_entire_snapshot_offline(monkeypatch):
    calls = []
    def fetch(path, params):
        calls.append(params["page"])
        if params["page"] == 1:
            return card("owned-one") + '<li hx-get="/search?page=2"></li>'
        return card("owned-two", "embedding", description="Find this source") + card("owned-cloud", "cloud", "")
    monkeypatch.setattr(library, "_fetch", fetch)
    progress = []
    result = library.synchronize_catalog(progress=progress.append)
    assert calls == [1, 2] and progress == [1, 3] and result["total"] == 3
    def forbidden(*args):
        raise AssertionError("Fresh complete snapshot should be locally searchable")
    monkeypatch.setattr(library, "_fetch", forbidden)
    result = library.search_library("Find this", kind="embedding")
    assert [m["name"] for m in result["models"]] == ["owned-two"]
    assert result["nextPage"] is None and not result["offline"]
    assert result["source"] == "snapshot"
    assert all(not m["cloud_only"] for m in library.search_library()["models"])
    path = library._CACHE_DIR / "library/inventory.json"
    inventory = json.loads(path.read_text(encoding="utf-8"))
    inventory["syncedAt"] = 1
    path.write_text(json.dumps(inventory), encoding="utf-8")
    monkeypatch.setattr(library, "_fetch", lambda *args: (_ for _ in ()).throw(ModelSearchUnavailable()))
    result = library.search_library("Find this", kind="embedding", refresh=True)
    assert result["offline"] and result["stale"] and result["models"][0]["name"] == "owned-two"


def test_partial_sync_and_repeated_pages_never_overwrite_last_complete_inventory(monkeypatch):
    inventory = library._CACHE_DIR / "library/inventory.json"
    inventory.parent.mkdir(parents=True)
    original = json.dumps(dict(schema=1, syncedAt=int(time.time()), models=[])).encode()
    inventory.write_bytes(original)
    def fetch(path, params):
        return card("owned") + f'<li hx-get="/search?page={params["page"] + 1}"></li>'
    monkeypatch.setattr(library, "_fetch", fetch)
    with pytest.raises(ModelSearchUnavailable):
        library.synchronize_catalog()
    assert inventory.read_bytes() == original
    def partial(path, params):
        if params["page"] == 2:
            raise ModelSearchUnavailable("private details")
        return card("owned") + '<li hx-get="/search?page=2"></li>'
    monkeypatch.setattr(library, "_fetch", partial)
    with pytest.raises(ModelSearchUnavailable):
        library.synchronize_catalog()
    assert inventory.read_bytes() == original


def test_server_errors_correlate_to_library_without_leaking_provider_response(monkeypatch):
    server = JsonLineServer.__new__(JsonLineServer)
    frames = []
    monkeypatch.setattr("local_cli.server._send", frames.append)
    def fail(*args, **kwargs):
        raise RuntimeError("private-provider-details")
    monkeypatch.setattr("local_cli.server.search_library", fail)
    monkeypatch.setattr("local_cli.server.model_variants", fail)
    server._handle_library_search(31, {})
    server._handle_library_variants(32, {"family": "owned"})
    assert [f["id"] for f in frames] == [31, 32]
    assert [f["code"] for f in frames] == ["MODEL_LIBRARY_UNAVAILABLE", "MODEL_VARIANTS_UNAVAILABLE"]
    assert "private" not in json.dumps(frames)
