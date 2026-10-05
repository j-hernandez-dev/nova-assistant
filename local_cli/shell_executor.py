"""Host-selected command interpreters. Tool calls never supply an executable."""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from local_cli.core.contracts import CancellationToken
from local_cli.core.process import ProcessLaunchRequest
from local_cli.process_config import DEFAULT_PROCESS_LIMITS
from local_cli.infrastructure.host_process import HostProcessLauncher
from local_cli.infrastructure.process_environment import minimum_process_environment


class ShellExecutionCancelled(Exception):
    """The process tree was stopped; effects before termination are unknown."""

    def __init__(self, *, started: bool = True, report=None) -> None:
        self.started = started
        self.process_report = report
        super().__init__("shell execution cancelled")


class ShellProcessOutcomeUnknown(Exception):
    def __init__(self, report):
        self.process_report = report
        super().__init__('process cleanup unknown')


@dataclass(frozen=True)
class ShellDescriptor:
    os_name: str
    kind: str
    executable: str
    version: str
    capabilities: tuple[str, ...] = ("pipes", "redirects")


def _probe(kind: str, executable: str) -> str | None:
    if kind == "powershell":
        args = [executable, "-NoProfile", "-NonInteractive", "-Command",
                "$PSVersionTable.PSVersion.ToString()"]
    elif kind == "sh":
        # POSIX sh has no portable --version option.
        args = [executable, "-c", "printf shell-ready"]
    else:
        args = [executable, "--version"]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=3,
            env=minimum_process_environment(os.environ), stdin=subprocess.DEVNULL, close_fds=True)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    if kind == "sh":
        return "unknown" if result.stdout == "shell-ready" else None
    return result.stdout.splitlines()[0].strip() if result.stdout.strip() else "unknown"


def detect_git_bash() -> ShellDescriptor | None:
    """Detect Git for Windows Bash separately from git.exe and native shells."""
    if sys.platform != "win32":
        return None
    roots = [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"),
             os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")]
    candidates = [Path(root) / "Git" / subdir / "bash.exe"
                  for root in roots if root for subdir in ("bin", "usr/bin")]
    path_candidate = shutil.which("bash.exe")
    if path_candidate:
        candidates.append(Path(path_candidate))
    for candidate in candidates:
        # A WSL bash.exe or unrelated binary on PATH is not Git Bash.
        in_git_bin = (candidate.parent.name.lower() == "bin"
                      and candidate.parent.parent.name.lower() == "git")
        in_git_usr_bin = (candidate.parent.name.lower() == "bin"
                          and candidate.parent.parent.name.lower() == "usr"
                          and candidate.parent.parent.parent.name.lower() == "git")
        if candidate.name.lower() != "bash.exe" or not (in_git_bin or in_git_usr_bin):
            continue
        if not candidate.is_file():
            continue
        version = _probe("bash", str(candidate))
        if version is not None:
            return ShellDescriptor("Windows", "bash", str(candidate.resolve()), version)
    return None


def detect_shell(preference: str = "native") -> ShellDescriptor | None:
    """Select a verified native shell; Git Bash requires an explicit host choice."""
    if preference == "git-bash":
        return detect_git_bash()
    if preference != "native":
        raise ValueError(f"Unsupported shell preference: {preference}")
    if sys.platform == "win32":
        os_name = "Windows"
        candidates = (("pwsh.exe", "powershell"), ("powershell.exe", "powershell"))
    elif sys.platform == "darwin":
        os_name = "macOS"
        candidates = (("zsh", "zsh"), ("bash", "bash"), ("sh", "sh"))
    else:
        os_name = "Linux"
        candidates = (("bash", "bash"), ("sh", "sh"))
    for name, kind in candidates:
        found = shutil.which(name)
        if found:
            version = _probe(kind, found)
            if version is not None:
                return ShellDescriptor(os_name, kind, str(Path(found).resolve()), version)
    return None


class PlatformShellExecutor:
    """Execute through a fixed interpreter and terminate its process group on timeout."""

    def __init__(self, descriptor: ShellDescriptor) -> None:
        self.descriptor = descriptor

    def argv(self, command: str) -> list[str]:
        raise NotImplementedError

    def run(self, command: str, timeout: int, cwd: str | None,
            env: dict[str, str], *,
            cancellation_token: CancellationToken | None = None,
            deadline: datetime | None = None) -> subprocess.CompletedProcess[str]:
        """Compatibility facade over the same bounded S4 launcher, not a fallback."""
        if cwd is None:
            raise ValueError("explicit cwd required")
        # Existing Core compatibility callers may supply an explicit relative
        # cwd. Snapshot it once; never change the host's global working directory.
        cwd = str(Path(cwd).resolve())
        argv = self.argv(command)
        executable = Path(self.descriptor.executable)
        argv[0] = str(executable if executable.is_absolute() else Path(
            shutil.which(str(executable)) or Path(cwd)/executable))
        request = ProcessLaunchRequest(command, tuple(argv), str(cwd),
            minimum_process_environment(env), max(1, min(timeout, DEFAULT_PROCESS_LIMITS.max_timeout)),
            DEFAULT_PROCESS_LIMITS)
        class NotCancelled:
            def is_cancel_requested(self):
                return False
        report = HostProcessLauncher().launch(request,
            cancellation_token=cancellation_token or NotCancelled(),
            deadline=deadline, validate_launch=lambda: None)
        if report.error_code == "PROCESS_CANCELLED":
            raise ShellExecutionCancelled(started=report.pid is not None, report=report)
        if report.error_code == "PROCESS_TIMEOUT":
            error = subprocess.TimeoutExpired(argv, timeout, output=report.stdout, stderr=report.stderr)
            error.process_report = report
            raise error
        if report.outcome == "outcome_unknown":
            raise ShellProcessOutcomeUnknown(report)
        if report.pid is None:
            error = FileNotFoundError(report.error_code) if report.error_code == "EXECUTABLE_NOT_FOUND" else OSError(
                report.error_code)
            error.process_report = report
            raise error
        result = subprocess.CompletedProcess(argv, report.exit_code, report.stdout, report.stderr)
        result.process_report = report
        return result

class PowerShellExecutor(PlatformShellExecutor):
    def argv(self, command: str) -> list[str]:
        # Make both Windows PowerShell and pwsh emit UTF-8 over captured pipes.
        script = ("$OutputEncoding = [Console]::OutputEncoding = "
                  "[System.Text.UTF8Encoding]::new($false); " + command)
        encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        return [self.descriptor.executable, "-NoLogo", "-NoProfile",
                "-NonInteractive", "-EncodedCommand", encoded]


class BashExecutor(PlatformShellExecutor):
    def argv(self, command: str) -> list[str]:
        return [self.descriptor.executable, "--noprofile", "--norc", "-c", command]


class ZshExecutor(PlatformShellExecutor):
    def argv(self, command: str) -> list[str]:
        return [self.descriptor.executable, "-f", "-c", command]


class ShExecutor(PlatformShellExecutor):
    def argv(self, command: str) -> list[str]:
        return [self.descriptor.executable, "-c", command]


def create_executor(descriptor: ShellDescriptor) -> PlatformShellExecutor:
    classes = {"powershell": PowerShellExecutor, "bash": BashExecutor,
               "zsh": ZshExecutor, "sh": ShExecutor}
    return classes[descriptor.kind](descriptor)
