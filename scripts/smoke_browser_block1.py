#!/usr/bin/env python3
"""Explicit Windows package smoke. Missing prerequisites are FAIL, never SKIP.

Runs the infrastructure service directly; this is not a model/tool-loop test.
Only the owned HTTP fixture is served. Receipts contain no raw page, profile,
environment, control token, host transcript, or exception message.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import shutil
import socket
import struct
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/browser_block1/owned_page.html"
EVIDENCE = ROOT / "docs/active_web_reimplementation/bloque_1_host_runtime"


class SmokeFailure(Exception):
    """A bounded public failure code; arbitrary exception text is not emitted."""


def _under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left.resolve())) == os.path.normcase(str(right.resolve()))


def _public_code(value: object) -> str:
    code = str(value)
    return code if code and len(code) <= 100 and all(c.isalnum() or c in "_-" for c in code) else "UNCLASSIFIED_FAILURE"


def _receipt_output(path: Path | None) -> Path:
    if path is None:
        return Path(tempfile.mkdtemp(prefix="nova-browser-block1-result-")) / "receipt.json"
    result = path.resolve()
    if not (_under(result, Path(tempfile.gettempdir())) or _under(result, EVIDENCE)):
        raise SmokeFailure("OUTPUT_OUTSIDE_BLOCK1_OR_TEMP")
    if result.exists():
        raise SmokeFailure("OUTPUT_ALREADY_EXISTS")
    return result


class _FixtureHandler(BaseHTTPRequestHandler):
    fixture: bytes = b""

    def do_GET(self):
        if self.path == "/owned.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(self.fixture)))
            self.end_headers()
            self.wfile.write(self.fixture)
        elif self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        else:
            self.send_error(404)

    def log_message(self, *_args):
        pass


class _ProcessEntry(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
    ]


class _TcpRow(ctypes.Structure):
    _fields_ = [(name, wintypes.DWORD) for name in (
        "state", "local_address", "local_port", "remote_address", "remote_port", "pid")]


class _Tcp6Row(ctypes.Structure):
    _fields_ = [
        ("local_address", ctypes.c_ubyte * 16), ("local_scope", wintypes.DWORD),
        ("local_port", wintypes.DWORD), ("remote_address", ctypes.c_ubyte * 16),
        ("remote_scope", wintypes.DWORD), ("remote_port", wintypes.DWORD),
        ("state", wintypes.DWORD), ("pid", wintypes.DWORD),
    ]


class _WindowsProbe:
    """OS observations independent of the host's reported executable/cleanup."""

    def __init__(self):
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.tcp = ctypes.WinDLL("iphlpapi", use_last_error=True)
        self.kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        self.kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        self.kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)]
        self.kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)]
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.tcp.GetExtendedTcpTable.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), wintypes.BOOL,
            wintypes.ULONG, ctypes.c_int, wintypes.ULONG]
        self.handles: dict[int, int] = {}

    def parents(self) -> dict[int, int]:
        handle = self.kernel.CreateToolhelp32Snapshot(2, 0)
        if handle == ctypes.c_void_p(-1).value:
            raise SmokeFailure("PROCESS_SNAPSHOT_FAILED")
        result = {}
        try:
            entry = _ProcessEntry()
            entry.dwSize = ctypes.sizeof(entry)
            success = self.kernel.Process32FirstW(handle, ctypes.byref(entry))
            while success:
                result[int(entry.th32ProcessID)] = int(entry.th32ParentProcessID)
                success = self.kernel.Process32NextW(handle, ctypes.byref(entry))
        finally:
            self.kernel.CloseHandle(handle)
        return result

    def retain(self, pid: int) -> bool:
        if pid in self.handles:
            return True
        # Keep handles until cleanup to avoid confusing a recycled PID with the
        # original process. TERMINATE is used only for emergency owned cleanup.
        handle = self.kernel.OpenProcess(0x1000 | 0x100000 | 0x0001, False, pid)
        if handle:
            self.handles[pid] = handle
            return True
        return False

    def image(self, pid: int) -> Path:
        if not self.retain(pid):
            raise SmokeFailure("PROCESS_INSPECTION_FAILED")
        length = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(length.value)
        if not self.kernel.QueryFullProcessImageNameW(self.handles[pid], 0, buffer, ctypes.byref(length)):
            raise SmokeFailure("PROCESS_IMAGE_QUERY_FAILED")
        return Path(buffer.value)

    def exited(self) -> bool:
        return all(self.kernel.WaitForSingleObject(handle, 0) == 0 for handle in self.handles.values())

    def close(self):
        for handle in self.handles.values():
            self.kernel.CloseHandle(handle)
        self.handles.clear()

    def emergency_terminate(self):
        for handle in reversed(tuple(self.handles.values())):
            if self.kernel.WaitForSingleObject(handle, 0) == 258:
                self.kernel.TerminateProcess(handle, 1)

    def listeners(self, port: int) -> list[tuple[str, int]]:
        rows = []
        for family, row_type in ((socket.AF_INET, _TcpRow), (socket.AF_INET6, _Tcp6Row)):
            size = wintypes.DWORD(0)
            status = self.tcp.GetExtendedTcpTable(None, ctypes.byref(size), False, family, 3, 0)
            if status not in (0, 122):
                raise SmokeFailure("TCP_LISTENER_QUERY_FAILED")
            buffer = ctypes.create_string_buffer(size.value)
            if self.tcp.GetExtendedTcpTable(buffer, ctypes.byref(size), False, family, 3, 0):
                raise SmokeFailure("TCP_LISTENER_QUERY_FAILED")
            count = wintypes.DWORD.from_buffer(buffer).value
            for index in range(count):
                row = row_type.from_buffer(buffer, ctypes.sizeof(wintypes.DWORD) + index * ctypes.sizeof(row_type))
                if socket.ntohs(int(row.local_port) & 0xffff) != port:
                    continue
                address = (socket.inet_ntoa(struct.pack("<I", row.local_address))
                           if family == socket.AF_INET else socket.inet_ntop(family, bytes(row.local_address)))
                rows.append((address, int(row.pid)))
        return rows


def _descendants(parents: dict[int, int], root: int) -> set[int]:
    result = {root}
    while True:
        children = {pid for pid, parent in parents.items() if parent in result}
        expanded = result | children
        if expanded == result:
            return result
        result = expanded


def _wait_for(predicate, timeout: float = 10) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return bool(predicate())


def run_smoke(package_root: Path, output: Path | None = None, *, timeout: float = 30) -> tuple[int, Path]:
    """Run one actual native smoke and write a new sanitized receipt after cleanup."""
    output = _receipt_output(output)
    receipt = {
        "schema": "nova-browser-block1-native-smoke-1", "status": "FAIL",
        "scope": "Windows packaged host / Fixed Version / Playwright infrastructure",
        "started_at": datetime.now(timezone.utc).isoformat(), "checks": [],
        "claims": {"model_tools_tested": False, "public_sites_tested": False,
                   "network_isolation_claimed": False, "historical_evidence_reused": False},
    }
    work = Path(tempfile.mkdtemp(prefix="nova-browser-block1-work-"))
    session = server = thread = probe = None
    driver_image = None
    process_baseline: set[int] = set()
    cdp_port = server_port = None
    error = None
    old_node = os.environ.pop("PLAYWRIGHT_NODEJS_PATH", None)

    def check(name, passed):
        receipt["checks"].append({"name": name, "passed": bool(passed)})
        if not passed:
            raise SmokeFailure(name.upper())

    try:
        check("windows_platform", sys.platform == "win32")
        package_root = package_root.resolve()
        host = package_root / "host/nova-webview-host.exe"
        host_assembly = package_root / "host/nova-webview-host.dll"
        runtime = package_root / "runtime/msedgewebview2.exe"
        python = package_root / "python"
        check("package_components_present", host.is_file() and host_assembly.is_file() and runtime.is_file() and python.is_dir())
        manifest_path = package_root / "package.json"
        check("package_receipt_present", manifest_path.is_file())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        check("package_receipt_target", manifest.get("schema") == "NOVA_BROWSER_PACKAGE_V1" and manifest.get("target") == "win-x64")
        check("owned_fixture_present", FIXTURE.is_file())
        # Direct script invocation puts scripts/ on sys.path. Select this source
        # tree and the explicitly supplied package's vendored Python libraries.
        sys.path.insert(0, str(ROOT))
        sys.path.insert(0, str(python))
        playwright = importlib.import_module("playwright")
        check("playwright_import_from_package", _under(Path(playwright.__file__), python))
        driver = importlib.import_module("playwright._impl._driver")
        driver_paths = driver.compute_driver_executable()
        check("playwright_driver_from_package", all(_under(Path(path), python) and Path(path).is_file() for path in driver_paths))
        receipt["versions"] = {"playwright": importlib.metadata.version("playwright")}
        check("playwright_version_matches_package", f"playwright=={receipt['versions']['playwright']}" in manifest.get("pythonDependencies", ()))
        driver_image = Path(driver_paths[0])
        module = importlib.import_module("local_cli.infrastructure.browser.windows_webview2")
        check("service_import_from_target_tree", _under(Path(module.__file__), ROOT / "local_cli"))
        child_env = dict(os.environ)
        child_env["PATH"] = str(Path(child_env.get("SystemRoot", r"C:\Windows")) / "System32")
        for variable in ("DOTNET_ROOT", "DOTNET_ROOT_X64", "DOTNET_ROOT_X86", "DOTNET_ROOT_ARM64", "DOTNET_ROOT(x86)"):
            child_env[variable] = str(work / "dotnet-not-installed")
        child_env["DOTNET_MULTILEVEL_LOOKUP"] = "0"
        check("external_dotnet_unavailable_to_host", shutil.which("dotnet", path=child_env["PATH"]) is None and not (work / "dotnet-not-installed").exists())
        handler = type("OwnedFixtureHandler", (_FixtureHandler,), {"fixture": FIXTURE.read_bytes()})
        server = HTTPServer(("127.0.0.1", 0), handler)
        server_port = int(server.server_address[1])
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        probe = _WindowsProbe()
        process_baseline = _descendants(probe.parents(), os.getpid())
        session = module.WebView2BrowserSession(package_root, profile_root=work / "profiles", timeout=timeout, host_environment=child_env)
        session.start()
        ready = session.ready
        check("ready_metadata_present", ready is not None)
        check("runtime_directory_from_package", _same_path(Path(ready.runtime_directory), runtime.parent))
        check("reported_browser_from_package", _same_path(Path(ready.browser_executable), runtime))
        check("profile_in_owned_temporary_directory", _under(Path(ready.profile_directory), work / "profiles"))
        check("profile_exists_while_running", Path(ready.profile_directory).is_dir())
        check("runtime_version_matches_package", ready.runtime_version == manifest.get("webview2Runtime", {}).get("version"))
        receipt["versions"]["webview2"] = ready.runtime_version
        receipt["components"] = {
            "host": {"path": "host/nova-webview-host.exe", "sha256": hashlib.sha256(host.read_bytes()).hexdigest()},
            "host_assembly": {"path": "host/nova-webview-host.dll", "sha256": hashlib.sha256(host_assembly.read_bytes()).hexdigest()},
            "runtime": {"path": "runtime/msedgewebview2.exe", "sha256": hashlib.sha256(runtime.read_bytes()).hexdigest()},
            "python": "python/",
        }
        check("host_digest_matches_package", receipt["components"]["host"]["sha256"] == manifest.get("hostSha256"))
        check("host_assembly_digest_matches_package", receipt["components"]["host_assembly"]["sha256"] == manifest.get("hostAssemblySha256"))
        parents = probe.parents()
        check("host_is_direct_owned_process", parents.get(ready.host_pid) == os.getpid())
        owned = _descendants(parents, ready.host_pid)
        check("browser_is_owned_descendant", ready.browser_pid in owned)
        check("actual_host_image_from_package", _same_path(probe.image(ready.host_pid), host))
        check("actual_browser_image_from_package", _same_path(probe.image(ready.browser_pid), runtime))
        driver_pids = []
        for pid in _descendants(parents, os.getpid()) - process_baseline - owned:
            try:
                if _same_path(probe.image(pid), driver_image):
                    driver_pids.append(pid)
            except SmokeFailure:
                pass  # A short-lived child may exit before image inspection.
        check("actual_playwright_driver_from_package", len(driver_pids) == 1)
        endpoint = urlsplit(ready.cdp_endpoint)
        check("cdp_endpoint_loopback", endpoint.scheme == "http" and endpoint.hostname == "127.0.0.1" and endpoint.port is not None)
        cdp_port = endpoint.port
        listeners = probe.listeners(cdp_port)
        check("cdp_listener_owned_and_loopback", bool(listeners) and all(address in ("127.0.0.1", "::1") and pid in owned for address, pid in listeners))
        session.navigate(f"http://127.0.0.1:{server_port}/owned.html")
        session.page.get_by_test_id("rendered").wait_for(state="visible", timeout=timeout * 1000)
        session.page.wait_for_function("document.querySelector('#rendered').textContent === 'Rendered by JavaScript: ready'", timeout=timeout * 1000)
        reading = session.read()
        check("rendered_javascript_read", "Rendered by JavaScript: ready" in reading.text and "JavaScript has not run." not in reading.text)
        session.page.get_by_role("button", name="Update owned page").click(timeout=timeout * 1000)
        after = session.read()
        check("owned_click_and_read", "Clicks: 1" in after.text and "Clicks: 0" not in after.text)
        # Retain all live descendants after operations, including renderer and
        # utility processes created during navigation, before asking to close.
        owned = _descendants(probe.parents(), ready.host_pid)
        for pid in owned:
            probe.retain(pid)
        receipt["owned_process_count_observed"] = len(probe.handles)
    except Exception as exc:
        error = _public_code(exc.args[0] if isinstance(exc, SmokeFailure) and exc.args else getattr(exc, "code", type(exc).__name__))
    finally:
        # Cleanup runs before writing any receipt, even after partial startup.
        if probe is not None and session is not None:
            try:
                parents = probe.parents()
                if session.ready is not None:
                    for pid in _descendants(parents, session.ready.host_pid):
                        probe.retain(pid)
                for pid in _descendants(parents, os.getpid()) - process_baseline:
                    try:
                        if driver_image is not None and _same_path(probe.image(pid), driver_image):
                            probe.retain(pid)
                    except SmokeFailure:
                        pass
            except SmokeFailure:
                error = error or "OWNED_PROCESS_CAPTURE_FAILED"
        if session is not None:
            try:
                closed = session.close()
                receipt["cleanup"] = {
                    "host_exited": bool(closed.host_exited), "job_empty": bool(closed.job_empty),
                    "profile_removed": bool(closed.profile_removed), "graceful": bool(closed.graceful),
                    "service_errors": [_public_code(item) for item in closed.errors],
                }
                if not (closed.host_exited and closed.job_empty and closed.profile_removed and not closed.errors):
                    error = error or "SERVICE_CLEANUP_FAILED"
            except Exception as exc:
                receipt["cleanup"] = {"service_close_exception": _public_code(type(exc).__name__)}
                error = error or "SERVICE_CLOSE_FAILED"
        if probe is not None:
            try:
                processes_exited = _wait_for(probe.exited)
                listener_closed = cdp_port is None or _wait_for(lambda: not probe.listeners(cdp_port))
                receipt.setdefault("cleanup", {}).update({"os_process_handles_exited": processes_exited, "cdp_listener_closed": listener_closed})
                if not processes_exited:
                    error = error or "OWNED_PROCESS_LEFTOVER"
                    probe.emergency_terminate()
                    receipt["cleanup"]["emergency_cleanup_exited"] = _wait_for(probe.exited)
                if not listener_closed:
                    error = error or "CDP_LISTENER_LEFTOVER"
            except Exception as exc:
                receipt.setdefault("cleanup", {})["os_check_exception"] = _public_code(type(exc).__name__)
                error = error or "OS_CLEANUP_CHECK_FAILED"
            finally:
                probe.close()
        if server is not None:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            listener_closed = True
            try:
                with socket.create_connection(("127.0.0.1", server_port), timeout=0.2):
                    listener_closed = False
            except OSError:
                pass
            receipt.setdefault("cleanup", {}).update({"owned_http_thread_stopped": not thread.is_alive(), "owned_http_listener_closed": listener_closed})
            if thread.is_alive() or not listener_closed:
                error = error or "OWNED_HTTP_CLEANUP_FAILED"
        try:
            shutil.rmtree(work)
            receipt.setdefault("cleanup", {})["owned_temporary_directory_removed"] = not work.exists()
        except OSError:
            receipt.setdefault("cleanup", {})["owned_temporary_directory_removed"] = False
            error = error or "OWNED_TEMPORARY_DIRECTORY_LEFTOVER"
        if old_node is not None:
            os.environ["PLAYWRIGHT_NODEJS_PATH"] = old_node
    receipt["completed_at"] = datetime.now(timezone.utc).isoformat()
    receipt["status"] = "FAIL" if error else "PASS"
    if error:
        receipt["failure_code"] = error
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, ensure_ascii=True)
        stream.write("\n")
    return (1 if error else 0), output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, default=ROOT / "dist/browser/windows-x64")
    parser.add_argument("--output", type=Path, help="New JSON file under system temp or this Block 1 documentation directory")
    parser.add_argument("--timeout", type=float, default=30, help="Startup/operation timeout in seconds")
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be positive and finite")
    try:
        code, output = run_smoke(args.package_dir, args.output, timeout=args.timeout)
    except SmokeFailure as exc:
        print(json.dumps({"status": "FAIL", "failure_code": _public_code(exc.args[0])}))
        return 1
    print(json.dumps({"status": "PASS" if code == 0 else "FAIL", "receipt": str(output)}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
