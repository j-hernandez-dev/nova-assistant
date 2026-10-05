"""Real Application composition with mocked executors; no security host launches."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Event, Thread
from unittest.mock import Mock
import subprocess

import pytest

from local_cli.application.grants import GrantIssuer
from local_cli.application.interactions import ApprovalGate, InteractionError
from local_cli.application.tool_runtime import ToolRegistry, ToolRuntime
from local_cli.core.contracts import ToolStatus, EventKind
from local_cli.core.security import GrantLifetime, GrantRequest, AuthorityCeiling, Capability
from local_cli.shell_executor import ShellDescriptor
from local_cli.tools.bash_tool import BashTool
from local_cli.tools import create_tools
from tests.security_v12.test_s2_policy import invocation
from tests.security_v12.process_fixtures import bind_mock_shell


def runtime(tmp_path, *, gate=None, **kwargs):
    executor = Mock()
    executor.run.return_value = subprocess.CompletedProcess([], 0, 'ok', '')
    shell = BashTool(descriptor=ShellDescriptor('Windows', 'powershell',
        str(tmp_path/'fake_pwsh.exe'), '7'), executor=executor, environment={}, cwd=tmp_path,
        confirm=lambda _c: pytest.fail('legacy callback bypass'))
    bind_mock_shell(shell, executor)
    events = []
    rt = ToolRuntime(ToolRegistry([shell]), approval_gate=gate, publish=events.append, **kwargs)
    rt.install_authority(tmp_path, 'session')
    return rt, executor, events


def response(req, actor):
    return dict(session_id=req.session_id, approval_id=req.approval_id,
                tool_call_id=req.tool_call_id, request_digest=req.request_digest,
                cwd=req.cwd, policy_revision=req.policy_revision, approved=True, actor=actor)


def pending_runtime(tmp_path, **kwargs):
    requested, ready = [], Event()
    gate = ApprovalGate(on_required=lambda r: (requested.append(r), ready.set()))
    actor = gate.register_actor('desktop_host', lambda: True)
    rt, executor, events = runtime(tmp_path, gate=gate, **kwargs)
    inv = invocation(tmp_path, arguments={'command': 'Remove-Item build -Recurse'})
    results = []
    worker = Thread(target=lambda: results.append(rt.execute(inv)), daemon=True)
    worker.start()
    assert ready.wait(2)
    return rt, gate, actor, inv, requested[0], executor, events, results, worker


def test_required_approval_and_grant_share_the_full_digest_and_execute_once(tmp_path):
    rt, gate, actor, inv, req, exe, events, results, worker = pending_runtime(tmp_path)
    exe.run.assert_not_called()
    gate.resolve(**response(req, actor))
    worker.join(2)
    assert results[0].status is ToolStatus.COMPLETED
    assert results[0].metadata['requestDigest'] == req.request_digest
    assert results[0].metadata['controlClasses'] == ['APPLICATION_ENFORCED', 'HOST_UNISOLATED']
    assert results[0].metadata['grantId']
    assert rt.execute(inv) is results[0]
    exe.run.assert_called_once()
    assert [e[0] for e in events] == [EventKind.TOOL_REQUESTED, EventKind.TOOL_STARTED, EventKind.TOOL_COMPLETED]
    grant = next(iter(rt._issuer._issued.values())).grant
    from local_cli.core.security import SecurityError
    with pytest.raises(SecurityError, match='GRANT_CONSUMED'):
        rt._issuer.claim(grant, grant.request)


@pytest.mark.parametrize('mutation', ['arguments', 'cwd', 'environment', 'policy', 'ceiling', 'cancel'])
def test_changes_while_approval_pending_cannot_start_executor(tmp_path, mutation):
    rt, gate, actor, inv, req, exe, events, results, worker = pending_runtime(tmp_path)
    if mutation == 'arguments':
        with pytest.raises(TypeError):
            inv.arguments['command'] = 'echo changed'
        # Simulate a host-side replacement while the human dialog is open.
        object.__setattr__(inv, 'arguments', {'command': 'echo changed'})
    elif mutation == 'cwd':
        rt.registry.tool('bash').cwd = tmp_path/'elsewhere'
    elif mutation == 'environment':
        rt.registry.tool('bash').environment['NEW_DUMMY'] = 'dummy'
    elif mutation == 'policy':
        rt.update_policy_revision(2)
    elif mutation == 'ceiling':
        rt._issuer.replace_ceiling(replace(rt._issuer.ceiling, revision=2))
    else:
        inv.context.cancellation_token.request()
    try:
        with pytest.raises(InteractionError):
            gate.resolve(**response(req, actor))
    finally:
        worker.join(2)
        inv.context.cancellation_token.request()
        worker.join(2)
    assert results and results[0].status in (ToolStatus.DENIED, ToolStatus.CANCELLED)
    exe.run.assert_not_called()
    assert len([e for e in events if e[0] is EventKind.TOOL_FAILED]) == 1
    assert not any(e[0] is EventKind.TOOL_STARTED for e in events)


def test_renderer_marker_and_json_cannot_create_human_authority(tmp_path):
    rt, gate, actor, inv, req, exe, events, results, worker = pending_runtime(tmp_path)
    for fake in (None, 'desktop_host', object()):
        with pytest.raises(InteractionError, match='APPROVAL_ACTOR_INVALID'):
            gate.resolve(**response(req, fake))
    gate.resolve(**response(req, actor))
    worker.join(2)
    assert results[0].status is ToolStatus.COMPLETED


def test_yes_never_supplies_human_confirmation(tmp_path):
    from local_cli.cli import build_parser
    parser = build_parser()
    assert parser.parse_args(['--yes']).auto_approve is True
    assert 'required human security approvals are never skipped' in ' '.join(parser.format_help().split())
    rt, exe, events = runtime(tmp_path, auto_approve=True)
    result = rt.execute(invocation(tmp_path, arguments={'command': 'npm install'}))
    assert result.status is ToolStatus.DENIED
    assert result.metadata['securityErrorCode'] == 'APPROVAL_REQUIRED'
    exe.run.assert_not_called()


@pytest.mark.parametrize('command', ['Format-Volume D:', 'sudo echo ok'])
def test_yes_never_overrides_a_deny(tmp_path, command):
    rt, exe, _ = runtime(tmp_path, auto_approve=True)
    result = rt.execute(invocation(tmp_path, arguments={'command': command}))
    assert result.status is ToolStatus.DENIED
    exe.run.assert_not_called()


def test_deadline_before_launch_has_no_effect(tmp_path):
    rt, exe, _ = runtime(tmp_path)
    inv = invocation(tmp_path, deadline=datetime.now(timezone.utc)-timedelta(seconds=1))
    assert rt.execute(inv).status is ToolStatus.CANCELLED
    exe.run.assert_not_called()


def test_all_fs_and_fetch_tools_pass_policy_and_claim_before_adapter(tmp_path, monkeypatch):
    monkeypatch.setattr('local_cli.tools.shell_tool.detect_shell', lambda _: ShellDescriptor(
        'Windows', 'powershell', str(tmp_path/'fake_pwsh.exe'), '7'))
    tools = create_tools('server', confirm=lambda _: False, cwd=tmp_path, environment={})
    # S3 no longer executes legacy FS adapters. Keep this a port-mocked
    # policy/claim ordering test; real filesystem evidence lives in S3.
    from tests.security_v12.test_s3_runtime import FakeBroker
    from local_cli.application.network import NetworkFetchService
    from local_cli.network_config import DEFAULT_FETCH_LIMITS
    from tests.security_v12.network_fixtures import ScriptedHTTPPort
    broker = FakeBroker()
    http = ScriptedHTTPPort()
    rt = ToolRuntime(ToolRegistry(tools), filesystem_broker=broker,
                     network_service=NetworkFetchService(http, DEFAULT_FETCH_LIMITS))
    rt.install_authority(tmp_path, 'session')
    cases = [('read', {'file_path': 'a'}), ('write', {'file_path': 'a', 'content': 'ok'}),
             ('edit', {'file_path': 'a', 'old_string': 'old', 'new_string': 'new'}),
             ('glob', {'pattern': '*'}), ('grep', {'pattern': 'x'}),
             ('web_fetch', {'url': 'https://example.test/'})]
    observed = []
    original_claim = rt._issuer.claim
    def claim(g, r):
        observed.append(r.tool_name)
        return original_claim(g, r)
    monkeypatch.setattr(rt._issuer, 'claim', claim)
    for index, (name, args) in enumerate(cases):
        tool = rt.registry.tool(name)
        monkeypatch.setattr(tool, 'execute', lambda **_: pytest.fail('legacy FS/HTTP fallback'))
        inv = invocation(tmp_path, name, args)
        inv = replace(inv, operation_id=str(index), context=replace(inv.context, operation_id=str(index)))
        result = rt.execute(inv)
        assert result.status is ToolStatus.COMPLETED, result
    assert observed == [name for name, _ in cases]
    assert broker.effects == [name for name, _ in cases if name != 'web_fetch']
    assert len(http.gets) == 1


def test_child_attenuates_delegation_and_cannot_reuse_parent_approval(tmp_path):
    root, _, _ = runtime(tmp_path)
    ctx = invocation(tmp_path).context
    parent = root.delegation_for(ctx)
    child_exe = Mock()
    child_exe.run.return_value = subprocess.CompletedProcess([], 0, 'child', '')
    shell = BashTool(descriptor=root.registry.tool('bash').descriptor,
                     executor=child_exe, cwd=tmp_path, environment={})
    bind_mock_shell(shell, child_exe)
    child = ToolRuntime(ToolRegistry([shell], scope='sub_agent'), issuer=root._issuer,
                        policy=root.policy, parent_grant=parent)
    inv = invocation(tmp_path, session_id='child_session', agent_id='child')
    inv = replace(inv, operation_id='child_op', context=replace(inv.context, operation_id='child_op'))
    allowed = child.execute(inv)
    assert allowed.status is ToolStatus.COMPLETED
    grant = root._issuer._issued[allowed.metadata['grantId']].grant
    assert grant.request.parent_grant_id == parent.grant_id
    assert grant.request.subject.parent_session_id == 'session'
    risky = replace(inv, arguments={'command': 'npm install'}, operation_id='other',
                    context=replace(inv.context, operation_id='other'))
    assert child.execute(risky).status is ToolStatus.DENIED
    child_exe.run.assert_called_once()
    root._issuer.revoke(parent)
    revoked = replace(inv, operation_id='revoked', context=replace(inv.context, operation_id='revoked'))
    assert child.execute(revoked).status is ToolStatus.DENIED
    child_exe.run.assert_called_once()


def test_logical_external_fs_deny_never_calls_adapter(tmp_path, monkeypatch):
    from local_cli.tools.read_tool import ReadTool
    tool = ReadTool(cwd=tmp_path)
    adapter = Mock(return_value='should not run')
    monkeypatch.setattr(tool, 'execute', adapter)
    rt = ToolRuntime(ToolRegistry([tool]))
    result = rt.execute(invocation(tmp_path, 'read', {'file_path': str(tmp_path.parent/'outside')}))
    assert result.status is ToolStatus.DENIED
    assert result.metadata['securityErrorCode'] == 'RESOURCE_SCOPE_VIOLATION'
    adapter.assert_not_called()


@pytest.mark.parametrize('command,launches', [('echo child', 1), ('npm install', 0)])
def test_agent_tool_composes_actual_child_with_parent_grant(tmp_path, monkeypatch, command, launches):
    from local_cli.tools.agent_tool import AgentTool
    from local_cli.sub_agent import SubAgentRunner
    from tests.test_nova_core_phase4_session import ScriptedProvider
    exe = Mock()
    exe.run.return_value = subprocess.CompletedProcess([], 0, 'child fixture', '')
    shell = BashTool(descriptor=ShellDescriptor('Windows', 'powershell', str(tmp_path/'pwsh.exe'), '7'),
                     executor=exe, cwd=tmp_path, environment={})
    bind_mock_shell(shell, exe)
    provider = ScriptedProvider([{'role': 'assistant', 'content': '', 'tool_calls': [
        {'function': {'name': 'bash', 'arguments': {'command': command}}} ]}, 'done'])
    runner = SubAgentRunner(max_workers=1)
    agent = AgentTool(runner=runner, provider=provider, model='fixture',
                      sub_agent_tools=[shell], cwd=tmp_path)
    monkeypatch.setattr(agent, '_create_fresh_provider', lambda: provider)
    rt = ToolRuntime(ToolRegistry([shell, agent]))
    try:
        result = rt.execute(invocation(tmp_path, 'agent', {'description': 'fixture', 'prompt': 'child task'}))
        assert result.status is ToolStatus.COMPLETED
        assert exe.run.call_count == launches
        grants = [state.grant for state in rt._issuer._issued.values()]
        assert len(grants) == 1 + launches
        if launches:
            parent = next(g for g in grants if g.request.tool_name == 'agent')
            child = next(g for g in grants if g.request.tool_name == 'bash')
            assert child.request.parent_grant_id == parent.grant_id
            assert child.request.subject.session_id != parent.request.subject.session_id
            assert all(any(p.covers(c) for p in parent.request.capabilities) for c in child.request.capabilities)
    finally:
        runner.shutdown()
