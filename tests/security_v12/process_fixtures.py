"""Explicit S4 launcher-port mock for old tests that spy on an executor.run Mock.

Never imported by product code and never native process evidence.
"""
import subprocess

from local_cli.core.process import ProcessReport
from local_cli.infrastructure.host_process import _Capture
from local_cli.shell_executor import ShellExecutionCancelled


class MockProcessLauncher:
    def __init__(self, executor):
        self.executor = executor

    def launch(self, request, *, cancellation_token, deadline, validate_launch):
        validate_launch()
        try:
            result = self.executor.run(request.command, request.timeout_seconds, request.cwd,
                dict(request.environment), cancellation_token=cancellation_token, deadline=deadline)
        except ShellExecutionCancelled as exc:
            return ProcessReport(123 if exc.started else None, None, '', '',
                'outcome_unknown' if exc.started else 'cancelled', 'PROCESS_CANCELLED', ('test_mock',))
        except subprocess.TimeoutExpired:
            return ProcessReport(123, None, '', '', 'outcome_unknown', 'PROCESS_TIMEOUT', ('test_mock',))
        except OSError:
            return ProcessReport(None, None, '', '', 'failed', 'PROCESS_LAUNCH_FAILED', ('launch_not_started',))
        out, err = _Capture(request.limits.stdout_bytes), _Capture(request.limits.stderr_bytes)
        out.add((result.stdout or '').encode()); err.add((result.stderr or '').encode())
        return ProcessReport(123, result.returncode, out.text(), err.text(),
            'completed' if result.returncode == 0 else 'failed',
            None if result.returncode == 0 else 'PROCESS_EXIT_NONZERO',
            ('test_mock',), out.truncated, err.truncated, cleanup_scope='test_mock')


def bind_mock_shell(tool, executor):
    """Inject the port on one fixture tool only, not a production fallback."""
    tool.create_process_launcher = lambda: MockProcessLauncher(executor)
    return tool
