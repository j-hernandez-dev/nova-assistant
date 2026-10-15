"""Read-only, platform-specific resource probes. Failure is never measured zero."""

from dataclasses import dataclass
from datetime import datetime, timezone
import platform
from pathlib import Path
import shutil
import subprocess

from local_cli.core.contracts import Observation, RuntimeCapabilitySnapshot
from local_cli.git_capability import detect_git_capability
from local_cli.legacy_contracts import legacy_shell_descriptor


@dataclass(frozen=True)
class MemoryObservation:
    total: Observation[int]
    available: Observation[int]
    source: str


def _windows_memory():
    import ctypes
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in (
                "total", "available", "page_total", "page_available",
                "virtual_total", "virtual_available", "extended_available")]
    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    api = ctypes.WinDLL("kernel32", use_last_error=True).GlobalMemoryStatusEx
    api.argtypes = [ctypes.POINTER(MemoryStatus)]
    api.restype = ctypes.c_int
    if not api(ctypes.byref(status)):
        raise ctypes.WinError(ctypes.get_last_error())
    return status.total, status.available


def probe_memory(system=None) -> MemoryObservation:
    system = system or platform.system()
    source = {"Windows": "Windows.GlobalMemoryStatusEx", "Linux": "Linux./proc/meminfo",
              "Darwin": "macOS.sysctl.hw.memsize"}.get(system, "unsupported_os")
    try:
        if system == "Windows":
            total, available = _windows_memory()
        elif system == "Linux":
            values = {}
            for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                key, value = line.split(":", 1)
                values[key] = int(value.strip().split()[0]) * 1024
            total, available = values["MemTotal"], values.get("MemAvailable")
        elif system == "Darwin":
            result = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True,
                                    text=True, timeout=5, check=True)
            total, available = int(result.stdout.strip()), None
        else:
            raise NotImplementedError("unsupported OS")
        if type(total) is not int or total <= 0 or (available is not None and
                (type(available) is not int or not 0 <= available <= total)):
            raise ValueError("invalid memory measurement")
        return MemoryObservation(Observation.known(total),
            Observation.known(available) if available is not None else
            Observation.unknown(source + ": available memory not measured"), source)
    except Exception as exc:
        reason = source + ": probe failed (" + type(exc).__name__ + ")"
        return MemoryObservation(Observation.unknown(reason), Observation.unknown(reason), source)


def probe_gpu():
    executable = shutil.which("nvidia-smi")
    if not executable:
        return (Observation.unknown("GPU probe: NVIDIA adapter unavailable"),
                Observation.unknown("VRAM not measured"), Observation.unknown("VRAM not measured"))
    try:
        result = subprocess.run([executable, "--query-gpu=name,memory.total,memory.free",
                                 "--format=csv,noheader,nounits"], capture_output=True,
                                text=True, timeout=5, check=True)
        devices = []
        for line in result.stdout.splitlines():
            name, total, available = (part.strip() for part in line.split(","))
            total, available = int(total) * 1024 ** 2, int(available) * 1024 ** 2
            if not name or total <= 0 or not 0 <= available <= total:
                raise ValueError("invalid GPU measurement")
            devices.append({"name": name, "vramTotalBytes": total,
                            "vramAvailableBytes": available, "source": "nvidia-smi"})
        if not devices:
            raise ValueError("empty GPU measurement")
        return (Observation.known(devices), Observation.known(sum(d["vramTotalBytes"] for d in devices)),
                Observation.known(sum(d["vramAvailableBytes"] for d in devices)))
    except Exception as exc:
        reason = "nvidia-smi: probe failed (" + type(exc).__name__ + ")"
        return tuple(Observation.unknown(reason) for _ in range(3))


def capture_capabilities(*, model=None, cwd: Path, shell=None, environment=None,
                         resource_context_limit=None) -> RuntimeCapabilitySnapshot:
    memory = probe_memory()
    gpu, total, available = probe_gpu()
    known = lambda value, reason: Observation.known(value) if value is not None else Observation.unknown(reason)
    support = lambda value: (Observation.known(value == "AVAILABLE") if value != "UNKNOWN"
                             else Observation.unknown("provider did not report support"))
    kwargs = {}
    if model is not None:
        kwargs = dict(provider_id=Observation.known(model.provider_id),
            provider_revision=Observation.known(model.provider_revision),
            endpoint_ref=known(model.endpoint, "provider endpoint not reported"),
            provider_health=known(model.health if model.health != "UNKNOWN" else None, "provider health unverified"),
            model_id=Observation.known(model.model_id), model_revision=known(model.model_revision, "model artifact revision not reported"),
            quantization=known(model.quantization, "model quantization not reported"),
            model_context_window=known(model.model_context_window, "native context not reported"),
            provider_context_window=known(model.provider_context_window, "provider context limit not reported"),
            tool_support=support(model.tool_support), thinking_support=support(model.thinking_support),
            embedding_support=support(model.embedding_support))
    return RuntimeCapabilitySnapshot(captured_at=datetime.now(timezone.utc),
        source=memory.source + "; GPU probe; " + (model.capability_source if model else "provider unprobed")
               + ("; host_config.context_resource_limit" if resource_context_limit is not None else ""),
        os=Observation.known(platform.system()), architecture=Observation.known(platform.machine()),
        system_ram_total_bytes=memory.total, system_ram_available_bytes=memory.available,
        gpu_devices=gpu, vram_total_bytes=total, vram_available_bytes=available,
        shell=legacy_shell_descriptor(shell),
        git_capability=Observation.known(detect_git_capability(str(cwd), environment).value),
        resource_context_window=known(resource_context_limit, "resource context limit unverified; no VRAM/KV calibration"),
        concurrency_limits=Observation.unknown("operational concurrency limits unverified (OD-06)"), **kwargs)
