"""System hardware detection and model recommendation.

Projects the shared hardware probes into the legacy recommendation UI.
Unknown RAM remains None; GPU memory is never inferred from system RAM.
"""

import platform


def get_system_info() -> dict:
    """Detect system hardware relevant for model selection.

    Returns:
        Dict with keys: ram_gb, chip, gpu, os, arch.
    """
    from local_cli.infrastructure.capabilities import probe_memory, probe_gpu
    memory = probe_memory()
    devices, total, available = probe_gpu()
    return {"ram_gb": memory.total.value // (1024 ** 3) if memory.total.value is not None else None,
            "ram_status": memory.total.status.value, "ram_source": memory.source,
            "ram_error": memory.total.reason, "chip": "",
            "gpu": ", ".join(device["name"] for device in (devices.value or [])),
            "gpu_status": devices.status.value,
            "vram_total_bytes": total.value, "vram_available_bytes": available.value,
            "os": platform.system(), "arch": platform.machine()}


def _usable_ram_gb(ram_gb: int) -> float:
    """Estimate usable RAM for models (leave room for OS + apps)."""
    if ram_gb <= 8:
        return ram_gb * 0.5
    if ram_gb <= 16:
        return ram_gb * 0.6
    return ram_gb * 0.7


# Model recommendations ordered by quality (best first).
# Each entry: (name, display, min_gb, description, category)
_RECOMMENDATIONS = [
    ("qwen3.5:27b", "Qwen 3.5 27B", 17.0, "Best quality. Vision + thinking + tools.", "code"),
    ("qwen3:30b", "Qwen 3 30B", 18.5, "Strong reasoning. Great for agents.", "code"),
    ("qwen2.5-coder:32b", "Qwen 2.5 Coder 32B", 20.0, "Top-tier coding specialist.", "code"),
    ("qwen3.5:9b", "Qwen 3.5 9B", 5.5, "Strong all-rounder for its size.", "code"),
    ("qwen2.5-coder:14b", "Qwen 2.5 Coder 14B", 9.0, "Code specialist, great accuracy.", "code"),
    ("qwen3:14b", "Qwen 3 14B", 9.0, "Balanced reasoning + tools.", "code"),
    ("qwen3:8b", "Qwen 3 8B", 5.2, "Good baseline with tool calling.", "code"),
    ("qwen2.5-coder:7b", "Qwen 2.5 Coder 7B", 4.7, "Compact code model.", "code"),
    ("qwen3.5:4b", "Qwen 3.5 4B", 2.6, "Capable for its size.", "general"),
    ("qwen3:4b", "Qwen 3 4B", 2.6, "Lightweight with tools.", "general"),
    ("qwen3.5:2b", "Qwen 3.5 2B", 1.3, "Very compact, basic tasks.", "general"),
    ("qwen3.5:0.8b", "Qwen 3.5 0.8B", 0.5, "Minimal. Testing only.", "general"),
]


def recommend_models(
    ram_gb: int | None = None,
    purpose: str = "code",
    max_results: int = 3,
) -> list[dict]:
    """Recommend models based on available RAM.

    Args:
        ram_gb: Total system RAM in GB. Auto-detected if None.
        purpose: 'code' or 'general'.
        max_results: Maximum recommendations to return.

    Returns:
        List of dicts with name, display, size_gb, reason, rank fields.
        rank 1 = best recommendation.
    """
    if ram_gb is None:
        info = get_system_info()
        ram_gb = info.get("ram_gb")
    if ram_gb is None:
        return []  # Unknown memory is not evidence that a model fits.

    usable = _usable_ram_gb(ram_gb)
    results = []
    rank = 0

    for name, display, min_gb, desc, cat in _RECOMMENDATIONS:
        if min_gb > usable:
            continue

        rank += 1
        reason = desc
        if rank == 1:
            reason = f"Best for your {ram_gb}GB system. " + desc

        results.append({
            "name": name,
            "display": display,
            "size_gb": min_gb,
            "reason": reason,
            "rank": rank,
        })

        if len(results) >= max_results:
            break

    return results
