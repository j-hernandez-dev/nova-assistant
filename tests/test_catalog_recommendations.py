"""Recommendations come from every public family and measured hardware."""
import time
from types import SimpleNamespace

import pytest

from local_cli import model_library as library
from local_cli import model_recommendations as recommendations
from local_cli.model_search import ModelSearchUnavailable
from local_cli.server import JsonLineServer


def family(name, kind="llm", cloud=False):
    return dict(name=name, display=name, description="Owned public model", kind=kind,
        tags=["embedding"] if kind == "embedding" else ["tools"], cloud_only=cloud)


def variant(name, size, cloud=False):
    return dict(name=name, size_gb=size, size_label=f"{size}GB", cloud_only=cloud, context_length=8192)


def setup(monkeypatch, families, variants):
    inventory = dict(syncedAt=int(time.time()), models=families)
    monkeypatch.setattr(library, "cached_inventory", lambda: inventory)
    def load(name):
        return dict(variants=variants[name], offline=False, stale=False)
    monkeypatch.setattr(library, "model_variants", load)
    return inventory


def test_every_eligible_public_family_is_considered_including_embeddings_and_more_than_three(monkeypatch):
    families = [family(f"new-owned-{i}") for i in range(6)] + [family("new-vector", "embedding"), family("owned-cloud", cloud=True), family("huge")]
    variants = {m["name"]: [variant(m["name"] + ":4b-q4_K_M", 2.5)] for m in families}
    variants["huge"] = [variant("huge:70b", 40)]
    setup(monkeypatch, families, variants)
    progress = []
    models, status = recommendations.recommend_catalog_models(dict(ram_gb=16),
        installed=["new-owned-0:4b-q4_K_M"], progress=lambda rows, state: progress.append((rows, state)))
    assert len(models) == 7
    assert {m["family"] for m in models} == {m["name"] for m in families[:7]}
    assert any(m["kind"] == "embedding" for m in models)
    assert next(m for m in models if m["family"] == "new-owned-0")["installed"]
    assert status["phase"] == "complete" and status["scanned"] == status["total"] == 8
    assert all(m["estimated_memory_gb"] <= status["budget_gb"] for m in models)
    assert progress[0][1]["phase"] == "catalog"


def test_memory_changes_variant_choice_without_recommending_cloud_extreme_quantization_or_unknown_sizes(monkeypatch):
    model = family("owned")
    variants = {"owned": [variant("owned:1b", .8), variant("owned:8b-q4_K_M", 5),
        variant("owned:8b-q8_0", 8), variant("owned:70b-iq2_xxs", 1),
        variant("owned:100b-cloud", .1, cloud=True), variant("owned:unknown", 0)]}
    setup(monkeypatch, [model], variants)
    low, _ = recommendations.recommend_catalog_models(dict(ram_gb=4))
    high, _ = recommendations.recommend_catalog_models(dict(ram_gb=32))
    assert low[0]["name"] == "owned:1b"
    assert high[0]["name"] == "owned:8b-q4_K_M"
    assert high[0]["reason"] == "MEMORY_FIT"


def test_unknown_or_no_available_memory_never_fabricates_fit_or_starts_network(monkeypatch):
    def forbidden():
        raise AssertionError("No catalog needed without memory evidence")
    monkeypatch.setattr(library, "cached_inventory", forbidden)
    models, status = recommendations.recommend_catalog_models(dict(ram_gb=None, vram_largest_available_bytes=100 * 1024**3))
    assert models == [] and status["phase"] == "memory_unknown"
    models, status = recommendations.recommend_catalog_models(dict(ram_gb=16, ram_available_bytes=0))
    assert models == [] and status["budget_gb"] == 0


def test_available_ram_limits_fit_and_vram_is_not_added_to_system_ram(monkeypatch):
    setup(monkeypatch, [family("owned")], {"owned": [variant("owned:8b", 5)]})
    models, status = recommendations.recommend_catalog_models(dict(ram_gb=16, ram_available_bytes=3 * 1024**3,
        vram_largest_available_bytes=80 * 1024**3))
    assert models == []
    assert status["budget_gb"] < 3
    models, _ = recommendations.recommend_catalog_models(dict(ram_gb=16, vram_largest_available_bytes=10 * 1024**3))
    assert models[0]["gpu_fit"]


def test_stale_offline_catalog_reuses_saved_variants_and_reports_unverified_families(monkeypatch):
    inventory = setup(monkeypatch, [family("owned"), family("missing")], {})
    inventory["syncedAt"] = 1
    monkeypatch.setattr(library, "synchronize_catalog", lambda **kw: (_ for _ in ()).throw(ModelSearchUnavailable()))
    def cached(name):
        if name == "missing":
            raise ModelSearchUnavailable()
        return dict(variants=[variant("owned:1b", .8)], offline=True, stale=True)
    monkeypatch.setattr(library, "cached_model_variants", cached)
    rows, status = recommendations.recommend_catalog_models(dict(ram_gb=8))
    assert [r["name"] for r in rows] == ["owned:1b"]
    assert status["offline"] and status["stale"] and status["unavailable"] == 1


def test_network_outage_is_bounded_by_worker_count_instead_of_a_timeout_per_family(monkeypatch):
    setup(monkeypatch, [family(f"owned-{n}") for n in range(100)], {})
    calls = []
    def offline(name):
        calls.append(name)
        raise library.ModelLibraryNetworkUnavailable()
    monkeypatch.setattr(library, "model_variants", offline)
    monkeypatch.setattr(library, "cached_model_variants", lambda name: (_ for _ in ()).throw(ModelSearchUnavailable()))
    rows, status = recommendations.recommend_catalog_models(dict(ram_gb=16))
    assert len(calls) <= 4 and not rows
    assert status["unavailable"] == 100 and status["offline"]


def test_server_progress_and_terminal_keep_request_identity_and_exact_installed_tag(monkeypatch):
    setup(monkeypatch, [family("owned")], {"owned": [variant("owned:1b", .8)]})
    monkeypatch.setattr("local_cli.system_info.get_system_info", lambda: dict(ram_gb=8))
    frames = []
    monkeypatch.setattr("local_cli.server._send", frames.append)
    server = JsonLineServer.__new__(JsonLineServer)
    server._client = SimpleNamespace(list_models=lambda: [dict(name="owned:other")])
    server._handle_recommend(123)
    assert all(f["id"] == 123 for f in frames)
    assert frames[0]["type"] == "recommend_progress" and frames[-1]["type"] == "recommend"
    assert frames[-1]["models"][0]["installed"] is False
    assert frames[-1]["recommendation"]["phase"] == "complete"
