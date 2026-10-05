"""S4 bounded host launcher. No sandbox and no retries, including cleanup failure."""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import time

from local_cli.core.process import ProcessLaunchRequest, ProcessReport
from local_cli.infrastructure.process_lifecycle import PipeReader, PosixGroup, WindowsJob


class _Capture:
    def __init__(self, limit):
        self.limit = limit
        self.data = bytearray()
        self.truncated = False

    def add(self, chunk):
        remaining = self.limit - len(self.data)
        self.data.extend(chunk[:remaining])
        self.truncated |= len(chunk) > remaining

    def text(self):
        # Incomplete UTF-8 at the cap is dropped. Replacement cannot expand past it.
        return bytes(self.data).decode('utf-8', errors='replace').encode('utf-8')[:self.limit].decode('utf-8', errors='ignore')


class HostProcessLauncher:
    """Native controls apply to our launch/capture and measured lifecycle only."""
    def __init__(self, *, popen=None, tree_factory=None):
        self._popen = popen or subprocess.Popen
        self._tree_factory = tree_factory or (WindowsJob if os.name == 'nt' else PosixGroup)

    def launch(self, request: ProcessLaunchRequest, *, cancellation_token,
               deadline, validate_launch):
        states = ['launch_not_started']
        def early(outcome, code):
            return ProcessReport(None, None, '', '', outcome, code, tuple(states))
        if cancellation_token.is_cancel_requested():
            return early('cancelled', 'PROCESS_CANCELLED')
        if deadline is not None and datetime.now(timezone.utc) >= deadline:
            return early('timeout', 'PROCESS_TIMEOUT')
        # Application validates exact request, claimed grant, revisions and liveness
        # at the last boundary. A refusal is not converted into a launched effect.
        validate_launch()
        if cancellation_token.is_cancel_requested():
            return early('cancelled', 'PROCESS_CANCELLED')
        if deadline is not None and datetime.now(timezone.utc) >= deadline:
            return early('timeout', 'PROCESS_TIMEOUT')
        try:
            proc = self._popen(request.argv, cwd=request.cwd, env=dict(request.environment),
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                close_fds=True, shell=False, bufsize=0,
                creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW)
                    if os.name == 'nt' else 0,
                start_new_session=os.name != 'nt')
        except FileNotFoundError:
            return early('unavailable', 'EXECUTABLE_NOT_FOUND') if not Path(request.argv[0]).is_file() else early(
                'failed', 'PROCESS_LAUNCH_FAILED')
        except OSError:
            return early('failed', 'PROCESS_LAUNCH_FAILED')
        states.append('running')
        stdout, stderr = _Capture(request.limits.stdout_bytes), _Capture(request.limits.stderr_bytes)
        tree = None
        readers = []
        stop = None
        cleanup_end = None
        root_exited = False
        capture_error = False
        cleanup_scope = 'root_only'
        clock_end = time.monotonic() + request.timeout_seconds
        try:
            tree = self._tree_factory(proc)
            if tree.available:
                cleanup_scope = tree.scope
            readers = [PipeReader(proc.stdout), PipeReader(proc.stderr)]
            while True:
                progressed = False
                for reader, capture in zip(readers, (stdout, stderr)):
                    chunk = reader.read()
                    capture.add(chunk)
                    progressed |= bool(chunk)
                code = proc.poll()
                if code is not None and not root_exited:
                    root_exited = True
                    states.append('root_exited')
                now = time.monotonic()
                if cleanup_end is None:
                    if cancellation_token.is_cancel_requested():
                        stop = 'cancel'
                        states.append('cancel_requested')
                    elif (now >= clock_end or (deadline is not None
                            and datetime.now(timezone.utc) >= deadline)):
                        stop = 'timeout'
                        states.append('timeout_requested')
                    if stop is not None or root_exited:
                        states.append('cleanup_attempted')
                        cleanup_end = now + request.limits.cleanup_seconds
                        # A root exiting does not imply descendants have stopped.
                        tree.terminate()
                        if proc.poll() is None:
                            proc.kill()
                if cleanup_end is not None:
                    root_exited = proc.poll() is not None
                    known_empty = tree.available and tree.active() == 0
                    if root_exited and all(r.eof for r in readers) and known_empty:
                        if 'root_exited' not in states:
                            states.append('root_exited')
                        states.append('cleanup_confirmed')
                        break
                    if now >= cleanup_end:
                        if root_exited and 'root_exited' not in states:
                            states.append('root_exited')
                        states.append('cleanup_unknown')
                        break
                if not progressed:
                    time.sleep(0.005)  # Poll cadence, not a product quota/grace default.
        except BaseException:
            capture_error = True
            states.append('cleanup_attempted')
            if tree is not None:
                try:
                    tree.terminate()
                except OSError:
                    pass
            if proc.poll() is None:
                try:
                    proc.kill()
                except OSError:
                    pass
            try:
                proc.wait(timeout=request.limits.cleanup_seconds)
            except (OSError, subprocess.TimeoutExpired):
                pass
            states.append('cleanup_unknown')
        finally:
            for stream in (proc.stdout, proc.stderr):
                if stream is not None:
                    stream.close()
            if tree is not None:
                tree.close()
            # Popen retains its Windows handle until GC; release our handle now.
            if os.name == 'nt' and hasattr(proc, '_handle'):
                proc._handle.Close()
        confirmed = 'cleanup_confirmed' in states and not capture_error
        if not confirmed:
            outcome, error = 'outcome_unknown', 'PROCESS_CLEANUP_UNKNOWN'
            states.append('outcome_unknown')
        elif stop is not None:
            # Effects already performed by an arbitrary command are unobserved,
            # even if all measured job/group members have terminated.
            outcome = 'outcome_unknown'
            error = 'PROCESS_CANCELLED' if stop == 'cancel' else 'PROCESS_TIMEOUT'
            states.append('outcome_unknown')
        else:
            outcome = 'completed' if proc.returncode == 0 else 'failed'
            error = None if outcome == 'completed' else 'PROCESS_EXIT_NONZERO'
        return ProcessReport(proc.pid, proc.returncode, stdout.text(), stderr.text(),
            outcome, error, tuple(states), stdout.truncated, stderr.truncated,
            cleanup_scope, confirmed)
