"""S4 process admission and minimal per-operation audit, without durable S7 policy."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from threading import BoundedSemaphore, RLock, Timer
import codecs
import time

from local_cli.core.process import HostProcessLauncherPort, ProcessLaunchRequest, ProcessLimits, ProcessReport


# Presentation limits only: these never change process execution/capture limits.
TOOL_OUTPUT_BYTES = 32 * 1024
TOOL_OUTPUT_INTERVAL = 0.1


class _OutputProgress:
    """Bound and redact real process output before any observer sees it."""
    def __init__(self, redactor, callback, limit):
        self.callback, self.limit = callback, min(TOOL_OUTPUT_BYTES, limit)
        self.decoders = {channel: codecs.getincrementaldecoder('utf-8')(errors='replace')
                         for channel in ('stdout', 'stderr')}
        self.scrubs = {channel: redactor.stream() for channel in self.decoders}
        self.pending = {channel: '' for channel in self.decoders}
        self.retained = 0
        self.truncated = False
        self.last_emit = None
        self.cut_published = False
        self._lock = RLock()
        self._timer = None
        self._closed = False

    def _retain(self, channel, text):
        raw = text.encode('utf-8')
        room = max(0, self.limit - self.retained)
        safe = raw[:room].decode('utf-8', errors='ignore')
        self.truncated |= len(raw) > room
        self.retained += len(safe.encode('utf-8'))
        self.pending[channel] += safe

    def feed(self, channel, chunk, truncated=False):
        with self._lock:
            if self._closed:
                return
            self.truncated |= truncated
            self._retain(channel, self.scrubs[channel].feed(self.decoders[channel].decode(chunk)))
            now = time.monotonic()
            if self.last_emit is None or now - self.last_emit >= TOOL_OUTPUT_INTERVAL:
                self.flush(now)
            elif self._timer is None and (any(self.pending.values()) or
                    (self.truncated and not self.cut_published)):
                self._timer = Timer(TOOL_OUTPUT_INTERVAL - (now - self.last_emit), self._flush_due)
                self._timer.daemon = True
                self._timer.start()

    def _flush_due(self):
        with self._lock:
            self._timer = None
            if not self._closed:
                self.flush()

    def flush(self, now=None):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        for channel in self.pending:
            text, self.pending[channel] = self.pending[channel], ''
            if text or (self.truncated and not self.cut_published):
                try:
                    self.callback(channel, text, self.truncated)
                except Exception:
                    pass
                self.cut_published |= self.truncated
        self.last_emit = time.monotonic() if now is None else now

    def finish(self):
        with self._lock:
            self._closed = True
            for channel in self.pending:
                self._retain(channel, self.scrubs[channel].feed(self.decoders[channel].decode(b'', final=True)))
                self._retain(channel, self.scrubs[channel].finish())
            self.flush()


class ProcessExecutionService:
    """Share this host-owned service with children; limits are not OS quotas."""
    def __init__(self, launcher: HostProcessLauncherPort, limits: ProcessLimits, *, redactor=None):
        self.launcher = launcher
        self.limits = limits
        from local_cli.application.secrets import SecretRedactor
        self.redactor = redactor or SecretRedactor()
        self._slots = BoundedSemaphore(limits.max_concurrent)

    def execute(self, request: ProcessLaunchRequest, *, cancellation_token,
                deadline, validate_launch, on_output=None):
        if request.limits != self.limits:
            raise ValueError('PROCESS_CONFIGURATION_MISMATCH')
        # No indefinite queue and no retry. The host can explicitly resubmit later.
        if not self._slots.acquire(blocking=False):
            return ProcessReport(None, None, '', '', 'unavailable',
                'PROCESS_CONCURRENCY_LIMIT', ('launch_not_started',)), ()
        records = []
        started = datetime.now(timezone.utc).isoformat()
        try:
            progress = (_OutputProgress(self.redactor, on_output, request.limits.published_bytes)
                        if on_output is not None else None)
            launch_options = dict(cancellation_token=cancellation_token,
                deadline=deadline, validate_launch=validate_launch)
            # Older injected ports remain supported without a new callback.
            if progress is not None and getattr(self.launcher, 'supports_output_progress', False) is True:
                launch_options['on_output'] = progress.feed
            try:
                report = self.launcher.launch(request, **launch_options)
            finally:
                if progress is not None:
                    progress.finish()
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
