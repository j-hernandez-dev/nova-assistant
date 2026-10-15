"""Approved application lifetime is exact; temporary-command cleanup stays bounded."""
from threading import Event, Thread
from unittest.mock import Mock, patch

import pytest

from local_cli.application.interactions import ApprovalGate, InteractionError
from local_cli.core.contracts import EffectState, ToolStatus
from local_cli.core.process import process_report_to_tool_result
from local_cli.infrastructure.host_process import HostProcessLauncher
from tests.security_v12.test_s2_policy import invocation
from tests.security_v12.test_s2_runtime import runtime, response
from tests.security_v12.test_s4_contracts import request, limits
from local_cli.application.cancellation import CancellationController


@pytest.mark.parametrize('approved', [False, True])
def test_application_lifetime_requires_approval_and_exact_grant(tmp_path, approved):
    ready, requests = Event(), []
    gate = ApprovalGate(on_required=lambda req: (requests.append(req), ready.set()))
    actor = gate.register_actor('cli_tty', lambda: True)
    rt, exe, _ = runtime(tmp_path, gate=gate, auto_approve=True)
    # Even a simple query cannot opt into persistent lifetime without approval.
    inv = invocation(tmp_path, arguments={'command': 'Write-Output ready', 'keep_open': True})
    launched = []
    original = rt._process_service.launcher.launch
    def capture(req, **kwargs):
        launched.append(req)
        return original(req, **kwargs)
    rt._process_service.launcher.launch = capture
    results = []
    worker = Thread(target=lambda: results.append(rt.execute(inv)), daemon=True)
    worker.start()
    try:
        assert ready.wait(2)
        exe.run.assert_not_called()
        answer = response(requests[0], actor); answer['approved'] = approved
        gate.resolve(**answer)
        worker.join(2)
        assert not worker.is_alive()
        if approved:
            exe.run.assert_called_once()
            assert launched[0].keep_open is True
            grant = rt._issuer._issued[results[0].metadata['grantId']].grant
            assert grant.request.arguments['keep_open'] is True
            assert grant.request.process_binding['keep_open'] is True
            assert grant.request.request_digest == requests[0].request_digest
        else:
            assert results[0].status is ToolStatus.DENIED
            assert not launched and not rt._issuer._issued
    finally:
        inv.context.cancellation_token.request(); worker.join(2); rt.close()


def test_lifetime_cannot_change_while_approval_is_pending(tmp_path):
    ready, requests = Event(), []
    gate = ApprovalGate(on_required=lambda req: (requests.append(req), ready.set()))
    actor = gate.register_actor('cli_tty', lambda: True)
    rt, exe, _ = runtime(tmp_path, gate=gate)
    inv = invocation(tmp_path, arguments={'command': 'Start-Process fixture.exe', 'keep_open': False})
    worker = Thread(target=lambda: rt.execute(inv), daemon=True); worker.start()
    try:
        assert ready.wait(2)
        object.__setattr__(inv, 'arguments', {'command': 'Start-Process fixture.exe', 'keep_open': True})
        with pytest.raises(InteractionError): gate.resolve(**response(requests[0], actor))
        worker.join(2)
        exe.run.assert_not_called()
    finally:
        inv.context.cancellation_token.request(); worker.join(2); rt.close()


@pytest.mark.parametrize('mode', ['temporary', 'persistent', 'failed', 'cancelled'])
def test_only_successful_persistent_launch_releases_children(tmp_path, mode):
    proc = Mock(pid=123, returncode=1 if mode == 'failed' else 0)
    if mode == 'cancelled': proc.returncode = None
    proc.poll.side_effect = lambda: proc.returncode
    proc.kill.side_effect = lambda: setattr(proc, 'returncode', -1)
    tree = Mock(available=True, scope='assigned_job_members')
    tree.active.return_value = 0
    class Reader:
        eof = True
        def __init__(self, stream): self.eof = mode != 'persistent'
        def read(self): return b''
    token = CancellationController()
    if mode == 'cancelled':
        token.is_cancel_requested = Mock(side_effect=[False, False, True])
    req = request(tmp_path, keep_open=mode != 'temporary')
    with patch('local_cli.infrastructure.host_process.PipeReader', Reader):
        report = HostProcessLauncher(popen=Mock(return_value=proc), tree_factory=lambda p: tree).launch(
            req, cancellation_token=token, deadline=None, validate_launch=lambda: None)
    if mode == 'persistent':
        tree.terminate.assert_not_called()
        assert report.children_released and report.cleanup_scope == 'launcher_only_children_released'
        assert report.outcome == 'completed'
        projected = process_report_to_tool_result(report, (), limits())
        assert projected.effect_state is EffectState.UNKNOWN
        assert projected.metadata['applicationWindowVerified'] is False
        assert 'not been verified' in projected.legacy_text
    else:
        tree.terminate.assert_called_once()
        assert not report.children_released
        assert report.outcome == ('completed' if mode == 'temporary' else 'failed' if mode == 'failed' else 'outcome_unknown')
    tree.close.assert_called_once()
    proc.stdout.close.assert_called_once(); proc.stderr.close.assert_called_once()


@pytest.mark.parametrize('value', [1, 'true', None])
def test_application_lifetime_rejects_non_boolean_values(tmp_path, value):
    with pytest.raises(ValueError, match='keep_open'):
        request(tmp_path, keep_open=value)
    rt, exe, _ = runtime(tmp_path)
    try:
        result = rt.execute(invocation(tmp_path, arguments={'command': 'Write-Output ready', 'keep_open': value}))
        assert result.status is ToolStatus.FAILED
        assert result.effect_state is EffectState.NONE
        assert result.metadata['securityErrorCode'] == 'INVALID_TOOL_ARGUMENTS'
        exe.run.assert_not_called()
    finally: rt.close()


def test_cli_approval_explains_persistent_application_lifetime(tmp_path, monkeypatch):
    from local_cli.interfaces.cli_application import CliApplicationClient
    from tests.security_v12.test_s0_frontends import _cli_runtime, _invocation
    monkeypatch.setattr(CliApplicationClient, '_human_tty', staticmethod(lambda: True))
    prompts = []
    frontend = _cli_runtime(tmp_path, read=lambda prompt: (prompts.append(prompt), 'n')[1])
    try:
        result = frontend.runtime.execute(_invocation(tmp_path,
            arguments={'command': 'Start-Process fixture.exe', 'keep_open': True},
            session_id=frontend.session_id, turn_id=frontend.turn_id))
        assert result.status is ToolStatus.DENIED
        assert len(prompts) == 1 and 'keep them open' in prompts[0]
        assert 'Start-Process fixture.exe' in prompts[0]
        frontend.executor.run.assert_not_called()
    finally: frontend.client.close(); frontend.runtime.close()


@pytest.mark.parametrize('command', ['Start-Process powershell', 'Start-Process fixture.exe -Verb RunAs', 'Format-Volume D:'])
def test_persistent_lifetime_cannot_override_a_command_denial(tmp_path, command):
    rt, exe, _ = runtime(tmp_path, auto_approve=True)
    try:
        result = rt.execute(invocation(tmp_path, arguments={'command': command, 'keep_open': True}))
        assert result.status is ToolStatus.DENIED and result.effect_state is EffectState.NONE
        exe.run.assert_not_called()
        assert not rt._issuer._issued
    finally: rt.close()
