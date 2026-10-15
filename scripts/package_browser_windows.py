"""Build the app-local Windows browser component, never install a system runtime.

Downloads occur only when explicitly requested by the developer at packaging
time. Normal Nova/browser startup never downloads or changes user settings.
The build dependency lock is not a product capability/authority manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "native" / "browser-dependencies.json"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def run(command: list[str], *, log: Path, timeout: int = 300) -> None:
    environment = dict(os.environ)
    environment.update(DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_NOLOGO="1",
                       PIP_DISABLE_PIP_VERSION_CHECK="1")
    result = subprocess.run(command, cwd=ROOT, env=environment, timeout=timeout,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            encoding="utf-8", errors="replace", shell=False)
    log.write_text(result.stdout, encoding="utf-8")
    if result.returncode:
        raise ValueError(f"Build step failed. See {log}:\n{result.stdout[-4000:]}")


def runtime_archive(lock: dict, source: Path, *, download: bool) -> Path:
    expected = lock["webview2Runtime"]
    if not source.is_file():
        if not download:
            raise ValueError("Fixed Version archive is missing. Supply --runtime-archive or use --download.")
        source.parent.mkdir(parents=True, exist_ok=True)
        temporary = source.with_suffix(".partial")
        deadline = time.monotonic() + 600
        size = 0
        with urllib.request.urlopen(expected["url"], timeout=30) as response, temporary.open("wb") as output:
            for block in iter(lambda: response.read(1024 * 1024), b""):
                size += len(block)
                if size > expected["bytes"] or time.monotonic() >= deadline:
                    raise ValueError("Fixed Version download exceeded its declared bound.")
                output.write(block)
        temporary.replace(source)
    if source.stat().st_size != expected["bytes"] or digest(source) != expected["sha256"]:
        raise ValueError("Fixed Version archive does not match the selected build dependency.")
    return source


def package(output: Path, archive: Path, *, download: bool) -> dict:
    if os.name != "nt" or platform.machine().upper() not in ("AMD64", "X86_64"):
        raise ValueError("This package build currently requires Windows x64.")
    output = output.resolve()
    if not output.is_relative_to((ROOT / "dist").resolve()):
        raise ValueError("Package output must be a new directory inside this project's dist directory.")
    if output.exists():
        raise ValueError("Package output already exists. Choose a new --output directory.")
    dotnet = shutil.which("dotnet")
    if not dotnet:
        raise ValueError("The .NET SDK is required to build the host (not to run its package).")
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    archive = runtime_archive(lock, archive.resolve(), download=download)
    build = ROOT / "build" / "browser"
    build.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="package-", dir=build)).resolve()
    # The staging directory is owned by this build and preserved on failure.
    print(f"Staging browser component in {stage}", flush=True)
    expanded = stage / "expanded"
    expanded.mkdir()
    print("Extracting the app-local Fixed Version runtime...", flush=True)
    run([str(Path(os.environ["SystemRoot"]) / "System32" / "expand.exe"),
         str(archive), "-F:*", str(expanded)], log=build / "expand.log")
    engines = list(expanded.rglob("msedgewebview2.exe"))
    if len(engines) != 1:
        raise ValueError("Fixed Version archive must contain exactly one browser executable.")
    # Only this owned, verified extraction is relocated into the package.
    runtime = stage / "runtime"
    engines[0].parent.rename(runtime)
    expanded.rmdir()
    print("Publishing the self-contained Windows host...", flush=True)
    run([dotnet, "publish", str(ROOT / "native" / "nova-webview-host" / "nova-webview-host.csproj"),
         "-c", "Release", "-r", lock["target"], "--self-contained", "true",
         "-o", str(stage / "host"), "--nologo", "-p:NuGetAudit=false"],
        log=build / "publish.log")
    print("Including Playwright and its driver (no Chromium download)...", flush=True)
    run([sys.executable, "-m", "pip", "install", "--no-compile", "--only-binary=:all:",
         "--target", str(stage / "python"), *lock["pythonDependencies"]],
        log=build / "python-dependencies.log")
    host = stage / "host" / "nova-webview-host.exe"
    assembly = stage / "host" / "nova-webview-host.dll"
    driver = stage / "python" / "playwright" / "driver" / "node.exe"
    if not host.is_file() or not assembly.is_file() or not driver.is_file():
        raise ValueError("The package is missing its self-contained host or Playwright driver.")
    receipt = {
        "schema": "NOVA_BROWSER_PACKAGE_V1", "target": lock["target"],
        "webview2Runtime": lock["webview2Runtime"], "webview2Sdk": lock["webview2Sdk"],
        "pythonVersion": platform.python_version(),
        "pythonDependencies": lock["pythonDependencies"],
        "host": "host/nova-webview-host.exe", "runtime": "runtime", "python": "python",
        "systemRuntimeRequired": False, "systemDotnetRequired": False,
        "playwrightChromiumIncluded": False,
        "hostSha256": digest(host),
        "hostAssemblySha256": digest(assembly),
        "bytes": sum(path.stat().st_size for path in stage.rglob("*") if path.is_file()),
    }
    (stage / "package.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    shutil.copyfile(LOCK, stage / "build-dependencies.json")
    (stage / "README.txt").write_text(
        "Nova Windows browser component\n"
        "Contains Microsoft WebView2 Fixed Version Runtime and a self-contained .NET host.\n"
        "Keep the full host/, runtime/ and python/ directories together.\n"
        "The Python dependencies match the Python version recorded in package.json.\n"
        "No system WebView2/.NET install, browser profile, or user configuration is modified.\n"
        "This component is not the complete Nova CLI installer.\n", encoding="utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage.rename(output)
    return {**receipt, "output": str(output)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/browser/windows-x64")
    parser.add_argument("--runtime-archive", type=Path,
        default=ROOT / "build/browser/downloads/Microsoft.WebView2.FixedVersionRuntime.155.0.4283.45.x64.cab")
    parser.add_argument("--download", action="store_true", help="Download the declared Microsoft archive if missing.")
    args = parser.parse_args()
    try:
        print(json.dumps(package(args.output, args.runtime_archive, download=args.download), indent=2))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
