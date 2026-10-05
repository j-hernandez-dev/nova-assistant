"""Real S7 Application/gates; explicit memory, process and HTTP fixture ports."""
from dataclasses import replace
from threading import Event, Thread
import json
import subprocess
import pytest

from local_cli.application.security_audit import SecurityAuditService, reconstruct_operation
from local_cli.application.secrets import SecretRedactor
from local_cli.application.interactions import ApprovalGate
from local_cli.application.tool_runtime import ToolRuntime, ToolRegistry
from local_cli.core.security_audit import AuditKind
from local_cli.core.contracts import ToolStatus, ToolResult, EffectState, EventKind
from local_cli.core.process import ProcessReport
from local_cli.core.network import HttpHop
from local_cli.tools.write_tool import WriteTool
from local_cli.tools.edit_tool import EditTool
from tests.security_v12.test_s2_policy import invocation
from tests.security_v12.test_s2_runtime import runtime, response
from tests.security_v12.test_s3_runtime import FakeBroker, FakePlan
from tests.security_v12.test_s5_runtime import runtime as network_runtime, fetch
from tests.security_v12.network_fixtures import ScriptedHTTPPort
from tests.security_v12.test_s7_contracts import FixtureAuditPort


def audit_fixture():
    port = FixtureAuditPort()
    return port, SecurityAuditService(port, redactor=SecretRedactor(source={}))


def kinds(port):
    return [r.kind for r in port.records]


def test_deny_reconstructable_without_fabricated_dispatch_or_grant(tmp_path):
    port, audit = audit_fixture()
    rt, exe, events = runtime(tmp_path, security_audit=audit)
    inv = invocation(tmp_path, arguments={'command': 'Format-Volume D:'})
    result = rt.execute(inv)
    assert result.status is ToolStatus.DENIED
    assert kinds(port) == [AuditKind.REQUEST, AuditKind.POLICY, AuditKind.TERMINAL]
    assert port.records[1].data['decision'] == 'DENY'
    assert reconstruct_operation(port.records)['outcome'] == 'denied'
    assert rt.execute(inv) is result and len(port.records) == 3
    exe.run.assert_not_called()
    assert sum(e[0] is EventKind.TOOL_FAILED for e in events) == 1


@pytest.mark.parametrize('approved', [True, False])
def test_live_approval_correlates_human_actor_digest_grant_terminal(tmp_path, approved):
    port, audit = audit_fixture()
    pending, ready = [], Event()
    gate = ApprovalGate(on_required=lambda r: (pending.append(r), ready.set()))
    actor = gate.register_actor('desktop_host', lambda: True)
    rt, exe, events = runtime(tmp_path, gate=gate, security_audit=audit)
    inv = invocation(tmp_path, arguments={'command': 'Remove-Item build -Recurse'})
    results = []
    worker = Thread(target=lambda: results.append(rt.execute(inv)), daemon=True)
    worker.start()
    try:
        assert ready.wait(2)
        required = next(r for r in port.records if r.kind is AuditKind.APPROVAL_REQUIRED)
        assert required.data['approvalId'] == pending[0].approval_id
        assert required.data['actor'] is None
        gate.resolve(**{**response(pending[0], actor), 'approved': approved})
        worker.join(2); assert not worker.is_alive()
        resolved = next(r for r in port.records if r.kind is AuditKind.APPROVAL_RESOLVED)
        assert resolved.data['actor'] == 'desktop_host'
        assert resolved.data['approvalStatus'] == ('approved' if approved else 'denied')
        assert required.data['requestDigest'] == resolved.data['requestDigest']
        assert reconstruct_operation(port.records)['completeObservedLifecycle']
        grants = [r for r in port.records if r.kind is AuditKind.GRANT]
        assert bool(grants) is approved
        if approved:
            assert grants[0].data['requestDigest'] == required.data['requestDigest']
            exe.run.assert_called_once()
        else:
            exe.run.assert_not_called()
        count = len(port.records)
        assert rt.execute(inv) is results[0] and len(port.records) == count
        assert sum(e[0] in (EventKind.TOOL_COMPLETED, EventKind.TOOL_FAILED) for e in events) == 1
    finally:
        inv.context.cancellation_token.request(); worker.join(2)


def test_pending_cancel_records_actual_resolution_without_human_actor(tmp_path):
    port, audit = audit_fixture()
    ready = Event()
    gate = ApprovalGate(on_required=lambda _: ready.set())
    rt, exe, _ = runtime(tmp_path, gate=gate, security_audit=audit)
    inv = invocation(tmp_path, arguments={'command': 'mystery.exe'})
    results = []
    worker = Thread(target=lambda: results.append(rt.execute(inv)), daemon=True)
    worker.start()
    try:
        assert ready.wait(2)
        inv.context.cancellation_token.request(); worker.join(2)
        assert results[0].status is ToolStatus.CANCELLED
        resolved = next(r for r in port.records if r.kind is AuditKind.APPROVAL_RESOLVED)
        assert resolved.data['approvalStatus'] == 'cancelled' and resolved.data['actor'] is None
        assert AuditKind.DISPATCH not in kinds(port)
        exe.run.assert_not_called()
    finally:
        inv.context.cancellation_token.request(); worker.join(2)


@pytest.mark.parametrize('outcome,states,error', [
    ('completed', ('running', 'root_exited'), None),
    ('timeout', ('running', 'timeout_requested', 'root_exited'), 'PROCESS_TIMEOUT'),
    ('cancelled', ('running', 'cancel_requested', 'root_exited'), 'PROCESS_CANCELLED'),
    ('outcome_unknown', ('running', 'cleanup_unknown'), 'PROCESS_CLEANUP_UNKNOWN'),
])
def test_observed_process_launch_terminal_has_no_invented_file_effects(tmp_path, outcome, states, error):
    port, audit = audit_fixture()
    rt, exe, events = runtime(tmp_path, security_audit=audit)
    class Launcher:
        def launch(self, request, **kwargs):
            kwargs['validate_launch']()
            return ProcessReport(123, 0, 'fixture output', '', outcome, error, states)
    rt._process_service.launcher = Launcher()
    inv = invocation(tmp_path)
    result = rt.execute(inv)
    process = [r for r in port.records if r.kind is AuditKind.PROCESS]
    assert [r.data['action'] for r in process] == ['process_launch', 'process_terminal']
    assert all(r.data['pid'] == 123 for r in process)
    assert process[0].data['executable'].endswith('fake_pwsh.exe')
    assert process[-1].data['processOutcome'] == outcome
    terminal = port.records[-1]
    assert terminal.data['outcome'] == result.status.value
    assert terminal.data['effectState'] == 'unknown'
    assert terminal.data['timeoutRequested'] is ('timeout_requested' in states)
    assert all('internal_process_effects' in r.data['observationScope'] for r in process)
    assert AuditKind.FILESYSTEM not in kinds(port)
    assert sum(e[0] in (EventKind.TOOL_COMPLETED, EventKind.TOOL_FAILED) for e in events) == 1
    count = len(port.records); assert rt.execute(inv) is result
    assert len(port.records) == count


def test_missing_executable_records_no_successful_launch(tmp_path):
    port, audit = audit_fixture()
    rt, exe, _ = runtime(tmp_path, security_audit=audit)
    exe.run.side_effect = FileNotFoundError('fixture')
    rt.execute(invocation(tmp_path))
    process = [r for r in port.records if r.kind is AuditKind.PROCESS]
    assert len(process) == 1 and process[0].data['action'] == 'process_terminal'
    assert process[0].data['pid'] is None
    assert port.records[-1].data['effectState'] == 'none'


@pytest.mark.parametrize('name', ['write', 'edit'])
def test_mediated_fs_provenance_observes_hashes_without_extra_read(tmp_path, name):
    port, audit = audit_fixture()
    class Plan(FakePlan):
        def execute(self, guard):
            guard(); self.broker.effects.append(self.inv.name)
            return ToolResult(ToolStatus.COMPLETED, EffectState.APPLIED, legacy_text='done',
                metadata={'filesystemAfterHash': 'after-hash-fixture', 'filesystemObjectIdentity': 'after-object',
                    **({'filesystemBeforeHash': 'before-hash-fixture'} if name == 'edit' else {})})
    class Broker(FakeBroker):
        def prepare(self, root, inv):
            plan = Plan(self, root, inv); self.plans.append(plan); return plan
    broker, events = Broker(), []
    tool = (WriteTool if name == 'write' else EditTool)(cwd=tmp_path)
    rt = ToolRuntime(ToolRegistry([tool]), filesystem_broker=broker,
        security_audit=audit, publish=events.append)
    args = {'file_path': 'a.txt', **({'content': 'body-not-for-audit'} if name == 'write'
        else {'old_text': 'old-not-for-audit', 'new_text': 'new-not-for-audit'})}
    result = rt.execute(invocation(tmp_path, name, args))
    assert result.status is ToolStatus.COMPLETED
    observation = next(r for r in port.records if r.kind is AuditKind.FILESYSTEM)
    assert observation.data['action'] == 'modify'
    assert observation.data['beforeObjectIdentity'] == 'file-1'
    assert observation.data['afterObjectIdentity'] == 'after-object'
    assert observation.data['afterHash'] == 'after-hash-fixture'
    assert observation.data['beforeHash'] == ('before-hash-fixture' if name == 'edit' else None)
    assert 'not-for-audit' not in json.dumps([r.to_dict() for r in port.records])
    grant = next(r for r in port.records if r.kind is AuditKind.GRANT)
    perms = {c['permission'] for c in grant.data['permissions']}
    assert ('filesystem.read' in perms) is (name == 'edit')
    assert broker.effects == [name] and broker.plans[0].closed


def test_network_redirect_provenance_drops_unknown_query_values(tmp_path):
    port, audit = audit_fixture()
    http = ScriptedHTTPPort([HttpHop(302, '', 'https://second.test/b?token=not-registered-456', b''),
                            HttpHop(200, 'text/plain', None, b'body-not-for-audit')])
    rt, _, _ = network_runtime(tmp_path, http, security_audit=audit)
    result = rt.execute(fetch(tmp_path, 'https://example.test/a?token=not-registered-123'))
    assert result.status is ToolStatus.COMPLETED
    observation = next(r for r in port.records if r.kind is AuditKind.NETWORK)
    assert observation.data['effectiveUrl'] == 'https://second.test/b'
    assert len(observation.data['hops']) == 2
    raw = json.dumps([r.to_dict() for r in port.records])
    assert 'not-registered' not in raw and 'body-not-for-audit' not in raw


def test_child_subject_parent_correlation_and_same_shared_redactor(tmp_path):
    port, audit = audit_fixture()
    root, _, _ = runtime(tmp_path, security_audit=audit)
    parent = root.delegation_for(invocation(tmp_path, operation_id='parent-operation').context)
    child = ToolRuntime(ToolRegistry([root.registry.tool('bash')], scope='sub_agent'),
        security_audit=audit, issuer=root._issuer, policy=root.policy,
        parent_grant=parent, process_service=root._process_service)
    inv = invocation(tmp_path, session_id='child-session', agent_id='child-agent')
    result = child.execute(inv)
    assert result.status is ToolStatus.COMPLETED
    assert audit.redactor is root.redactor is child.redactor
    child_records = port.read_operation('child-session', 'operation')
    assert all(r.origin == 'subagent_runtime' and r.agent_id == 'child-agent' for r in child_records)
    assert all(r.data['parentSessionId'] == 'session' and r.data['parentTurnId'] == 'turn' for r in child_records)
    grant = next(r for r in child_records if r.kind is AuditKind.GRANT)
    assert grant.data['parentGrantId'] == parent.grant_id
    raw = json.dumps([r.to_dict() for r in port.records])
    for forbidden in ('issuerId', 'ceilingFingerprint', 'authorityFingerprint', 'environment_intent', 'grantRequest'):
        assert forbidden not in raw


def test_known_secret_redaction_in_request_process_records_and_scope(tmp_path):
    port = FixtureAuditPort()
    audit = SecurityAuditService(port, redactor=SecretRedactor(source={'DUMMY_TOKEN': 'dummy-known-789'}))
    rt, exe, _ = runtime(tmp_path, security_audit=audit)
    exe.run.return_value = subprocess.CompletedProcess([], 0, 'dummy-known-789', '')
    result = rt.execute(invocation(tmp_path, arguments={'command': 'echo dummy-known-789'}))
    assert result.status is ToolStatus.COMPLETED
    raw = json.dumps([r.to_dict() for r in port.records])
    assert 'dummy-known-789' not in raw
    assert '[REDACTED]' in raw
    assert not any('stdout' in r.data or 'stderr' in r.data for r in port.records)


def test_baseexception_audited_once_no_unknown_effect_retry(tmp_path):
    port, audit = audit_fixture()
    rt, exe, events = runtime(tmp_path, security_audit=audit)
    exe.run.side_effect = KeyboardInterrupt()
    inv = invocation(tmp_path)
    with pytest.raises(KeyboardInterrupt):
        rt.execute(inv)
    result = rt.execute(inv)
    assert result.status is ToolStatus.OUTCOME_UNKNOWN
    assert port.records[-1].data['outcome'] == 'outcome_unknown'
    assert port.records[-1].data['retryAllowed'] is False
    assert sum(r.kind is AuditKind.TERMINAL for r in port.records) == 1
    assert sum(e[0] is EventKind.TOOL_FAILED for e in events) == 1
    exe.run.assert_called_once()


def test_direct_fixture_embedding_does_not_claim_durability(tmp_path):
    rt, _, _ = runtime(tmp_path)
    assert rt._security_audit is None
    assert rt.execute(invocation(tmp_path)).status is ToolStatus.COMPLETED


def test_application_cli_uses_common_audit_without_extra_terminals(tmp_path, monkeypatch):
    from local_cli.application.session import AgentSessionCoordinator
    from local_cli.application.events import EventBufferConfig
    from local_cli.interfaces.cli_application import CliApplicationClient
    from tests.test_nova_core_phase4_session import ScriptedProvider, start
    from local_cli.core.environment import EnvironmentSelection
    port = FixtureAuditPort()
    rt, exe, _ = runtime(tmp_path)
    call = {'role': 'assistant', 'content': '', 'tool_calls': [{'function': {
        'name': 'bash', 'arguments': {'command': 'echo dummy-project-pass-789'}}}]}
    app = AgentSessionCoordinator(provider=ScriptedProvider([call, 'done']), model='fixture',
        tool_factory=lambda _: [rt.registry.tool('bash')], security_audit_port=port,
        environment_selector=lambda _: EnvironmentSelection({'PROJECT_TOKEN': 'dummy-project-pass-789'}),
        event_config=EventBufferConfig())
    sid = start(app, tmp_path).session_id
    shown = []
    monkeypatch.setattr(CliApplicationClient, '_human_tty', staticmethod(lambda: True))
    cli = CliApplicationClient(app, sid, read=lambda _: 'yes', write=shown.append, write_error=shown.append)
    try:
        cli.submit_user_input('fixture')
        exe.run.assert_called_once()
        resolved = next(r for r in port.records if r.kind is AuditKind.APPROVAL_RESOLVED)
        assert resolved.data['actor'] == 'cli_tty'
        assert app.get_snapshot(sid).turns[0]['terminalCount'] == 1
        assert sum(r.kind is AuditKind.TERMINAL for r in port.records) == 1
        assert reconstruct_operation(port.records)['outcome'] == 'completed'
        raw = json.dumps([r.to_dict() for r in port.records])
        assert 'dummy-project-pass-789' not in raw
        assert app.security_audit is app._session.tool_runtime._security_audit
    finally:
        cli.close()


def test_actual_subagent_routes_tools_through_shared_audit(tmp_path):
    from local_cli.sub_agent import SubAgent
    from tests.test_nova_core_phase4_session import ScriptedProvider
    port, audit = audit_fixture()
    rt, exe, _ = runtime(tmp_path)
    call = {'role': 'assistant', 'content': '', 'tool_calls': [{'function': {
        'name': 'bash', 'arguments': {'command': 'echo child'}}}]}
    child = SubAgent(ScriptedProvider([call, 'done']), 'fixture', [rt.registry.tool('bash')],
        'task', cwd=tmp_path, environment={}, security_audit=audit, redactor=audit.redactor)
    result = child.run()
    assert result.status == 'success'
    exe.run.assert_called_once()
    assert port.records
    assert all(r.origin == 'subagent_runtime' and r.agent_id == child.agent_id for r in port.records)
    assert reconstruct_operation(port.records)['outcome'] == 'completed'


def test_subagent_lifecycle_records_have_real_operation_ids_and_no_fake_toolcall(tmp_path):
    port, audit = audit_fixture()
    context = invocation(tmp_path).context
    audit.agent(context, 'child-operation', 'child-agent', started=True)
    audit.agent(context, 'child-operation', 'child-agent', started=False, outcome='outcome_unknown')
    assert all(r.operation_id == 'child-operation' and r.origin == 'application' for r in port.records)
    assert all(r.tool_call_id is None for r in port.records)
    assert all(r.data['parentOperationId'] == 'operation' for r in port.records)
    assert reconstruct_operation(port.records)['outcome'] == 'outcome_unknown'


@pytest.mark.parametrize('background', [False, True])
def test_application_agent_callbacks_and_child_tools_share_one_audit(tmp_path, monkeypatch, background):
    from local_cli.application.session import AgentSessionCoordinator
    from local_cli.application.events import EventBufferConfig
    from local_cli.tools.agent_tool import AgentTool
    from local_cli.sub_agent import SubAgentRunner
    from tests.test_nova_core_phase4_session import ScriptedProvider, start, submit
    port = FixtureAuditPort()
    rt, exe, _ = runtime(tmp_path)
    shell = rt.registry.tool('bash')
    child_call = {'role': 'assistant', 'content': '', 'tool_calls': [{'function': {
        'name': 'bash', 'arguments': {'command': 'echo child'}}}]}
    child_provider = ScriptedProvider([child_call, 'child done'])
    runner = SubAgentRunner(max_workers=1)
    agent = AgentTool(runner=runner, provider=child_provider, model='fixture',
        sub_agent_tools=[shell], cwd=tmp_path)
    monkeypatch.setattr(agent, '_create_fresh_provider', lambda: child_provider)
    parent_call = {'role': 'assistant', 'content': '', 'tool_calls': [{'function': {
        'name': 'agent', 'arguments': {'description': 'fixture', 'prompt': 'child task',
                                     'run_in_background': background}}}]}
    app = AgentSessionCoordinator(provider=ScriptedProvider([parent_call, 'parent done']),
        model='fixture', tool_factory=lambda _: [shell, agent], security_audit_port=port,
        event_config=EventBufferConfig())
    try:
        sid = start(app, tmp_path).session_id
        receipt = submit(app, sid, 'delegate')
        assert app.wait_for_turn(receipt.created_ids['turnId'], 5)
        for child in app._session.agent_operations.values():
            assert child.done.wait(5)
        exe.run.assert_called_once()
        started = [r for r in port.records if r.kind is AuditKind.AGENT_STARTED]
        terminal = [r for r in port.records if r.kind is AuditKind.AGENT_TERMINAL]
        assert len(started) == len(terminal) == 1
        assert started[0].operation_id == terminal[0].operation_id
        assert started[0].agent_id == terminal[0].agent_id
        child_records = [r for r in port.records if r.tool == 'bash' and r.origin == 'subagent_runtime']
        assert child_records and all(r.data['parentSessionId'] == sid for r in child_records)
        assert all(r.data['parentTurnId'] == receipt.created_ids['turnId'] for r in child_records)
        assert all(r.agent_id == started[0].agent_id for r in child_records)
        assert reconstruct_operation(child_records)['outcome'] == 'completed'
        assert app.get_snapshot(sid).turns[0]['terminalCount'] == 1
        events = app._events._journal.read_after(0)
        assert sum(e.kind is EventKind.AGENT_COMPLETED for e in events) == 1
        assert not any(e.kind is EventKind.OPERATION_COMPLETED and e.operation_id == terminal[0].operation_id for e in events)
    finally:
        runner.shutdown()
