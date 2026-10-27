"""Hardware-fit suggestions drawn exclusively from the public library.

Published download sizes are observations; runtime memory is a conservative
estimate, not a benchmark or a guarantee. No inference or installation is run.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import math
import re
import threading
import time

from local_cli import model_library
from local_cli.model_search import ModelSearchUnavailable

_RECOMMENDING = threading.Lock()


def _positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def memory_budget(info):
    total = info.get("ram_total_bytes")
    if not _positive(total):
        ram = info.get("ram_gb")
        if not _positive(ram):
            return None
        total = ram * 1024**3
    # Keep a substantial reserve for the OS, desktop and other applications.
    ratio = .5 if total <= 8 * 1024**3 else .6 if total <= 16 * 1024**3 else .7
    budget = total * ratio
    available = info.get("ram_available_bytes")
    if type(available) in (int, float) and math.isfinite(available) and 0 <= available <= total:
        budget = min(budget, available * .85)
    return budget / 1e9


def estimated_memory(variant, kind):
    size = variant.get("size_gb")
    if not _positive(size):
        return None
    return size * 1.25 + (.25 if kind == "embedding" else .75)


def _variant_priority(variant):
    tag = variant["name"].partition(":")[2].lower()
    count = re.match(r"(\d+(?:\.\d+)?)(b|m)(?:$|[-_])", tag)
    params = float(count[1]) * (1 if count[2] == "b" else .001) if count else 0
    quant = re.search(r"(?:^|[-_])(?:i?q)(\d+)", tag)
    # Favor balanced published quantizations rather than fp16 expansion of the
    # same parameter count. Aliases with an unspecified quantization stay valid.
    quality = {4: 6, 5: 5, 6: 4, 8: 3}.get(int(quant[1]), 1) if quant else 2
    return params, quality, -variant["size_gb"], variant["name"]


def fitting_variant(model, variants, budget):
    eligible = []
    for variant in variants:
        name = variant.get("name", "")
        if not isinstance(name, str) or not name.startswith(model["name"] + ":") or variant.get("cloud_only"):
            continue
        # Very low precision variants can fit by sacrificing substantial quality;
        # they remain discoverable in All, without being default suggestions.
        quant = re.search(r"(?:^|[-_])(?:i?q)(\d+)", name.partition(":")[2], re.I)
        if quant and int(quant[1]) < 4:
            continue
        memory = estimated_memory(variant, model.get("kind", "llm"))
        if memory is not None and memory <= budget:
            eligible.append(variant)
    return max(eligible, key=_variant_priority) if eligible else None


def recommend_catalog_models(info, *, installed=(), progress=None):
    """Evaluate every local family, reusing the library's cached variant metadata."""
    if not _RECOMMENDING.acquire(blocking=False):
        raise ModelSearchUnavailable("Model recommendations are already being prepared.")
    try:
        budget = memory_budget(info)
        status = dict(phase="catalog", scanned=0, total=0, unavailable=0, offline=False,
            stale=False, syncedAt=0, budget_gb=round(budget or 0, 2))
        def emit(models):
            if progress:
                progress(models, dict(status))
        if budget is None:
            status["phase"] = "memory_unknown"
            return [], status
        if budget == 0:
            status["phase"] = "complete"
            return [], status
        emit([])
        inventory = model_library.cached_inventory()
        if not inventory["syncedAt"] or time.time() - inventory["syncedAt"] >= model_library._TTL:
            try:
                model_library.synchronize_catalog(progress=lambda _count: emit([]))
                inventory = model_library.cached_inventory()
            except ModelSearchUnavailable:
                if not inventory["syncedAt"]:
                    raise
                status["offline"] = True
        status.update(syncedAt=inventory["syncedAt"], stale=time.time() - inventory["syncedAt"] >= model_library._TTL,
            phase="variants")
        families = [m for m in inventory["models"] if not m.get("cloud_only")]
        status["total"] = len(families)
        emit([])
        results = {}
        positions = {m["name"]: i for i, m in enumerate(families)}
        installed = set(installed)
        gpu_memory = info.get("vram_largest_available_bytes")
        gpu_budget = gpu_memory * .85 / 1e9 if _positive(gpu_memory) else 0
        offline = threading.Event()
        if status["offline"]:
            offline.set()
        def load_variants(family):
            if offline.is_set():
                return model_library.cached_model_variants(family)
            try:
                data = model_library.model_variants(family)
                if data.get("offline"):
                    offline.set()
                return data
            except model_library.ModelLibraryNetworkUnavailable:
                offline.set()
                raise
        def ordered():
            values = sorted(results.values(), key=lambda m: (not m["gpu_fit"], positions[m["family"]]))
            return [{**model, "rank": i + 1} for i, model in enumerate(values)]
        # Small concurrency keeps first use responsive without flooding the site.
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="nova-model-fit") as pool:
            jobs = {pool.submit(load_variants, m["name"]): m for m in families}
            last_emit = 0
            for job in as_completed(jobs):
                model = jobs[job]
                status["scanned"] += 1
                try:
                    data = job.result()
                    status["offline"] |= data.get("offline", False)
                    status["stale"] |= data.get("stale", False)
                    variant = fitting_variant(model, data["variants"], budget)
                    if variant:
                        name = variant["name"]
                        memory = estimated_memory(variant, model.get("kind", "llm"))
                        results[model["name"]] = dict(name=name, family=model["name"], display=model["display"],
                            description=model["description"], kind=model.get("kind", "llm"), tags=model.get("tags", []),
                            size_gb=variant["size_gb"], size_label=variant["size_label"],
                            context_length=variant.get("context_length", 0), estimated_memory_gb=round(memory, 2),
                            gpu_fit=bool(gpu_budget and memory <= gpu_budget),
                            reason="MEMORY_FIT", installed=name in installed)
                except Exception:
                    # Missing or changed variant metadata is not proof of fit.
                    status["unavailable"] += 1
                status["offline"] |= offline.is_set()
                if time.monotonic() - last_emit >= .25 or status["scanned"] == status["total"]:
                    emit(ordered())
                    last_emit = time.monotonic()
        status["phase"] = "complete"
        return ordered(), status
    finally:
        _RECOMMENDING.release()
