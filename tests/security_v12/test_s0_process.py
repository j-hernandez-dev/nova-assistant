"""S0 characterization of the current process boundary using synthetic fixtures.

The host tests use an isolated Python driver, a finite Python child, synthetic
environment values, and files contained in one temporary fixture directory.
They document current behavior; they do not establish process confinement.
"""

from __future__ import annotations

import inspect
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import Mock

import pytest

from local_cli import security
from local_cli import shell_executor
from local_cli.core.contracts import ToolStatus
from local_cli.shell_executor import ShellDescriptor, create_executor
from local_cli.tools.shell_tool import ShellTool


OUTPUT_LIMIT = 100 * 1024
BLOCKED_CANARY = "NOVA_S0_BLOCKED_CANARY"
UNLISTED_CANARY = "NOVA_S0_UNLISTED_CANARY"
STDIN_CANARY = "NOVA_S0_STDIN_CANARY\n"
FILE_CANARY = "NOVA_S0_SIBLING_FILE_CANARY"
SYNTHETIC_DESCRIPTOR = ShellDescriptor(
    "Linux", "bash", "/s0-fixture/no-executable/bash", "S0 fixture"
)


@pytest.mark.parametrize("explicit_environment", [False, True])
def test_synthetic_environment_is_filtered_and_captured_before_execution(
    tmp_path, monkeypatch, explicit_environment
):
    synthetic = {
        key.swapcase(): BLOCKED_CANARY for key in security.SANITIZED_ENV_VARS
    }
    synthetic.update({
        "NOVA_FIXTURE_SECRET": UNLISTED_CANARY,
        "NOVA_FIXTURE_NORMAL": "NOVA_S0_NORMAL_CANARY",
    })
    # Replace the mapping only for this test: do not read or copy the host env.
    monkeypatch.setattr(security.os, "environ", synthetic)
    executor = Mock()
    executor.run.return_value = subprocess.CompletedProcess([], 0, "ok\n", "")
    kwargs = {"environment": synthetic} if explicit_environment else {}
    tool = ShellTool(
        descriptor=SYNTHETIC_DESCRIPTOR,
        executor=executor,
        cwd=tmp_path,
        **kwargs,
    )
    expected = {
        "NOVA_FIXTURE_SECRET": UNLISTED_CANARY,
        "NOVA_FIXTURE_NORMAL": "NOVA_S0_NORMAL_CANARY",
    }
    assert tool.environment == expected
    synthetic["NOVA_FIXTURE_SECRET"] = "NOVA_S0_CHANGED_AFTER_CONSTRUCTION"
    synthetic["NOVA_FIXTURE_LATE"] = "NOVA_S0_LATE_CANARY"

    result = tool.execute_result(command="echo S0-fixture")

    assert result.status is ToolStatus.COMPLETED
    assert executor.run.call_args.args[3] == expected
    assert executor.run.call_args.args[3] is not tool.environment
    assert tool.environment == expected


@pytest.mark.parametrize(
    "os_name,kind,expected_session,expected_flags",
    [("Linux", "bash", True, 0), ("Windows", "powershell", False, 512)],
)
def test_executor_uses_popen_stdin_and_handle_defaults_with_mocked_launch(
    tmp_path, monkeypatch, os_name, kind, expected_session, expected_flags
):
    # Characterize Python defaults before replacing Popen; the app omits them.
    parameters = inspect.signature(subprocess.Popen).parameters
    assert parameters["stdin"].default is None
    assert parameters["close_fds"].default is True
    assert parameters["pass_fds"].default == ()
    process = Mock()
    process.returncode = 0
    process.communicate.return_value = ("NOVA_S0_STDOUT", "NOVA_S0_STDERR")
    popen = Mock(return_value=process)
    monkeypatch.setattr(shell_executor.subprocess, "Popen", popen)
    # The Windows branch remains a pure unit case on a POSIX test host.
    monkeypatch.setattr(
        shell_executor.subprocess, "CREATE_NEW_PROCESS_GROUP", 512, raising=False
    )
    descriptor = ShellDescriptor(
        os_name, kind, "/s0-fixture/no-executable/shell", "S0 fixture"
    )
    executor = create_executor(descriptor)
    environment = {
        "NOVA_FIXTURE_SECRET": UNLISTED_CANARY,
        "OPENAI_API_KEY": BLOCKED_CANARY,
    }

    result = executor.run("echo S0-fixture", 3, str(tmp_path), environment)

    assert popen.call_args.args == (executor.argv("echo S0-fixture"),)
    launch = popen.call_args.kwargs
    assert launch["cwd"] == str(tmp_path)
    assert launch["env"] == environment
    assert launch["stdout"] == subprocess.PIPE
    assert launch["stderr"] == subprocess.PIPE
    assert launch["text"] is True
    assert launch["encoding"] == "utf-8"
    assert launch["errors"] == "replace"
    assert launch["start_new_session"] is expected_session
    assert launch["creationflags"] == expected_flags
    assert all(
        option not in launch
        for option in ("stdin", "close_fds", "pass_fds", "startupinfo", "shell")
    )
    process.communicate.assert_called_once_with(timeout=3)
    assert (result.stdout, result.stderr, result.returncode) == (
        "NOVA_S0_STDOUT", "NOVA_S0_STDERR", 0
    )


@pytest.mark.parametrize(
    "stdout_size,stderr_size,legacy_truncated,streams_truncated",
    [
        (OUTPUT_LIMIT, 0, False, False),
        (OUTPUT_LIMIT + 32, 0, True, True),
        (0, OUTPUT_LIMIT + 32, True, True),
        (60 * 1024, 60 * 1024, True, False),
    ],
)
def test_output_limits_apply_after_executor_returns_complete_streams(
    tmp_path, stdout_size, stderr_size, legacy_truncated, streams_truncated
):
    stdout, stderr = "A" * stdout_size, "B" * stderr_size
    executor = Mock()
    executor.run.return_value = subprocess.CompletedProcess([], 0, stdout, stderr)
    tool = ShellTool(
        descriptor=SYNTHETIC_DESCRIPTOR,
        executor=executor,
        cwd=tmp_path,
        environment={},
    )

    result = tool.execute_result(command="echo S0-fixture")

    assert result.stdout == stdout[:OUTPUT_LIMIT]
    assert result.stderr == stderr[:OUTPUT_LIMIT]
    expected_legacy = (stdout + stderr)[:OUTPUT_LIMIT]
    if legacy_truncated:
        expected_legacy += "\n... [output truncated at 100KB]"
    assert result.legacy_text == expected_legacy
    assert result.metadata["rawStreamsTruncated"] is streams_truncated
    assert executor.run.return_value.stdout == stdout
    assert executor.run.return_value.stderr == stderr


def test_output_byte_boundary_uses_replacement_for_partial_utf8(tmp_path):
    stdout = "A" * (OUTPUT_LIMIT - 1) + "€"
    executor = Mock()
    executor.run.return_value = subprocess.CompletedProcess([], 0, stdout, "")
    tool = ShellTool(
        descriptor=SYNTHETIC_DESCRIPTOR,
        executor=executor,
        cwd=tmp_path,
        environment={},
    )

    result = tool.execute_result(command="echo S0-fixture")

    expected = "A" * (OUTPUT_LIMIT - 1) + "\ufffd"
    assert result.stdout == expected
    assert len(result.stdout.encode("utf-8")) == OUTPUT_LIMIT + 2
    assert result.legacy_text == expected + "\n... [output truncated at 100KB]"
    assert result.metadata["rawStreamsTruncated"] is True


def test_timeout_result_does_not_return_partial_captured_output(tmp_path):
    executor = Mock()
    executor.run.side_effect = subprocess.TimeoutExpired(
        "S0 fixture", 1, output="NOVA_S0_PARTIAL_OUT", stderr="NOVA_S0_PARTIAL_ERR"
    )
    tool = ShellTool(
        descriptor=SYNTHETIC_DESCRIPTOR,
        executor=executor,
        cwd=tmp_path,
        environment={},
    )

    result = tool.execute_result(command="echo S0-fixture", timeout=1)

    assert result.status is ToolStatus.OUTCOME_UNKNOWN
    assert result.stdout == ""
    assert result.stderr == ""
    assert result.legacy_text == "Error: command timed out after 1 seconds."


def _native_descriptor():
    """Resolve a host shell without executing detection's ambient-env probe."""
    if sys.platform == "win32":
        os_name = "Windows"
        candidates = (("pwsh.exe", "powershell"), ("powershell.exe", "powershell"))
    elif sys.platform == "darwin":
        os_name = "macOS"
        candidates = (("zsh", "zsh"), ("bash", "bash"), ("sh", "sh"))
    else:
        os_name = "Linux"
        candidates = (("bash", "bash"), ("sh", "sh"))
    for executable, kind in candidates:
        found = shutil.which(executable)
        if found:
            return ShellDescriptor(os_name, kind, str(Path(found).resolve()), "S0 fixture")
    pytest.skip("No native host shell is available for the S0 process fixture")


def _fixture_environment(tmp_path, extra=None):
    environment = {
        "PYTHONIOENCODING": "utf-8",
        "HOME": str(tmp_path),
        "USERPROFILE": str(tmp_path),
        "TEMP": str(tmp_path),
        "TMP": str(tmp_path),
    }
    if sys.platform == "win32":
        # PowerShell's native executable handling depends on PATHEXT. Omitting
        # it made this fixture return before Python, without its streams. The
        # controlled comparison is retained in S0 evidence; this is a fixture
        # prerequisite, not a change to Nova's environment policy.
        environment["PATHEXT"] = ".COM;.EXE;.BAT;.CMD"
        # These OS installation paths are the only ambient values forwarded.
        # User profiles, PATH, tokens, service URLs and other env are not copied.
        for key in ("SystemRoot", "WINDIR"):
            value = os.environ.get(key)
            if value:
                environment[key] = value
    if extra:
        environment.update(extra)
    return environment


def _runtime_python_executable():
    """Prefer the real interpreter file under base_prefix over a launch alias."""
    executable_name = "python.exe" if sys.platform == "win32" else "bin/python"
    candidates = [Path(sys.base_prefix) / executable_name]
    base_executable = getattr(sys, "_base_executable", None)
    if base_executable:
        candidates.append(Path(base_executable))
    candidates.append(Path(sys.executable))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())
    pytest.fail("No concrete Python interpreter file was found for the S0 driver")


DRIVER_SOURCE = r'''import json
import os
from pathlib import Path
import shlex
import sys

sys.path.insert(0, sys.argv[1])
from local_cli.shell_executor import ShellDescriptor, create_executor
from local_cli.tools.shell_tool import ShellTool

descriptor = ShellDescriptor(sys.argv[2], sys.argv[3], sys.argv[4], "S0 fixture")
fixture = Path(sys.argv[5])
workspace = Path(sys.argv[6])
mode = sys.argv[7]
python_executable = sys.argv[8]
if descriptor.kind == "powershell":
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    if mode == "tool":
        # ShellPolicy blocks PowerShell's call operator. This executable name
        # resolves through a synthetic PATH containing only its own folder.
        command = Path(python_executable).name + " -I " + quote(fixture) + "; exit $LASTEXITCODE"
    else:
        command = "& " + quote(python_executable) + " -I " + quote(fixture) + "; exit $LASTEXITCODE"
else:
    command = shlex.quote(python_executable) + " -I " + shlex.quote(str(fixture))
raw = {"python_executable": sys.executable,
       "python_base_executable": getattr(sys, "_base_executable", None),
       "python_base_prefix": sys.base_prefix, "selected_python": python_executable,
       "command": command}
try:
    if mode == "executor":
        result = create_executor(descriptor).run(command, 5, str(workspace), dict(os.environ))
        raw.update({"status": "completed" if result.returncode == 0 else "failed",
                    "exit_code": result.returncode,
                    "stdout": result.stdout, "stderr": result.stderr})
    else:
        result = ShellTool(descriptor=descriptor, cwd=workspace).execute_result(
            command=command, timeout=5)
        raw.update({"status": result.status.value, "exit_code": result.exit_code,
                    "stdout": result.stdout, "stderr": result.stderr,
                    "error": result.error})
except Exception as exc:
    output = getattr(exc, "output", None)
    error_output = getattr(exc, "stderr", None)
    raw.update({"status": "exception", "exit_code": None,
                "exception": type(exc).__name__,
                "stdout": output.decode("utf-8", errors="replace") if isinstance(output, bytes) else output,
                "stderr": error_output.decode("utf-8", errors="replace") if isinstance(error_output, bytes) else error_output})
# Persist the exact child streams before printing or parsing the report.
(workspace / "driver_child_raw.json").write_text(json.dumps(raw), encoding="utf-8")
print(json.dumps(raw), flush=True)
'''


def _assert_recorded_fixture_child_closed(child_started):
    """Query only the PID that the synthetic child recorded; never signal it."""
    marker = json.loads(child_started.read_text(encoding="utf-8"))
    assert marker["marker"] == "NOVA_S0_CHILD_STARTED"
    pid = marker["pid"]
    assert isinstance(pid, int) and pid > 0
    if sys.platform == "win32":
        import ctypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.GetExitCodeProcess.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)
        ]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            assert ctypes.get_last_error() == 87, "Child closure could not be verified"
            return
        try:
            status = ctypes.c_ulong()
            assert kernel.GetExitCodeProcess(handle, ctypes.byref(status))
            assert status.value != 259, "The synthetic child remained running"
        finally:
            kernel.CloseHandle(handle)
    else:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        pytest.fail("The recorded synthetic child PID still exists")


def _run_host_fixture(
    tmp_path, fixture_source, *, mode, input_text="", extra_env=None,
    raw_observation_path=None,
):
    descriptor = _native_descriptor()
    workspace = tmp_path / "workspace ' spaces"
    workspace.mkdir()
    fixture = workspace / "fixture ' child.py"
    child_started = workspace / "child_started.json"
    prefix = (
        "import json,os,sys\nfrom pathlib import Path\n"
        f"Path({str(child_started)!r}).write_text(json.dumps({{"
        "'marker': 'NOVA_S0_CHILD_STARTED', 'pid': os.getpid(), "
        "'python_executable': sys.executable, 'python_base_prefix': sys.base_prefix"
        "}), encoding='utf-8')\n"
    )
    fixture.write_text(prefix + fixture_source, encoding="utf-8")
    driver = tmp_path / "isolated_driver.py"
    driver.write_text(DRIVER_SOURCE, encoding="utf-8")
    repository = Path(shell_executor.__file__).resolve().parent.parent
    python_executable = _runtime_python_executable()
    environment = _fixture_environment(tmp_path, extra_env)
    environment["PYTHONPATH"] = str(repository)
    environment["PATH"] = str(Path(python_executable).parent)
    driver_raw = tmp_path / "host_driver_raw.json"
    command = [
        python_executable, "-I", str(driver), str(repository),
        descriptor.os_name, descriptor.kind, descriptor.executable,
        str(fixture), str(workspace), mode, python_executable,
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=workspace,
            env=environment,
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        raw = {"driver_returncode": completed.returncode,
               "driver_stdout": completed.stdout, "driver_stderr": completed.stderr}
    except subprocess.TimeoutExpired as exc:
        raw = {"exception": "TimeoutExpired", "driver_stdout": repr(exc.output),
               "driver_stderr": repr(exc.stderr)}
        raw.update({"command": command, "child_started": child_started.exists()})
        driver_raw.write_text(json.dumps(raw), encoding="utf-8")
        raise
    raw.update({"command": command, "child_started": child_started.exists(),
                "child_stream_report_exists": (workspace / "driver_child_raw.json").exists(),
                "parent_sys_executable": sys.executable,
                "parent_base_executable": getattr(sys, "_base_executable", None),
                "parent_base_prefix": sys.base_prefix})
    driver_raw.write_text(json.dumps(raw), encoding="utf-8")
    assert completed.returncode == 0, "The isolated S0 fixture driver failed"
    assert completed.stdout.strip(), "Driver stdout is empty; see host_driver_raw.json"
    result = json.loads(completed.stdout)
    assert result["status"] == "completed"
    assert result["exit_code"] == 0
    assert child_started.is_file(), "The Python fixture did not record that it started"
    _assert_recorded_fixture_child_closed(child_started)
    # Runtime launcher diagnostics on stderr are outside these stdin/env cases.
    if result["stdout"].strip():
        return json.loads(result["stdout"]), "stdout"
    if raw_observation_path is not None and raw_observation_path.is_file():
        return None, "child_raw_file"
    pytest.fail("Child stdout is empty and no child observation artifact exists")


def test_host_real_executor_observes_synthetic_stdin_with_finite_child(
    tmp_path, record_property
):
    child_raw = tmp_path / "workspace ' spaces" / "stdin_child_raw.json"
    child_bytes = child_raw.with_suffix(".bin")
    fixture_source = (
        "import json,os,sys\nfrom pathlib import Path\n"
        "from threading import Event,Thread\n"
        "received = {}\nfinished = Event()\n"
        "def receive():\n"
        " try:\n"
        # Text-mode stdin may translate LF to CRLF on Windows; retain the
        # full raw line, including either explicit terminator, before matching.
        f"  received['data'] = sys.stdin.buffer.readline({len(STDIN_CANARY.encode('ascii')) + 2})\n"
        " except BaseException as exc:\n"
        "  received['error'] = type(exc).__name__\n"
        " finally:\n"
        "  finished.set()\n"
        "reader = Thread(target=receive, daemon=True)\nreader.start()\n"
        "reader.join(1.5)\n"
        "payload = received.get('data', b'')\n"
        "raw = {'read_completed': finished.is_set(), 'data_hex': payload.hex(),\n"
        "       'read_error': received.get('error'), 'reader_alive': reader.is_alive(),\n"
        "       'reader_deadline_seconds': 1.5}\n"
        f"Path({str(child_bytes)!r}).write_bytes(payload)\n"
        f"Path({str(child_raw)!r}).write_text(json.dumps(raw), encoding='utf-8')\n"
        "if not raw['read_completed']:\n"
        " observation, inherited = 'UNKNOWN', None\n"
        f"elif payload in ({STDIN_CANARY.encode('ascii')!r}, {STDIN_CANARY.replace(chr(10), chr(13) + chr(10)).encode('ascii')!r}):\n"
        " observation, inherited = 'OBSERVED', True\n"
        "else:\n"
        " observation, inherited = 'INPUT_NOT_OBSERVED', False\n"
        "print(json.dumps({'stdin_observation': observation, 'inherited_canary': inherited}), flush=True)\n"
        # Exit the fixture itself even when its daemon reader is still blocked.
        "os._exit(0)\n"
    )

    observed, transport = _run_host_fixture(
        tmp_path, fixture_source, mode="executor", input_text=STDIN_CANARY,
        raw_observation_path=child_raw,
    )

    assert child_raw.is_file(), "The child did not persist its stdin observation"
    raw = json.loads(child_raw.read_text(encoding="utf-8"))
    payload = bytes.fromhex(raw["data_hex"])
    if not raw["read_completed"]:
        expected = {"stdin_observation": "UNKNOWN", "inherited_canary": None}
    elif payload in (STDIN_CANARY.encode("ascii"),
                     STDIN_CANARY.replace("\n", "\r\n").encode("ascii")):
        expected = {"stdin_observation": "OBSERVED", "inherited_canary": True}
    else:
        expected = {
            "stdin_observation": "INPUT_NOT_OBSERVED", "inherited_canary": False
        }
    record_property("s0.stdin.observation", expected["stdin_observation"])
    record_property("s0.stdin.payload_hex", raw["data_hex"])
    record_property("s0.stdin.read_completed", raw["read_completed"])
    record_property("s0.stdin.read_error", raw["read_error"])
    record_property("s0.stdin.report_transport", transport)
    record_property("s0.stdin.reader_deadline_seconds", raw["reader_deadline_seconds"])
    record_property("s0.stdin.child_closed", True)
    assert raw["reader_deadline_seconds"] == 1.5
    assert child_bytes.read_bytes() == payload
    if observed is not None:
        assert observed == expected
    else:
        assert transport == "child_raw_file"


def test_host_real_shelltool_filters_env_and_reads_sibling_dummy_file(
    tmp_path, record_property
):
    private_fixture = tmp_path / "private_fixture"
    private_fixture.mkdir()
    dummy = private_fixture / "dummy_canary.txt"
    dummy.write_text(FILE_CANARY, encoding="utf-8")
    fixture_source = (
        "import json,os\nfrom pathlib import Path\n"
        "keys = {key.casefold() for key in os.environ}\n"
        "observed = {\n"
        " 'blocked_keys_present': bool(keys & {'openai_api_key','github_token','bash_env'}),\n"
        f" 'unlisted_canary_retained': os.environ.get('NOVA_FIXTURE_SECRET') == {UNLISTED_CANARY!r},\n"
        f" 'sibling_dummy_readable': Path({str(dummy)!r}).read_text(encoding='utf-8') == {FILE_CANARY!r},\n"
        "}\nprint(json.dumps(observed))\n"
    )

    observed, transport = _run_host_fixture(
        tmp_path,
        fixture_source,
        mode="tool",
        extra_env={
            "OPENAI_API_KEY": BLOCKED_CANARY,
            "gItHuB_tOkEn": BLOCKED_CANARY,
            "BASH_ENV": "NOVA_S0_DUMMY_STARTUP_HOOK",
            "NOVA_FIXTURE_SECRET": UNLISTED_CANARY,
        },
    )

    record_property("s0.env.blocked_keys_present", observed["blocked_keys_present"])
    record_property("s0.env.unlisted_canary_retained", observed["unlisted_canary_retained"])
    record_property("s0.authority.sibling_dummy_readable", observed["sibling_dummy_readable"])
    record_property("s0.env.report_transport", transport)
    record_property("s0.env.child_closed", True)
    assert observed == {
        "blocked_keys_present": False,
        "unlisted_canary_retained": True,
        "sibling_dummy_readable": True,
    }
