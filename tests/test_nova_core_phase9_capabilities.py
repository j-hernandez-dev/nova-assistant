"""Real Windows RAM and isolated platform probes; no guessed VRAM/KV limits."""

import platform
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from local_cli.core.contracts import CapabilityStatus
from local_cli.core.models import ModelRuntimeSnapshot
from local_cli.infrastructure import capabilities as probes


def test_windows_api_success_and_zero_available_is_a_measurement(monkeypatch):
    monkeypatch.setattr(probes, "_windows_memory", lambda: (16 * 1024 ** 3, 0))
    memory = probes.probe_memory("Windows")
    assert memory.total.value == 16 * 1024 ** 3
    assert memory.available.value == 0
    assert memory.source == "Windows.GlobalMemoryStatusEx"


@pytest.mark.parametrize("failure", [OSError("secret"), AttributeError("unavailable API")])
def test_windows_probe_failure_is_unknown_with_source_and_safe_reason(monkeypatch, failure):
    monkeypatch.setattr(probes, "_windows_memory", Mock(side_effect=failure))
    memory = probes.probe_memory("Windows")
    assert memory.total.status is CapabilityStatus.UNKNOWN
    assert memory.total.value is None and memory.available.value is None
    assert "GlobalMemoryStatusEx" in memory.total.reason and "secret" not in memory.total.reason


def test_linux_memory_total_available_and_missing_available(monkeypatch):
    monkeypatch.setattr(probes.Path, "read_text", lambda *_args, **_kwargs: "MemTotal: 16384 kB\nMemAvailable: 1234 kB\n")
    memory = probes.probe_memory("Linux")
    assert memory.total.value == 16384 * 1024 and memory.available.value == 1234 * 1024
    monkeypatch.setattr(probes.Path, "read_text", lambda *_args, **_kwargs: "MemTotal: 16384 kB\n")
    assert probes.probe_memory("Linux").available.status is CapabilityStatus.UNKNOWN


def test_macos_does_not_claim_unified_memory_is_vram(monkeypatch):
    run = Mock(return_value=SimpleNamespace(stdout=str(32 * 1024 ** 3)))
    monkeypatch.setattr(probes.subprocess, "run", run)
    memory = probes.probe_memory("Darwin")
    assert memory.total.value == 32 * 1024 ** 3
    assert memory.available.value is None
    assert run.call_args.kwargs["timeout"] == 5 and run.call_args.kwargs["check"]


@pytest.mark.parametrize("system", ["Linux", "Darwin", "unsupported"])
def test_platform_errors_are_unknown(monkeypatch, system):
    monkeypatch.setattr(probes.Path, "read_text", Mock(side_effect=OSError()))
    monkeypatch.setattr(probes.subprocess, "run", Mock(side_effect=OSError()))
    assert probes.probe_memory(system).total.value is None


def test_nvidia_multiple_devices_keep_separate_evidence(monkeypatch):
    monkeypatch.setattr(probes.shutil, "which", lambda _: "nvidia-smi.exe")
    run = Mock(return_value=SimpleNamespace(stdout="GPU A, 8192, 2048\nGPU B, 4096, 0\n"))
    monkeypatch.setattr(probes.subprocess, "run", run)
    devices, total, available = probes.probe_gpu()
    assert len(devices.value) == 2
    assert total.value == 12288 * 1024 ** 2 and available.value == 2048 * 1024 ** 2
    assert "shell" not in run.call_args.kwargs


def test_gpu_missing_and_probe_failure_are_not_zero(monkeypatch):
    monkeypatch.setattr(probes.shutil, "which", lambda _: None)
    assert all(item.value is None for item in probes.probe_gpu())
    monkeypatch.setattr(probes.shutil, "which", lambda _: "nvidia-smi.exe")
    monkeypatch.setattr(probes.subprocess, "run", Mock(side_effect=OSError("secret")))
    assert all(item.value is None and "secret" not in item.reason for item in probes.probe_gpu())


def test_capability_unknown_model_quantization_and_resource_are_not_invented(tmp_path, monkeypatch):
    monkeypatch.setattr(probes.shutil, "which", lambda _: None)
    model = ModelRuntimeSnapshot("ollama", "model:7b-q4", 2)
    snapshot = probes.capture_capabilities(model=model, cwd=tmp_path)
    assert snapshot.provider_revision.value == 2 and snapshot.model_revision.value is None
    assert snapshot.quantization.value is None and snapshot.model_context_window.value is None
    assert snapshot.resource_context_window.value is None and snapshot.concurrency_limits.value is None
    assert snapshot.source and snapshot.captured_at.tzinfo
    configured = probes.capture_capabilities(model=model, cwd=tmp_path, resource_context_limit=8192)
    assert configured.resource_context_window.value == 8192
    assert configured.concurrency_limits.value is None  # OD-06 remains open.


@pytest.mark.skipif(platform.system() != "Windows", reason="native Windows smoke")
def test_real_windows_api_ram_and_both_legacy_projections():
    from local_cli.context_sizing import _system_ram_gb
    from local_cli.system_info import get_system_info
    memory = probes.probe_memory("Windows")
    assert memory.total.status is CapabilityStatus.KNOWN and memory.total.value > 0
    assert memory.available.status is CapabilityStatus.KNOWN
    assert _system_ram_gb() > 0 and get_system_info()["ram_gb"] > 0


def test_legacy_recommendation_failure_preserves_unknown(monkeypatch):
    from local_cli.context_sizing import _system_ram_gb
    from local_cli.system_info import get_system_info, recommend_models
    memory = probes.MemoryObservation(probes.Observation.unknown("failed"),
                                     probes.Observation.unknown("failed"), "mock")
    monkeypatch.setattr(probes, "probe_memory", lambda: memory)
    monkeypatch.setattr(probes.shutil, "which", lambda _: None)
    assert _system_ram_gb() is None
    assert get_system_info()["ram_gb"] is None and get_system_info()["ram_status"] == "UNKNOWN"
    assert recommend_models() == []
