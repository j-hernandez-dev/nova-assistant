"""Packaged WebView2 host connected to Playwright over local CDP.

This adapter is an internal Block 1 seam. It does not register tools, choose a
browser, download a runtime, or depend on historical Active Web contracts.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit
import uuid

from local_cli.application.browser import (
    BrowserCloseReceipt, BrowserNavigation, BrowserRead, BrowserUnavailable,
)
from .process_job import ProcessJob
from .page_io import PlaywrightPageIO


_FRAME_LIMIT = 16384


@dataclass(frozen=True)
class WebView2Ready:
    host_pid: int
    browser_pid: int
    runtime_version: str
    runtime_directory: Path
    browser_executable: Path
    cdp_endpoint: str
    profile_directory: Path


def _load_playwright(package_root: Path):
    # Packaging supplies Playwright and its driver. Importing this module on an
    # unsupported machine must not import the optional dependency or Windows DLLs.
    dependency_root = (package_root / "python").resolve()
    if not (dependency_root / "playwright" / "sync_api" / "__init__.py").is_file():
        raise BrowserUnavailable("PLAYWRIGHT_NOT_AVAILABLE", "The packaged Playwright dependency is missing.")

    def belongs_to_package(module) -> bool:
        source = getattr(module, "__file__", None)
        if not source:
            return False
        try:
            Path(source).resolve().relative_to(dependency_root)
            return True
        except ValueError:
            return False

    families = ("playwright", "greenlet", "pyee")
    for name, module in tuple(sys.modules.items()):
        if any(name == family or name.startswith(family + ".") for family in families):
            if module is not None and not belongs_to_package(module):
                raise BrowserUnavailable("PLAYWRIGHT_PACKAGE_CONFLICT", "A browser dependency was already loaded from another package.")
    # This is the explicit, shipped dependency directory. Keep it available for
    # the driver's later imports; never search user installations or downloads.
    dependency_path = str(dependency_root)
    if dependency_path not in sys.path:
        sys.path.insert(0, dependency_path)
    try:
        module = importlib.import_module("playwright.sync_api")
        if not belongs_to_package(module):
            raise BrowserUnavailable("PLAYWRIGHT_PACKAGE_CONFLICT", "Playwright was not loaded from the browser package.")
        for name, dependency in tuple(sys.modules.items()):
            if any(name == family or name.startswith(family + ".") for family in families):
                if dependency is not None and not belongs_to_package(dependency):
                    raise BrowserUnavailable("PLAYWRIGHT_PACKAGE_CONFLICT", "A browser dependency is missing from the shipped package.")
        return module.sync_playwright
    except (ImportError, OSError) as exc:
        raise BrowserUnavailable("PLAYWRIGHT_NOT_AVAILABLE", "The packaged Playwright dependency is missing.") from exc


def _validate_endpoint(value: object) -> str:
    if not isinstance(value, str) or len(value) > 128:
        raise ValueError("Invalid CDP endpoint")
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment
            or parsed.port is None or not 1 <= parsed.port <= 65535
            or parsed.netloc != f"127.0.0.1:{parsed.port}"):
        raise ValueError("Invalid CDP endpoint")
    return value.rstrip("/")


class _ControlReader:
    """One bounded reader for the host's private inherited stdout pipe."""

    def __init__(self, stream):
        self._stream = stream
        self._frames = queue.Queue(maxsize=4)
        self._failed = threading.Event()
        self._thread = threading.Thread(target=self._run, name="nova-browser-control", daemon=True)
        self._thread.start()

    def _run(self):
        try:
            while True:
                frame = self._stream.readline(_FRAME_LIMIT + 1)
                if not frame:
                    self._frames.put_nowait(None)
                    return
                if len(frame) > _FRAME_LIMIT or not frame.endswith(b"\n"):
                    raise ValueError("Oversized or incomplete host frame")
                self._frames.put_nowait(frame)
        except (OSError, ValueError, queue.Full):
            self._failed.set()

    def receive(self, timeout: float) -> dict:
        end = time.monotonic() + max(0, timeout)
        while True:
            if self._failed.is_set():
                raise BrowserUnavailable("HOST_PROTOCOL_ERROR", "The browser host returned an invalid control message.")
            try:
                frame = self._frames.get(timeout=min(0.05, max(0, end - time.monotonic())))
                break
            except queue.Empty:
                if time.monotonic() >= end:
                    raise BrowserUnavailable("HOST_START_TIMEOUT", "The browser host did not respond before its deadline.")
        if frame is None:
            raise BrowserUnavailable("HOST_EXITED", "The browser host exited before completing its response.")
        try:
            result = json.loads(frame.decode("utf-8"))
            if not isinstance(result, dict):
                raise ValueError("Expected object")
            return result
        except (ValueError, UnicodeError) as exc:
            raise BrowserUnavailable("HOST_PROTOCOL_ERROR", "The browser host returned an invalid control message.") from exc

    def join(self):
        self._thread.join(timeout=0.5)


class WebView2BrowserSession(PlaywrightPageIO):
    """Own one native host, its WebView2 children, profile and CDP connection.

    ``package_root`` contains ``host/nova-webview-host.exe`` and
    ``runtime/msedgewebview2.exe``. ``profile_root`` is a parent for a new private
    profile, never an existing user browser profile. Instances are single use.
    Raw ``page`` and ``ready`` are exposed only for trusted infrastructure smoke
    checks, and are not a public model API.
    """

    def __init__(self, package_root: Path | str, *, profile_root: Path | str | None = None,
                 timeout: float = 30, host_environment: dict[str, str] | None = None):
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be a positive finite number")
        self.package_root = Path(package_root).resolve()
        self.runtime_directory = self.package_root / "runtime"
        self.host_executable = self.package_root / "host" / "nova-webview-host.exe"
        self._profile_parent = Path(profile_root or Path(tempfile.gettempdir()) / "nova-browser-profiles").resolve()
        self.profile_directory: Path | None = None
        self.timeout = float(timeout)
        self._host_environment = host_environment
        self._token = uuid.uuid4().hex
        self._process = self._job = self._reader = None
        self._playwright = self._browser = None
        self.page = None
        self.ready: WebView2Ready | None = None
        self.close_receipt: BrowserCloseReceipt | None = None
        self._started = False

    def _send(self, command: str):
        frame = json.dumps({"command": command, "token": self._token}, separators=(",", ":")) + "\n"
        self._process.stdin.write(frame.encode("utf-8"))
        self._process.stdin.flush()

    def private_control(self, command, **fields):
        payload = {'command': command, 'token': self._token, **fields}
        frame = (json.dumps(payload, separators=(',', ':')) + '\n').encode('utf-8')
        if len(frame) > _FRAME_LIMIT: raise BrowserUnavailable('HOST_PROTOCOL_ERROR', 'The private control request exceeded its limit.')
        self._process.stdin.write(frame); self._process.stdin.flush()
        result = self._reader.receive(3)
        if result.get('event') != 'control' or result.get('token') != self._token or result.get('command') != command:
            raise BrowserUnavailable('HOST_PROTOCOL_ERROR', 'The browser host did not confirm its control state.')
        return result

    def set_visible(self, visible):
        result = self.private_control('show' if visible else 'hide')
        if result.get('visible') is not visible:
            raise BrowserUnavailable('BROWSER_WINDOW_UNAVAILABLE', 'The browser window could not change visibility.')

    def _accept_ready(self, frame: dict) -> WebView2Ready:
        try:
            if (frame.get("event") != "ready" or frame.get("token") != self._token
                    or type(frame.get("hostPid")) is not int or frame["hostPid"] != self._process.pid
                    or type(frame.get("browserPid")) is not int or frame["browserPid"] <= 0
                    or not isinstance(frame.get("runtimeVersion"), str) or not 1 <= len(frame["runtimeVersion"]) <= 128):
                raise ValueError("Invalid ready identity")
            runtime = Path(frame["runtimeDirectory"]).resolve()
            executable = Path(frame["browserExecutable"]).resolve()
            profile = Path(frame["profileDirectory"]).resolve()
            endpoint = _validate_endpoint(frame.get("cdpEndpoint"))
            if (runtime != self.runtime_directory.resolve()
                    or executable != (self.runtime_directory / "msedgewebview2.exe").resolve()
                    or profile != self.profile_directory or not self._job.contains(frame["browserPid"])):
                raise ValueError("Browser does not belong to this packaged session")
            return WebView2Ready(frame["hostPid"], frame["browserPid"], frame["runtimeVersion"],
                                 runtime, executable, endpoint, profile)
        except (KeyError, TypeError, ValueError, OSError) as exc:
            raise BrowserUnavailable("HOST_PROTOCOL_ERROR", "The browser host did not confirm the owned packaged browser.") from exc

    def start(self) -> WebView2BrowserSession:
        if self._started or self.close_receipt is not None:
            raise BrowserUnavailable("SESSION_ALREADY_USED", "Create a new browser session before starting again.")
        self._started = True
        try:
            if os.name != "nt":
                raise BrowserUnavailable("UNSUPPORTED_PLATFORM", "The packaged browser currently supports Windows only.")
            if not self.host_executable.is_file():
                raise BrowserUnavailable("HOST_NOT_FOUND", "The packaged browser host is missing.")
            if not (self.runtime_directory / "msedgewebview2.exe").is_file():
                raise BrowserUnavailable("RUNTIME_NOT_FOUND", "The packaged WebView2 Fixed Version runtime is missing.")
            playwright_factory = _load_playwright(self.package_root)
            self._profile_parent.mkdir(parents=True, exist_ok=True)
            self.profile_directory = self._profile_parent / ("nova-webview-" + uuid.uuid4().hex)
            if self.profile_directory.exists():
                raise BrowserUnavailable("PROFILE_NOT_OWNED", "Could not allocate a new browser profile.")
            environment = dict(os.environ if self._host_environment is None else self._host_environment)
            for key in list(environment):
                if key.upper().startswith("WEBVIEW2_"):
                    del environment[key]
            deadline = time.monotonic() + self.timeout
            self._process = subprocess.Popen(
                [str(self.host_executable), "--runtime-directory", str(self.runtime_directory),
                 "--user-data-directory", str(self.profile_directory), "--owner-pid", str(os.getpid()),
                 "--token", self._token],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                shell=False, cwd=str(self.host_executable.parent), env=environment,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self._job = ProcessJob(self._process)
            self._reader = _ControlReader(self._process.stdout)
            self._send("start")  # The host has not created browser children until this point.
            self.ready = self._accept_ready(self._reader.receive(max(0, deadline - time.monotonic())))
            self._playwright = playwright_factory().start()
            self._browser = self._playwright.chromium.connect_over_cdp(
                self.ready.cdp_endpoint, timeout=max(1, int((deadline - time.monotonic()) * 1000)))
            if not self._browser.contexts or not self._browser.contexts[0].pages:
                raise BrowserUnavailable("CDP_PAGE_NOT_FOUND", "The packaged browser did not expose its initial page.")
            self.page = self._browser.contexts[0].pages[0]
            self._context = self._browser.contexts[0]
            self.page.set_default_timeout(self.timeout * 1000)
            self.page.set_default_navigation_timeout(self.timeout * 1000)
            return self
        except BrowserUnavailable:
            self.close()
            raise
        except Exception as exc:
            code = "CDP_CONNECT_FAILED" if self.ready is not None else "HOST_START_FAILED"
            self.close()
            raise BrowserUnavailable(code, "The packaged browser could not start or connect.") from exc
        except BaseException:
            self.close()
            raise

    def _active_page(self):
        if self.page is None or self.close_receipt is not None or self._process.poll() is not None:
            raise BrowserUnavailable("BROWSER_CLOSED", "The browser session is closed.")
        return self.page

    def _remove_profile(self) -> bool:
        profile = self.profile_directory
        if profile is None: return True
        from .profile_cleanup import remove_owned_profile
        return remove_owned_profile(profile, self._profile_parent, 'nova-webview-')

    def close(self) -> BrowserCloseReceipt:
        if self.close_receipt is not None:
            return self.close_receipt
        errors = []
        closed = forced = False
        process = self._process
        if self._playwright is not None:
            try:
                # Stopping the driver disconnects CDP; the owned native host
                # controls WebView2 shutdown and reports whether it exited.
                self._playwright.stop()
            except Exception:
                errors.append("PLAYWRIGHT_DISCONNECT_FAILED")
            self._playwright = self._browser = self.page = None
        if process is not None and process.poll() is None:
            try:
                self._send("shutdown")
                if self._reader is not None:
                    frame = self._reader.receive(min(3, self.timeout))
                    closed = (frame.get("event") == "closed" and frame.get("token") == self._token
                              and type(frame.get("hostPid")) is int and frame["hostPid"] == process.pid
                              and frame.get("browserExited") is True)
                process.wait(timeout=min(2, self.timeout))
            except Exception:
                pass  # The owned process job is the bounded cleanup fallback.
        host_exited = process is None or process.poll() is not None
        job_empty = self._job is None and host_exited
        if self._job is not None:
            try:
                job_empty = self._job.wait_empty(0.5)
                if not job_empty:
                    forced = True
                    self._job.terminate()
                    job_empty = self._job.wait_empty(2)
            except OSError:
                errors.append("JOB_CLEANUP_UNCONFIRMED")
            finally:
                try:
                    self._job.close()
                except OSError:
                    errors.append("JOB_CLOSE_FAILED")
        if process is not None:
            if process.poll() is None:
                forced = True
                try:
                    process.kill()
                    process.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    errors.append("HOST_CLEANUP_UNCONFIRMED")
            host_exited = process.poll() is not None
            # No start frame was sent if job assignment failed. No browser
            # descendants can exist in that case.
            if self._job is None:
                job_empty = host_exited
            for stream in (process.stdin, process.stdout):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        errors.append("CONTROL_PIPE_CLOSE_FAILED")
        if self._reader is not None:
            self._reader.join()
        profile_removed = False
        if host_exited and job_empty:
            try:
                profile_removed = self._remove_profile()
            except OSError:
                pass
        if not host_exited:
            errors.append("HOST_STILL_RUNNING")
        if not job_empty:
            errors.append("JOB_NOT_EMPTY")
        if not profile_removed:
            errors.append("PROFILE_CLEANUP_UNCONFIRMED")
        self.close_receipt = BrowserCloseReceipt(host_exited, job_empty, profile_removed,
                                                 closed and host_exited and job_empty and not forced,
                                                 forced, tuple(errors))
        return self.close_receipt

    def __enter__(self) -> WebView2BrowserSession:
        return self.start()

    def __exit__(self, *_exc) -> None:
        self.close()
