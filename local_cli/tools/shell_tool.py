"""Public command tool backed by a host-selected platform executor."""

from __future__ import annotations

import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

from local_cli.security import SANITIZED_ENV_VARS, get_sanitized_env
from local_cli.shell_executor import (
    PlatformShellExecutor, ShellDescriptor, ShellExecutionCancelled,
    create_executor, detect_shell,
)
from local_cli.shell_policy import ShellDecision, ShellPolicy
from local_cli.core.contracts import CancellationToken, EffectState, ToolResult, ToolStatus
from local_cli.tools.base import Tool
from local_cli.tools._paths import capture_cwd

_MAX_OUTPUT_BYTES = 100 * 1024
_DEFAULT_TIMEOUT = 120


class ShellTool(Tool):
    """Execute one command in the selected dialect; the model cannot switch it."""

    def __init__(self, confirm: Callable[[str], bool] | None = None,
                 *, descriptor: ShellDescriptor | None = None,
                 executor: PlatformShellExecutor | None = None,
                 policy: ShellPolicy | None = None,
                 preference: str = "native",
                 cwd: str | Path | None = None,
                 environment: Mapping[str, str] | None = None) -> None:
        self._confirm = confirm
        self.cwd = capture_cwd(cwd)
        blocked = {key.casefold() for key in SANITIZED_ENV_VARS}
        self.environment = (get_sanitized_env() if environment is None else {
            key: value for key, value in environment.items()
            if key.casefold() not in blocked
        })
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
        return self.execute_result(**kwargs).legacy_text or ""

    def execute_result(self, **kwargs: object) -> ToolResult:
        """Expose a typed outcome while retaining the exact legacy text."""
        return self._execute_result(kwargs)

    def execute_with_approval(self, *, cancellation_token: CancellationToken,
                              deadline: datetime | None,
                              **kwargs: object) -> ToolResult:
        """Application-only path; ToolRuntime has already checked the gate."""
        return self._execute_result(kwargs, approval_granted=True,
                                    cancellation_token=cancellation_token,
                                    deadline=deadline)

    def execute_with_context(self, *, cancellation_token: CancellationToken,
                             deadline: datetime | None,
                             **kwargs: object) -> ToolResult:
        return self._execute_result(kwargs, cancellation_token=cancellation_token,
                                    deadline=deadline)

    def _execute_result(self, kwargs: Mapping[str, object], *,
                        approval_granted: bool = False,
                        cancellation_token: CancellationToken | None = None,
                        deadline: datetime | None = None) -> ToolResult:
        def error(status: ToolStatus, text: str,
                  effect: EffectState = EffectState.NONE) -> ToolResult:
            return ToolResult(status, effect, error=text, legacy_text=text)

        command = kwargs.get("command")
        if not isinstance(command, str) or not command.strip():
            return error(ToolStatus.FAILED,
                         "Error: 'command' parameter is required and must be a non-empty string.")
        if self.descriptor is None or self._executor is None:
            return error(ToolStatus.FAILED,
                         "Error: no supported command shell is available on this host.")
        timeout = kwargs.get("timeout", _DEFAULT_TIMEOUT)
        if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                or not math.isfinite(timeout)):
            timeout = _DEFAULT_TIMEOUT
        timeout = max(1, min(int(timeout), 600))
        decision = self._policy.classify(command, self.descriptor)
        if decision is ShellDecision.BLOCK:
            return error(ToolStatus.DENIED,
                         f"Error: command blocked by security policy: {command}")
        if cancellation_token is not None and cancellation_token.is_cancel_requested():
            return error(ToolStatus.CANCELLED, "Error: command cancelled before execution.")
        if (decision is ShellDecision.CONFIRM and not approval_granted
                and self._confirm is not None):
            if not self._confirm(command):
                return error(ToolStatus.DENIED,
                             f"Command declined (not run): {command}\n"
                             "This risky command was not approved. Use a less destructive "
                             "alternative, or ask the user to run it themselves.")
        if ((cancellation_token is not None and cancellation_token.is_cancel_requested())
                or (deadline is not None and datetime.now(timezone.utc) >= deadline)):
            return error(ToolStatus.CANCELLED,
                         "Error: command cancelled before execution.")
        try:
            if cancellation_token is None and deadline is None:
                result = self._executor.run(command, timeout, str(self.cwd),
                                            dict(self.environment))
            else:
                result = self._executor.run(
                    command, timeout, str(self.cwd), dict(self.environment),
                    cancellation_token=cancellation_token, deadline=deadline,
                )
        except ShellExecutionCancelled as exc:
            if not exc.started:
                return error(ToolStatus.CANCELLED,
                             "Error: command cancelled before execution.")
            return error(ToolStatus.OUTCOME_UNKNOWN,
                         "Error: command cancelled after execution began; outcome unknown.",
                         EffectState.UNKNOWN)
        except subprocess.TimeoutExpired:
            return error(ToolStatus.OUTCOME_UNKNOWN,
                         f"Error: command timed out after {timeout} seconds.",
                         EffectState.UNKNOWN)
        except PermissionError as exc:
            return error(ToolStatus.FAILED, f"Error: permission denied: {exc}")
        except OSError as exc:
            return error(ToolStatus.FAILED,
                         f"Error: failed to execute command: {exc}")
        output = (result.stdout or "") + (result.stderr or "")
        encoded = output.encode("utf-8", errors="replace")
        if len(encoded) > _MAX_OUTPUT_BYTES:
            output = encoded[:_MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
            output += "\n... [output truncated at 100KB]"
        if result.returncode != 0:
            output = f"{output.rstrip()}\n[exit code: {result.returncode}]"
        stdout_bytes = (result.stdout or "").encode("utf-8", errors="replace")
        stderr_bytes = (result.stderr or "").encode("utf-8", errors="replace")
        streams_truncated = (len(stdout_bytes) > _MAX_OUTPUT_BYTES or
                             len(stderr_bytes) > _MAX_OUTPUT_BYTES)
        return ToolResult(
            status=(ToolStatus.COMPLETED if result.returncode == 0
                    else ToolStatus.FAILED),
            effect_state=EffectState.UNKNOWN,
            stdout=stdout_bytes[:_MAX_OUTPUT_BYTES].decode("utf-8", errors="replace"),
            stderr=stderr_bytes[:_MAX_OUTPUT_BYTES].decode("utf-8", errors="replace"),
            exit_code=result.returncode,
            legacy_text=output,
            metadata={"rawStreamsTruncated": streams_truncated},
        )
