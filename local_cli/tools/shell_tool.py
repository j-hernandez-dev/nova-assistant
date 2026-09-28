"""Public command tool backed by a host-selected platform executor."""

from __future__ import annotations

import os
import math
import subprocess
from typing import Callable

from local_cli.security import get_sanitized_env
from local_cli.shell_executor import (
    PlatformShellExecutor, ShellDescriptor, create_executor, detect_shell,
)
from local_cli.shell_policy import ShellDecision, ShellPolicy
from local_cli.tools.base import Tool

_MAX_OUTPUT_BYTES = 100 * 1024
_DEFAULT_TIMEOUT = 120


class ShellTool(Tool):
    """Execute one command in the selected dialect; the model cannot switch it."""

    def __init__(self, confirm: Callable[[str], bool] | None = None,
                 *, descriptor: ShellDescriptor | None = None,
                 executor: PlatformShellExecutor | None = None,
                 policy: ShellPolicy | None = None,
                 preference: str = "native") -> None:
        self._confirm = confirm
        self.descriptor = descriptor or detect_shell(preference)
        self._executor = executor or (create_executor(self.descriptor) if self.descriptor else None)
        self._policy = policy or ShellPolicy()

    @property
    def name(self) -> str:
        # Wire compatibility for existing prompts, providers and transcripts.
        return "bash"

    @property
    def description(self) -> str:
        if self.descriptor is None:
            return "Run a command using the host-selected shell (currently unavailable)."
        return ("Run a command using the host-selected "
                f"{self.descriptor.kind} shell on {self.descriptor.os_name}. "
                "The tool name 'bash' is retained for compatibility; "
                "write commands in the selected shell's syntax.")

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command in the selected shell's syntax."},
                "timeout": {"type": "integer", "description": "Maximum seconds (default 120)."},
            },
            "required": ["command"],
        }

    def execute(self, **kwargs: object) -> str:
        command = kwargs.get("command")
        if not isinstance(command, str) or not command.strip():
            return "Error: 'command' parameter is required and must be a non-empty string."
        if self.descriptor is None or self._executor is None:
            return "Error: no supported command shell is available on this host."
        timeout = kwargs.get("timeout", _DEFAULT_TIMEOUT)
        if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                or not math.isfinite(timeout)):
            timeout = _DEFAULT_TIMEOUT
        timeout = max(1, min(int(timeout), 600))
        decision = self._policy.classify(command, self.descriptor)
        if decision is ShellDecision.BLOCK:
            return f"Error: command blocked by security policy: {command}"
        if decision is ShellDecision.CONFIRM and self._confirm is not None:
            if not self._confirm(command):
                return (f"Command declined (not run): {command}\n"
                        "This risky command was not approved. Use a less destructive "
                        "alternative, or ask the user to run it themselves.")
        try:
            result = self._executor.run(command, timeout, os.getcwd(), get_sanitized_env())
        except subprocess.TimeoutExpired:
            return f"Error: command timed out after {timeout} seconds."
        except PermissionError as exc:
            return f"Error: permission denied: {exc}"
        except OSError as exc:
            return f"Error: failed to execute command: {exc}"
        output = (result.stdout or "") + (result.stderr or "")
        encoded = output.encode("utf-8", errors="replace")
        if len(encoded) > _MAX_OUTPUT_BYTES:
            output = encoded[:_MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
            output += "\n... [output truncated at 100KB]"
        if result.returncode != 0:
            output = f"{output.rstrip()}\n[exit code: {result.returncode}]"
        return output
