"""S4 unit/contract/mock tests. Numeric values are fixtures, not product defaults."""
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from threading import Event, Thread
from unittest.mock import Mock
import subprocess
import os

import pytest

from local_cli.application.cancellation import CancellationController
from local_cli.application.process import ProcessExecutionService
from local_cli.core.process import ProcessLaunchRequest, ProcessLimits, ProcessReport
from local_cli.core.contracts import EventKind, ToolStatus
from local_cli.infrastructure.host_process import _Capture, HostProcessLauncher
from local_cli.infrastructure.process_environment import minimum_process_environment
from tests.security_v12.test_s2_runtime import runtime
from tests.security_v12.test_s2_policy import invocation
from local_cli.shell_executor import PowerShellExecutor


def limits(**changes):
    return replace(ProcessLimits(1024, 512, 1024, 10, 20, 2, 1), **changes)


def request(tmp_path, **changes):
    return replace(ProcessLaunchRequest('fixture', (str(tmp_path/'fixture.exe'),),
        str(tmp_path), {}, 10, limits()), **changes)


@pytest.mark.parametrize('name,value', [
    ('stdout_bytes', 0), ('stderr_bytes', True), ('published_bytes', -1),
    ('max_concurrent', 0), ('default_timeout', 21), ('max_timeout', float('inf')),
    ('cleanup_seconds', 0), ('default_timeout', float('nan')),
])
def test_invalid_explicit_limits(name, value):
    with pytest.raises(ValueError):
        limits(**{name: value})


def test_request_is_immutable_and_copies_host_environment(tmp_path):
    source = {'PATH': 'fixture'}
    req = request(tmp_path, environment=source)
    source['PATH'] = 'changed'
    assert req.environment['PATH'] == 'fixture'
    with pytest.raises(TypeError):
        req.environment['PATH'] = 'changed'
    with pytest.raises(FrozenInstanceError):
        req.command = 'changed'


@pytest.mark.parametrize('changes', [
    {'argv': ('relative.exe',)}, {'cwd': 'relative'},
    {'timeout_seconds': 21}, {'environment': {'BAD=NAME': 'value'}},
])
def test_invalid_launch_snapshot(tmp_path, changes):
    with pytest.raises(ValueError):
        request(tmp_path, **changes)


def test_capture_never_retains_full_large_output_or_expands_utf8_cap():
    capture = _Capture(17)
    for _ in range(100):
        capture.add(b'A'*16 + '€'.encode())
        assert len(capture.data) <= 17
    assert capture.truncated and len(capture.text().encode()) <= 17


@pytest.mark.parametrize('source', [
    {'PATH': 'fixture', 'OPENAI_API_KEY': 'dummy', 'NOVA_PROVIDER_API_KEY': 'dummy'},
    {'path': 'fixture', 'oPeNaI_aPi_KeY': 'dummy', 'NOVA_APPROVAL_HOST_KEY': 'dummy'},
])
def test_minimum_environment_has_no_implicit_inheritance_or_known_secrets(source):
    before = source.copy()
    result = minimum_process_environment(source, source.keys())
    assert result == {key: value for key, value in source.items() if key.casefold() == 'path'}
    assert source == before


def test_empty_allowlist_is_empty_even_with_arbitrary_host_values():
    assert minimum_process_environment({'FIXTURE_SECRET': 'dummy'}, ()) == {}


@pytest.mark.parametrize('reason', ['cancel', 'deadline'])
def test_prelaunch_cancel_timeout_has_no_effect(tmp_path, reason):
    token, popen = CancellationController(), Mock()
    if reason == 'cancel':
        token.request()
    deadline = datetime.now(timezone.utc)-timedelta(seconds=1) if reason == 'deadline' else None
    report = HostProcessLauncher(popen=popen).launch(request(tmp_path),
        cancellation_token=token, deadline=deadline, validate_launch=lambda: None)
    assert report.pid is None and report.states == ('launch_not_started',)
    assert report.outcome == ('cancelled' if reason == 'cancel' else 'timeout')
    popen.assert_not_called()


def test_last_boundary_refusal_cannot_start_process(tmp_path):
    popen = Mock()
    def refuse():
        raise ValueError('APPROVAL_STALE')
    with pytest.raises(ValueError, match='APPROVAL_STALE'):
        HostProcessLauncher(popen=popen).launch(request(tmp_path),
            cancellation_token=CancellationController(), deadline=None, validate_launch=refuse)
    popen.assert_not_called()


@pytest.mark.parametrize('mutation', ['command', 'cwd', 'environment', 'descriptor', 'policy', 'ceiling', 'revoke'])
def test_runtime_revalidates_after_tool_started_before_executor(tmp_path, mutation):
    rt, exe, events = runtime(tmp_path)
    inv = invocation(tmp_path)
    def publish(event):
        events.append(event)
        if event[0] is not EventKind.TOOL_STARTED:
            return
        tool = rt.registry.tool('bash')
        if mutation == 'command':
            object.__setattr__(inv, 'arguments', {'command': 'echo changed'})
        elif mutation == 'cwd':
            tool.cwd = tmp_path/'other'
        elif mutation == 'environment':
            tool.environment['FIXTURE'] = 'changed'
        elif mutation == 'descriptor':
            tool.descriptor = replace(tool.descriptor, executable=str(tmp_path/'other.exe'))
        elif mutation == 'policy':
            rt.update_policy_revision(2)
        elif mutation == 'ceiling':
            rt._issuer.replace_ceiling(replace(rt._issuer.ceiling, revision=2))
        else:
            rt._issuer.revoke(next(iter(rt._issuer._issued.values())).grant)
    rt._publish = publish
    result = rt.execute(inv)
    assert result.status is ToolStatus.DENIED
    assert result.effect_state.value == 'none'
    exe.run.assert_not_called()
    assert len([e for e in events if e[0] is EventKind.TOOL_FAILED]) == 1
    if mutation == 'command':
        with pytest.raises(ValueError, match='IDEMPOTENCY_CONFLICT'):
            rt.execute(inv)
    else:
        assert rt.execute(inv) is result


def test_shared_service_admission_and_release_without_retry(tmp_path):
    entered, release = Event(), Event()
    class Launcher:
        def launch(self, request, **kwargs):
            entered.set(); assert release.wait(2)
            return ProcessReport(123, 0, '', '', 'completed', None, ('root_exited',))
    service = ProcessExecutionService(Launcher(), limits())
    results = []
    req = request(tmp_path)
    kw = dict(cancellation_token=CancellationController(), deadline=None, validate_launch=lambda: None)
    worker = Thread(target=lambda: results.append(service.execute(req, **kw)))
    worker.start(); assert entered.wait(1)
    report, records = service.execute(req, **kw)
    assert report.error_code == 'PROCESS_CONCURRENCY_LIMIT' and records == ()
    release.set(); worker.join(2)
    assert results[0][0].outcome == 'completed'
    report, records = service.execute(req, **kw)
    assert report.outcome == 'completed'
    assert [r['kind'] for r in records] == ['process_launch', 'process_terminal']
    assert all('environment' not in r and 'stdout' not in r for r in records)


def test_runtime_uses_typed_launcher_and_no_retry_for_unknown_effect(tmp_path):
    launcher = Mock()
    launcher.launch.return_value = ProcessReport(123, 1, 'partial', '', 'outcome_unknown',
        'PROCESS_TIMEOUT', ('running', 'timeout_requested', 'root_exited', 'cleanup_confirmed', 'outcome_unknown'),
        cleanup_scope='assigned_job_members', cleanup_confirmed=True)
    rt, exe, events = runtime(tmp_path)
    tool = rt.registry.tool('bash')
    tool._executor = PowerShellExecutor(tool.descriptor)
    rt._process_service = ProcessExecutionService(launcher, limits())
    inv = invocation(tmp_path)
    result = rt.execute(inv)
    assert result.status is ToolStatus.OUTCOME_UNKNOWN
    assert result.metadata['pid'] == 123 and result.stdout == 'partial'
    assert result.metadata['processModel'] == 'HOST_UNISOLATED'
    assert result.metadata['treeControl'] == 'BEST_EFFORT'
    assert rt.execute(inv) is result and launcher.launch.call_count == 1
    exe.run.assert_not_called()
    assert [e[0] for e in events] == [EventKind.TOOL_REQUESTED, EventKind.TOOL_STARTED, EventKind.TOOL_FAILED]
    grant = next(iter(rt._issuer._issued.values())).grant
    assert grant.request.process_binding['limits']['stdout_bytes'] == 1024
    req = launcher.launch.call_args.args[0]
    assert req.command == inv.arguments['command'] and req.cwd == str(tmp_path)
    assert req.correlation['requestDigest'] == grant.request.request_digest


def test_process_binding_digest_and_deep_immutability(tmp_path):
    rt, _, _ = runtime(tmp_path)
    tool = rt.registry.tool('bash')
    tool._executor = PowerShellExecutor(tool.descriptor)
    rt._process_service = ProcessExecutionService(Mock(), limits())
    inv = invocation(tmp_path)
    from local_cli.core.security import GrantLifetime
    now = datetime.now(timezone.utc)
    original, _ = rt._request(inv, GrantLifetime(now, now+timedelta(seconds=30)))
    altered = replace(original, process_binding={**original.process_binding, 'timeout': 11})
    assert original.request_digest != altered.request_digest
    with pytest.raises(TypeError):
        original.process_binding['limits']['stdout_bytes'] = 99


def test_published_utf8_and_marker_stay_within_explicit_cap():
    from local_cli.application.tool_runtime import ToolRuntime
    report = ProcessReport(123, 7, '€'*300, 'tail', 'failed', 'PROCESS_EXIT_NONZERO',
                           ('root_exited',), stdout_truncated=True)
    result = ToolRuntime._process_result(report, (), limits(published_bytes=55))
    assert len(result.legacy_text.encode()) <= 55
    assert result.metadata['truncated'] and result.exit_code == 7


def test_real_platform_executor_descriptor_cannot_drift(tmp_path):
    rt, _, _ = runtime(tmp_path)
    tool = rt.registry.tool('bash')
    tool._executor = PowerShellExecutor(replace(tool.descriptor, executable=str(tmp_path/'different.exe')))
    result = rt.execute(invocation(tmp_path))
    assert result.status is ToolStatus.DENIED and result.metadata['securityErrorCode'] == 'REQUEST_MISMATCH'


def test_launcher_channels_are_explicit_no_elevation_or_retry(tmp_path):
    popen = Mock(side_effect=FileNotFoundError())
    report = HostProcessLauncher(popen=popen).launch(request(tmp_path),
        cancellation_token=CancellationController(), deadline=None, validate_launch=lambda: None)
    popen.assert_called_once()
    args, kwargs = popen.call_args
    assert args == (request(tmp_path).argv,)
    assert kwargs['stdin'] == subprocess.DEVNULL and kwargs['close_fds'] is True
    assert kwargs['shell'] is False and kwargs['cwd'] == str(tmp_path)
    assert kwargs['stdout'] == kwargs['stderr'] == subprocess.PIPE
    assert 'pass_fds' not in kwargs and 'startupinfo' not in kwargs
    if os.name == 'nt':
        assert kwargs['creationflags'] & subprocess.CREATE_NO_WINDOW
    assert report.pid is None and report.error_code == 'EXECUTABLE_NOT_FOUND'


def test_slot_is_released_when_final_authorization_refuses(tmp_path):
    launcher = Mock()
    launcher.launch.side_effect = ValueError('APPROVAL_STALE')
    service = ProcessExecutionService(launcher, limits())
    for _ in range(2):
        with pytest.raises(ValueError, match='APPROVAL_STALE'):
            service.execute(request(tmp_path), cancellation_token=CancellationController(),
                            deadline=None, validate_launch=lambda: None)
    assert launcher.launch.call_count == 2


def test_common_application_session_uses_injected_s4_service(tmp_path):
    from local_cli.application.session import AgentSessionCoordinator
    from local_cli.application.events import EventBufferConfig
    from local_cli.tools.shell_tool import ShellTool
    from local_cli.shell_executor import ShellDescriptor
    from tests.test_nova_core_phase4_session import ScriptedProvider, start, submit
    descriptor = ShellDescriptor('Windows', 'powershell', str(tmp_path/'fixture_pwsh.exe'), 'fixture')
    shell = ShellTool(descriptor=descriptor, cwd=tmp_path, environment={})
    launcher = Mock()
    launcher.launch.return_value = ProcessReport(123, 0, 'fixture-ok', '', 'completed', None,
        ('running', 'root_exited', 'cleanup_confirmed'), cleanup_scope='assigned_job_members', cleanup_confirmed=True)
    service = ProcessExecutionService(launcher, limits())
    call = {'role': 'assistant', 'content': '', 'tool_calls': [{
        'function': {'name': 'bash', 'arguments': {'command': 'echo fixture-ok'}}}]}
    app = AgentSessionCoordinator(provider=ScriptedProvider([call, 'done']), model='local',
        tool_factory=lambda cwd: [shell], process_service=service, event_config=EventBufferConfig())
    session_id = start(app, tmp_path).session_id
    receipt = submit(app, session_id, 'benign fixture')
    assert app.wait_for_turn(receipt.created_ids['turnId'], timeout=5)
    events = app.poll_events(app.subscribe_events(session_id, after_sequence=0))
    terminals = [e for e in events if e.kind in (EventKind.TOOL_COMPLETED, EventKind.TOOL_FAILED)]
    assert len(terminals) == 1 and terminals[0].kind is EventKind.TOOL_COMPLETED
    assert launcher.launch.call_count == 1 and app._session.tool_runtime._process_service is service


def test_approved_defaults_and_effective_environment_are_bound(tmp_path):
    from local_cli.process_config import DEFAULT_PROCESS_LIMITS, COMPATIBLE_ENVIRONMENT_NAMES
    from local_cli.core.security import GrantLifetime
    from local_cli.application.tool_runtime import ToolRuntime, ToolRegistry
    from local_cli.tools.shell_tool import ShellTool
    from local_cli.shell_executor import ShellDescriptor
    assert DEFAULT_PROCESS_LIMITS == ProcessLimits(102400, 102400, 102400, 120, 600, 5, 2)
    assert len(COMPATIBLE_ENVIRONMENT_NAMES) == 20
    env = {'PATH': 'fixture', 'USERPROFILE': str(tmp_path), 'APPDATA': str(tmp_path),
           'NOVA_PROVIDER_API_KEY': 'DUMMY', 'NOVA_GRANT_MATERIAL': 'DUMMY',
           'NODE_OPTIONS': 'DUMMY', 'PYTHONPATH': 'DUMMY', 'SSH_AUTH_SOCK': 'DUMMY'}
    shell = ShellTool(descriptor=ShellDescriptor('Windows', 'powershell', str(tmp_path/'pwsh.exe'), 'fixture'),
                      cwd=tmp_path, environment=env)
    rt = ToolRuntime(ToolRegistry([shell]))
    rt.install_authority(tmp_path, 'session')
    inv = invocation(tmp_path, environment=shell.environment, arguments={'command':'echo ok', 'timeout':999})
    now = datetime.now(timezone.utc)
    req, _ = rt._request(inv, GrantLifetime(now, now+timedelta(minutes=5)))
    assert dict(req.environment_intent) == {'PATH':'fixture', 'USERPROFILE':str(tmp_path), 'APPDATA':str(tmp_path)}
    assert req.process_binding['timeout'] == 600
    assert req.process_binding['limits']['max_concurrent'] == 2
    assert env['NOVA_PROVIDER_API_KEY'] == 'DUMMY'  # Host/provider mapping untouched.


def test_missing_service_cannot_fall_back_to_legacy_executor(tmp_path):
    rt, exe, _ = runtime(tmp_path)
    rt._process_service = None
    result = rt.execute(invocation(tmp_path))
    assert result.status is ToolStatus.DENIED
    assert result.metadata['securityErrorCode'] == 'PROCESS_LAUNCHER_UNAVAILABLE'
    exe.run.assert_not_called()


def test_process_timeout_not_capped_by_launch_grant_expiry(tmp_path):
    rt, _, _ = runtime(tmp_path)
    launcher = Mock()
    launcher.launch.return_value = ProcessReport(123, 0, '', '', 'completed', None, ('test_mock',))
    from local_cli.process_config import DEFAULT_PROCESS_LIMITS
    rt._process_service = ProcessExecutionService(launcher, DEFAULT_PROCESS_LIMITS)
    result = rt.execute(invocation(tmp_path, arguments={'command':'echo ok','timeout':600}))
    assert result.status is ToolStatus.COMPLETED
    req = launcher.launch.call_args.args[0]
    assert req.timeout_seconds == 600 and launcher.launch.call_args.kwargs['deadline'] is None
