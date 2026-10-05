"""Real native-host smoke, identical tests run on Windows/Linux/macOS CI.

No sys.platform/shutil.which/subprocess mocks. A local pass proves only that
host; publishing the workflow is not evidence that the other jobs have run.
"""
import ctypes
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from threading import Thread
import time

import pytest

from local_cli.application.cancellation import CancellationController
from local_cli.shell_executor import ShellExecutionCancelled, create_executor, detect_shell
from local_cli.security import get_sanitized_env


def native():
    descriptor = detect_shell()
    assert descriptor is not None, "Required native shell unavailable on actual host"
    expected = {"win32": "powershell", "darwin": "zsh"}.get(sys.platform, "bash")
    # Native fallback is legitimate if the preferred executable is unavailable.
    assert descriptor.kind in ({"powershell"} if sys.platform == "win32" else {expected, "bash", "sh"})
    return descriptor, create_executor(descriptor)


def python_command(descriptor, path):
    if descriptor.kind == "powershell":
        quote = lambda s: "'" + str(s).replace("'", "''") + "'"
        return "& " + quote(sys.executable) + " " + quote(path) + "; exit $LASTEXITCODE"
    return shlex.quote(sys.executable) + " " + shlex.quote(str(path))


def test_real_native_unicode_quoting_cwd_env_stdout_stderr_exit(tmp_path):
    descriptor, executor = native()
    folder = tmp_path / "á space ' quote"
    folder.mkdir()
    script = folder / "script.py"
    script.write_text("import os,sys\nfrom pathlib import Path\nsys.stdout.reconfigure(encoding='utf-8')\n"
        "print('ñ🧠|' + str(Path.cwd()) + '|' + os.environ['LANG'])\n"
        "print('NATIVE_ERR', file=sys.stderr)\nsys.exit(7)\n", encoding="utf-8")
    # S6 deliberately excludes Nova/internal variables. Exercise compatible
    # locale env here; exact additional passes are covered by S6 native tests.
    environment = {**get_sanitized_env(), "LANG": "native"}
    before = Path.cwd()
    result = executor.run(python_command(descriptor, script), 10, str(folder), environment)
    # python_command explicitly propagates $LASTEXITCODE in PowerShell.
    assert result.returncode == 7
    assert "ñ🧠|" + str(folder) + "|native" in result.stdout
    assert "NATIVE_ERR" in result.stderr
    assert Path.cwd() == before and os.environ.get("LANG") != "native"


@pytest.mark.skipif(sys.platform != "win32", reason="Real Windows PowerShell fallback gate")
def test_real_windows_powershell_fallback_without_pwsh_or_git_bash(tmp_path):
    root = Path(__file__).resolve().parents[1]
    system = Path(os.environ.get("SystemRoot", "C:/Windows"))
    folder = system / "System32/WindowsPowerShell/v1.0"
    assert (folder / "powershell.exe").is_file()
    environment = {**get_sanitized_env(), "PYTHONPATH": str(root),
        "PYTHONIOENCODING": "utf-8", "PATH": os.pathsep.join(map(str, [folder, system / "System32"]))}
    # Restrict only the child's PATH: this is a real detector/executor probe,
    # without patching sys.platform, which(), versions or subprocess results.
    script = """import json
from local_cli.shell_executor import detect_shell, create_executor
from local_cli.security import get_sanitized_env
d=detect_shell()
r=create_executor(d).run("Write-Output 'fallback-ñ🧠'; exit 7", 10, '.', get_sanitized_env())
print(json.dumps({'kind':d.kind,'executable':d.executable,'version':d.version,
                 'stdout':r.stdout,'exitCode':r.returncode}))
"""
    result = subprocess.run([sys.executable, "-c", script], env=environment, cwd=tmp_path,
        capture_output=True, text=True, encoding="utf-8", timeout=20)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["kind"] == "powershell" and data["version"].startswith("5.1")
    assert Path(data["executable"]) == folder / "powershell.exe"
    assert data["exitCode"] == 7 and "fallback-ñ🧠" in data["stdout"]


def process_running(pid):
    if sys.platform == "win32":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            status = ctypes.c_ulong()
            assert kernel.GetExitCodeProcess(handle, ctypes.byref(status))
            return status.value == 259
        finally:
            kernel.CloseHandle(handle)
    status = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, timeout=5)
    return bool(status.stdout.strip()) and not status.stdout.strip().startswith("Z")


@pytest.mark.parametrize("cancel", [False, True])
def test_real_native_timeout_cancel_terminates_child_tree(tmp_path, cancel):
    descriptor, executor = native()
    child = tmp_path / "child.py"
    child.write_text("import os,time\nfrom pathlib import Path\n"
        "Path('child.pid').write_text(str(os.getpid()))\ntime.sleep(30)\n", encoding="utf-8")
    parent = tmp_path / "parent.py"
    parent.write_text("import subprocess,sys,time\n"
        "subprocess.Popen([sys.executable, 'child.py'])\ntime.sleep(30)\n", encoding="utf-8")
    token = CancellationController()
    errors = []
    def run():
        try:
            executor.run(python_command(descriptor, parent), 3, str(tmp_path), get_sanitized_env(),
                         cancellation_token=token if cancel else None)
        except (ShellExecutionCancelled, subprocess.TimeoutExpired) as exc:
            errors.append(exc)
    worker = Thread(target=run)
    worker.start()
    pid_file = tmp_path / "child.pid"
    deadline = time.monotonic() + 2.5
    while not pid_file.exists() and time.monotonic() < deadline:
        time.sleep(.01)
    assert pid_file.exists(), "Child did not start before the test deadline"
    pid = int(pid_file.read_text())
    if cancel:
        token.request()
    worker.join(10)
    assert not worker.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], ShellExecutionCancelled if cancel else subprocess.TimeoutExpired)
    deadline = time.monotonic() + 2
    while process_running(pid) and time.monotonic() < deadline:
        time.sleep(.02)
    assert not process_running(pid), "Child survived native tree termination"
