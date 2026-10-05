"""S4 host-process contracts. Limits are explicit, not OS containment quotas."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import math
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Mapping, Protocol

from local_cli.core.contracts import CancellationToken, EffectState, ToolResult, ToolStatus


@dataclass(frozen=True)
class ProcessLimits:
    """Explicit host configuration. Product defaults live in the composition config."""
    stdout_bytes: int
    stderr_bytes: int
    published_bytes: int
    default_timeout: float
    max_timeout: float
    cleanup_seconds: float
    max_concurrent: int

    def __post_init__(self):
        for name in ('stdout_bytes', 'stderr_bytes', 'published_bytes', 'max_concurrent'):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError('invalid process limit: ' + name)
        for name in ('default_timeout', 'max_timeout', 'cleanup_seconds'):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError('invalid process limit: ' + name)
        if self.default_timeout > self.max_timeout:
            raise ValueError('default timeout exceeds maximum')


@dataclass(frozen=True)
class ProcessLaunchRequest:
    """Internal, already authorized launch snapshot; never supplied by the LLM."""
    command: str
    argv: tuple[str, ...]
    cwd: str
    environment: Mapping[str, str]
    timeout_seconds: float
    limits: ProcessLimits
    correlation: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if type(self.limits) is not ProcessLimits:
            raise ValueError('explicit process limits required')
        if not isinstance(self.command, str) or not self.command.strip():
            raise ValueError('missing command')
        argv = tuple(self.argv)
        if (not argv or any(type(x) is not str or '\0' in x for x in argv)
                or not Path(argv[0]).is_absolute()):
            raise ValueError('host executable must be absolute')
        if not Path(self.cwd).is_absolute() or '\0' in self.cwd:
            raise ValueError('explicit absolute cwd required')
        if (type(self.timeout_seconds) not in (int, float)
                or not math.isfinite(self.timeout_seconds)
                or not 0 < self.timeout_seconds <= self.limits.max_timeout):
            raise ValueError('invalid timeout')
        if any(type(k) is not str or type(v) is not str or not k or '=' in k
               or '\0' in k + v for k, v in self.environment.items()):
            raise ValueError('invalid environment')
        if any(type(k) is not str or type(v) is not str for k, v in self.correlation.items()):
            raise ValueError('correlation contains only opaque IDs and safe strings')
        object.__setattr__(self, 'argv', argv)
        object.__setattr__(self, 'environment', MappingProxyType(dict(self.environment)))
        object.__setattr__(self, 'correlation', MappingProxyType(dict(self.correlation)))


@dataclass(frozen=True)
class ProcessReport:
    pid: int | None
    exit_code: int | None
    stdout: str
    stderr: str
    outcome: str
    error_code: str | None
    states: tuple[str, ...]
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    cleanup_scope: str = 'none'
    cleanup_confirmed: bool = False
    tree_control: str = 'BEST_EFFORT'


class HostProcessLauncherPort(Protocol):
    def launch(self, request: ProcessLaunchRequest, *,
               cancellation_token: CancellationToken,
               deadline: datetime | None,
               validate_launch: Callable[[], None]) -> ProcessReport: ...


def process_report_to_tool_result(report, audit, limits):
    """Pure typed result/legacy-view projection shared with compatibility adapters."""
    status = {'completed': ToolStatus.COMPLETED, 'cancelled': ToolStatus.CANCELLED,
              'timeout': ToolStatus.CANCELLED, 'outcome_unknown': ToolStatus.OUTCOME_UNKNOWN}.get(
                  report.outcome, ToolStatus.FAILED)
    text = report.stdout + report.stderr
    suffix = ''
    if report.error_code in ('PROCESS_TIMEOUT', 'PROCESS_CANCELLED', 'PROCESS_CLEANUP_UNKNOWN'):
        label = {'PROCESS_TIMEOUT': 'command timed out', 'PROCESS_CANCELLED': 'command cancelled',
                 'PROCESS_CLEANUP_UNKNOWN': 'process cleanup unknown'}[report.error_code]
        suffix = '\nError: ' + label + ('; outcome unknown.' if report.pid is not None else '.')
    elif report.pid is None:
        suffix = 'Error: ' + (report.error_code or 'PROCESS_LAUNCH_FAILED')
    elif report.exit_code:
        text = text.rstrip()
        suffix = '\n[exit code: ' + str(report.exit_code) + ']'
    truncated = report.stdout_truncated or report.stderr_truncated
    data = text.encode('utf-8')
    truncated |= len(data) + len(suffix.encode()) > limits.published_bytes
    if truncated:
        suffix = '\n... [output truncated]' + suffix
    suffix_data = suffix.encode()[:limits.published_bytes]
    text = data[:max(0, limits.published_bytes-len(suffix_data))].decode('utf-8', errors='ignore')
    text += suffix_data.decode('utf-8', errors='ignore')
    return ToolResult(status, EffectState.NONE if report.pid is None else EffectState.UNKNOWN,
        stdout=report.stdout, stderr=report.stderr, exit_code=report.exit_code,
        error=report.error_code, legacy_text=text,
        metadata={'processModel': 'HOST_UNISOLATED', 'pid': report.pid,
            'processOutcome': report.outcome, 'processStates': list(report.states),
            'cleanupScope': report.cleanup_scope, 'cleanupConfirmed': report.cleanup_confirmed,
            'treeControl': report.tree_control, 'truncated': truncated,
            'stdoutTruncated': report.stdout_truncated, 'stderrTruncated': report.stderr_truncated,
            'rawStreamsTruncated': report.stdout_truncated or report.stderr_truncated,
            'securityErrorCode': report.error_code, 'processAudit': list(audit), 'cached': False})
