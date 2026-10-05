"""S4 process admission and minimal per-operation audit, without durable S7 policy."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from threading import BoundedSemaphore

from local_cli.core.process import HostProcessLauncherPort, ProcessLaunchRequest, ProcessLimits, ProcessReport


class ProcessExecutionService:
    """Share this host-owned service with children; limits are not OS quotas."""
    def __init__(self, launcher: HostProcessLauncherPort, limits: ProcessLimits, *, redactor=None):
        self.launcher = launcher
        self.limits = limits
        from local_cli.application.secrets import SecretRedactor
        self.redactor = redactor or SecretRedactor()
        self._slots = BoundedSemaphore(limits.max_concurrent)

    def execute(self, request: ProcessLaunchRequest, *, cancellation_token,
                deadline, validate_launch):
        if request.limits != self.limits:
            raise ValueError('PROCESS_CONFIGURATION_MISMATCH')
        # No indefinite queue and no retry. The host can explicitly resubmit later.
        if not self._slots.acquire(blocking=False):
            return ProcessReport(None, None, '', '', 'unavailable',
                'PROCESS_CONCURRENCY_LIMIT', ('launch_not_started',)), ()
        records = []
        started = datetime.now(timezone.utc).isoformat()
        try:
            report = self.launcher.launch(request, cancellation_token=cancellation_token,
                deadline=deadline, validate_launch=validate_launch)
            # A compact per-operation tuple, not EventJournal or durable audit.
            # Environment values and bearer grant objects are never included.
            base = {**request.correlation, 'controlClass': 'HOST_UNISOLATED',
                'treeControl': 'BEST_EFFORT', 'cwd': request.cwd,
                'command': request.command, 'executable': request.argv[0]}
            if report.pid is not None:
                records.append({**base, 'kind': 'process_launch', 'timestamp': started,
                                'pid': report.pid})
            records.append({**base, 'kind': 'process_terminal',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                **asdict(report)})
            # Output belongs to ToolResult, not duplicated into audit.
            records[-1].pop('stdout'); records[-1].pop('stderr')
            from dataclasses import replace
            def retained(text, limit, truncated):
                safe = self.redactor.text(text, partial=truncated).encode('utf-8')
                return safe[:limit].decode('utf-8', errors='ignore'), truncated or len(safe) > limit
            stdout, out_cut = retained(report.stdout, request.limits.stdout_bytes, report.stdout_truncated)
            stderr, err_cut = retained(report.stderr, request.limits.stderr_bytes, report.stderr_truncated)
            report = replace(report, stdout=stdout, stderr=stderr,
                             stdout_truncated=out_cut, stderr_truncated=err_cut)
            safe_records = self.redactor.value(records)
            for raw, safe in zip(records, safe_records):
                for key in (*request.correlation.keys(), 'controlClass', 'treeControl', 'kind', 'timestamp',
                            'outcome', 'states', 'cleanup_scope', 'tree_control'):
                    if key in raw:
                        safe[key] = raw[key]
            return report, tuple(safe_records)
        finally:
            self._slots.release()
