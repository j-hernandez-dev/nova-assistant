"""Host-selected command interpreters. Tool calls never supply an executable."""

from __future__ import annotations

import base64
import os
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


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
        result = subprocess.run(args, capture_output=True, text=True, timeout=3)
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
            env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        windows = self.descriptor.os_name == "Windows"
        proc = subprocess.Popen(
            self.argv(command), cwd=cwd, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if windows else 0,
            start_new_session=not windows,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            if windows:
                # taskkill /T also stops descendants left behind by the shell.
                try:
                    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                                   capture_output=True, timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            else:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if proc.poll() is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
            try:
                proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                # A descendant may still hold a pipe open if the platform's
                # tree-kill facility failed. Do not hang the agent forever.
                if proc.stdout:
                    proc.stdout.close()
                if proc.stderr:
                    proc.stderr.close()
            raise
        return subprocess.CompletedProcess(self.argv(command), proc.returncode, stdout, stderr)


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
