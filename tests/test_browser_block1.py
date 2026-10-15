"""Offline tests for the small packaged WebView2 lifecycle boundary."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from local_cli.application.browser import BrowserService, BrowserUnavailable
from local_cli.infrastructure.browser import windows_webview2 as browser


class FakePage:
    url = "about:blank"
    text = "A short owned page"

    def __init__(self):
        self.visits = []

    def set_default_timeout(self, _timeout):
        pass

    def set_default_navigation_timeout(self, _timeout):
        pass

    def goto(self, url, **_options):
        self.visits.append(url)
        self.url = url

    def title(self):
        return "Owned title"

    def locator(self, selector):
        assert selector == "body"
        return self

    def evaluate(self, function, limit, **_options):
        assert "text.slice(0, limit)" in function
        return {"text": self.text[:limit], "truncated": len(self.text) > limit}


class FakeInput(io.BytesIO):
    def __init__(self, process):
        super().__init__()
        self.process = process
        self.offset = 0

    def flush(self):
        raw = self.getvalue()[self.offset:]
        if raw:
            self.offset += len(raw)
            frame = json.loads(raw)
            self.process.commands.append(frame)
            if frame["command"] == "start":
                assert self.process.job_assigned
                self.process.profile.mkdir()


class FakeProcess:
    pid = 4123

    def __init__(self, args, options):
        self.args, self.options = args, options
        self.profile = Path(args[args.index("--user-data-directory") + 1])
        self.token = args[args.index("--token") + 1]
        self.runtime = Path(args[args.index("--runtime-directory") + 1])
        self.stdin = FakeInput(self)
        self.stdout = io.BytesIO()
        self.commands = []
        self.code = None
        self.job_assigned = False
        self.killed = False

    def poll(self):
        return self.code

    def wait(self, **_options):
        self.code = 0
        return self.code

    def kill(self):
        self.killed = True
        self.code = 1


@pytest.fixture
def harness(tmp_path, monkeypatch):
    package = tmp_path / "package"
    (package / "host").mkdir(parents=True)
    (package / "runtime").mkdir()
    (package / "host" / "nova-webview-host.exe").touch()
    (package / "runtime" / "msedgewebview2.exe").touch()
    state = SimpleNamespace(package=package, process=None, page=FakePage(), frame_changes={},
                            connect_error=False, protocol_error=False, stuck_job=False,
                            playwright_stopped=False, job_closed=False, connect_calls=[])
    monkeypatch.setattr(browser, "os", SimpleNamespace(name="nt", environ=os.environ, getpid=os.getpid))

    def popen(args, **options):
        state.process = FakeProcess(args, options)
        return state.process

    class Job:
        def __init__(self, process):
            process.job_assigned = True

        def contains(self, pid):
            return pid == 5123

        def wait_empty(self, timeout):
            return not state.stuck_job

        def terminate(self):
            state.process.kill()
            state.stuck_job = False

        def close(self):
            state.job_closed = True

    class Reader:
        def __init__(self, _stream):
            pass

        def receive(self, _timeout):
            process = state.process
            if state.protocol_error:
                raise BrowserUnavailable("HOST_PROTOCOL_ERROR", "Invalid host control message.")
            if process.commands[-1]["command"] == "shutdown":
                return {"event": "closed", "token": process.token, "hostPid": process.pid,
                        "browserExited": True}
            frame = {"event": "ready", "token": process.token, "hostPid": process.pid,
                     "browserPid": 5123, "runtimeVersion": "155.0.4283.45",
                     "runtimeDirectory": str(process.runtime),
                     "browserExecutable": str(process.runtime / "msedgewebview2.exe"),
                     "profileDirectory": str(process.profile), "cdpEndpoint": "http://127.0.0.1:19223"}
            frame.update(state.frame_changes)
            return frame

        def join(self):
            pass

    class Playwright:
        chromium = None

        def __init__(self):
            self.chromium = self

        def start(self):
            return self

        def connect_over_cdp(self, endpoint, **_options):
            state.connect_calls.append(endpoint)
            if state.connect_error:
                raise state.connect_error
            return SimpleNamespace(contexts=[SimpleNamespace(pages=[state.page])])

        def stop(self):
            state.playwright_stopped = True

    monkeypatch.setattr(browser.subprocess, "Popen", popen)
    monkeypatch.setattr(browser, "ProcessJob", Job)
    monkeypatch.setattr(browser, "_ControlReader", Reader)
    monkeypatch.setattr(browser, "_load_playwright", lambda _package: Playwright)
    state.session = lambda: browser.WebView2BrowserSession(package, profile_root=tmp_path / "profiles")
    return state


def test_owned_session_connects_navigates_reads_and_cleans_up(harness):
    session = harness.session()
    service = BrowserService(session)
    with service:
        assert session.ready.host_pid == harness.process.pid
        assert session.ready.browser_executable == harness.package / "runtime" / "msedgewebview2.exe"
        assert session.profile_directory.exists()
        navigation = service.navigate("http://127.0.0.1:8080/owned?q=hello#section")
        assert navigation.url.endswith("/owned?q=hello#section")
        result = service.read(max_chars=7)
        assert result.text == "A short" and result.truncated
        assert harness.process.commands[0]["command"] == "start"
        assert harness.process.options["shell"] is False
    receipt = service.close()
    assert receipt.host_exited and receipt.job_empty and receipt.profile_removed and receipt.graceful
    assert receipt.errors == () and not receipt.forced
    assert harness.playwright_stopped and harness.job_closed
    assert not session.profile_directory.exists()
    assert service.close() is receipt


@pytest.mark.parametrize("missing,code", [("host/nova-webview-host.exe", "HOST_NOT_FOUND"),
                                        ("runtime/msedgewebview2.exe", "RUNTIME_NOT_FOUND")])
def test_missing_package_component_fails_without_launch(harness, missing, code):
    (harness.package / missing).unlink()
    session = harness.session()
    with pytest.raises(BrowserUnavailable) as caught:
        session.start()
    assert caught.value.code == code
    assert harness.process is None
    assert session.close_receipt.profile_removed


def test_missing_playwright_fails_before_process_or_profile(harness, monkeypatch):
    def unavailable(_package):
        raise BrowserUnavailable("PLAYWRIGHT_NOT_AVAILABLE", "Missing packaged dependency.")
    monkeypatch.setattr(browser, "_load_playwright", unavailable)
    with pytest.raises(BrowserUnavailable, match="Missing packaged dependency"):
        harness.session().start()
    assert harness.process is None


def test_other_platform_is_unavailable_before_optional_dependency(harness, monkeypatch):
    monkeypatch.setattr(browser, "os", SimpleNamespace(name="posix"))
    with pytest.raises(BrowserUnavailable) as caught:
        harness.session().start()
    assert caught.value.code == "UNSUPPORTED_PLATFORM"
    assert harness.process is None


@pytest.mark.parametrize("change", [{"token": "foreign"}, {"hostPid": 999}, {"browserPid": 999},
                                    {"runtimeDirectory": "unowned-runtime"},
                                    {"browserExecutable": "unowned-browser.exe"},
                                    {"profileDirectory": "unowned-profile"}])
def test_ready_identity_mismatch_never_connects_and_cleans_profile(harness, change):
    harness.frame_changes = change
    session = harness.session()
    with pytest.raises(BrowserUnavailable) as caught:
        session.start()
    assert caught.value.code == "HOST_PROTOCOL_ERROR"
    assert harness.connect_calls == []
    assert session.close_receipt.profile_removed and harness.job_closed


@pytest.mark.parametrize("endpoint", ["http://localhost:9000", "http://127.0.0.1.evil:9000",
                                      "http://127.0.0.1:9000/path", "http://user@127.0.0.1:9000",
                                      "https://127.0.0.1:9000", "http://127.0.0.1:0",
                                      "http://127.0.0.1:9000?token=x", "http://[::1]:9000"])
def test_cdp_endpoint_must_be_exact_ipv4_loopback(harness, endpoint):
    harness.frame_changes = {"cdpEndpoint": endpoint}
    with pytest.raises(BrowserUnavailable) as caught:
        harness.session().start()
    assert caught.value.code == "HOST_PROTOCOL_ERROR"
    assert harness.connect_calls == []


@pytest.mark.parametrize("connection_error", [
    RuntimeError("Sensitive diagnostic must not become public error"), KeyboardInterrupt(),
], ids=["operational-failure", "keyboard-interrupt"])
def test_connection_failure_is_bounded_and_releases_owned_resources(harness, connection_error):
    harness.connect_error = connection_error
    session = harness.session()
    expected = KeyboardInterrupt if isinstance(connection_error, KeyboardInterrupt) else BrowserUnavailable
    with pytest.raises(expected) as caught:
        session.start()
    if expected is BrowserUnavailable:
        assert caught.value.code == "CDP_CONNECT_FAILED"
        assert "Sensitive" not in caught.value.message
    else:
        assert caught.value is connection_error
    assert len(harness.connect_calls) == 1
    assert harness.playwright_stopped
    assert session.close_receipt.profile_removed


def test_job_assignment_failure_never_sends_start(harness, monkeypatch):
    def fail_job(_process):
        raise OSError("No job assignment")
    monkeypatch.setattr(browser, "ProcessJob", fail_job)
    session = harness.session()
    with pytest.raises(BrowserUnavailable) as caught:
        session.start()
    assert caught.value.code == "HOST_START_FAILED"
    assert all(frame["command"] != "start" for frame in harness.process.commands)
    assert session.close_receipt.host_exited and session.close_receipt.profile_removed


def test_stuck_descendant_is_terminated_and_reported_as_forced(harness):
    session = harness.session().start()
    harness.stuck_job = True
    receipt = session.close()
    assert receipt.forced and not receipt.graceful
    assert receipt.host_exited and receipt.job_empty and receipt.profile_removed
    assert harness.process.killed


def test_operations_are_bounded_and_session_is_single_use(harness):
    session = harness.session().start()
    for invalid in (0, 32001, True):
        with pytest.raises(ValueError):
            session.read(max_chars=invalid)
    with pytest.raises(BrowserUnavailable) as caught:
        session.navigate("file:///C:/private.txt")
    assert caught.value.code == "INVALID_URL" and harness.page.visits == []
    session.close()
    with pytest.raises(BrowserUnavailable) as caught:
        session.read()
    assert caught.value.code == "BROWSER_CLOSED"
    with pytest.raises(BrowserUnavailable) as caught:
        session.start()
    assert caught.value.code == "SESSION_ALREADY_USED"


def test_private_control_reader_rejects_oversized_and_invalid_frames():
    for raw in (b"x" * 16385 + b"\n", b"not-json\n", b"[]\n", b"unterminated"):
        reader = browser._ControlReader(io.BytesIO(raw))
        reader.join()
        with pytest.raises(BrowserUnavailable) as caught:
            reader.receive(0.1)
        assert caught.value.code == "HOST_PROTOCOL_ERROR"


def test_dependency_loader_requires_shipped_package_and_rejects_mixed_playwright(tmp_path, monkeypatch):
    with pytest.raises(BrowserUnavailable) as caught:
        browser._load_playwright(tmp_path)
    assert caught.value.code == "PLAYWRIGHT_NOT_AVAILABLE"
    module_path = tmp_path / "python" / "playwright" / "sync_api" / "__init__.py"
    module_path.parent.mkdir(parents=True)
    module_path.touch()
    monkeypatch.setitem(sys.modules, "playwright", SimpleNamespace(__file__=str(tmp_path / "outside.py")))
    with pytest.raises(BrowserUnavailable) as caught:
        browser._load_playwright(tmp_path)
    assert caught.value.code == "PLAYWRIGHT_PACKAGE_CONFLICT"
    assert str(tmp_path / "python") not in sys.path


def test_profile_cleanup_refuses_a_changed_target(harness, tmp_path):
    session = harness.session().start()
    owned_profile = session.profile_directory
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    sentinel = unrelated / "sentinel.txt"
    sentinel.write_text("Keep this file", encoding="utf-8")
    session.profile_directory = unrelated
    assert session._remove_profile() is False
    assert sentinel.read_text(encoding="utf-8") == "Keep this file"
    session.profile_directory = owned_profile
    assert session.close().profile_removed
