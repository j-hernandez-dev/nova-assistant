"""Common Application backed by real JSONL; effect adapters explicitly mocked."""
from dataclasses import replace
import json
import os
from threading import Event, Thread
import pytest

from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit
from local_cli.application.security_audit import SecurityAuditService, reconstruct_operation
from local_cli.application.secrets import SecretRedactor
from local_cli.application.tool_runtime import ToolRuntime, ToolRegistry
from local_cli.application.interactions import ApprovalGate
from local_cli.core.security_audit import AuditKind
from local_cli.core.process import ProcessReport
from local_cli.core.contracts import EffectState, ToolStatus, ToolResult, EventKind
from local_cli.tools.write_tool import WriteTool
from tests.security_v12.test_s2_runtime import runtime, response
from tests.security_v12.test_s2_policy import invocation
from tests.security_v12.test_s3_runtime import FakeBroker, FakePlan


def disk_audit(tmp_path):
    work = tmp_path/'work'; work.mkdir()
    disk = JsonlSecurityAudit(tmp_path/'state', workspace=work)
    audit = SecurityAuditService(disk, redactor=SecretRedactor(source={}))
    return work, disk, audit


@pytest.mark.parametrize('outcome,states', [
    ('completed', ('running','root_exited')),
    ('timeout', ('running','timeout_requested','root_exited')),
    ('cancelled', ('running','cancel_requested','root_exited')),
    ('outcome_unknown', ('running','cleanup_unknown')),
])
def test_durable_process_fixture_reconstructed_after_reopen(tmp_path, outcome, states):
    work, disk, audit = disk_audit(tmp_path)
    rt, _, events = runtime(work, security_audit=audit)
    class Launcher:
        calls = 0
        def launch(self, request, **kwargs):
            self.calls += 1
            # The dispatch record is visible before starting the mocked effect.
            assert AuditKind.DISPATCH in [r.kind for r in disk.read_operation('session','operation')]
            kwargs['validate_launch']()
            return ProcessReport(123, 0, 'dummy-output-not-audited', '', outcome,
                'PROCESS_CLEANUP_UNKNOWN' if outcome == 'outcome_unknown' else None, states)
    launch = Launcher(); rt._process_service.launcher = launch
    inv = invocation(work)
    try:
        actual = rt.execute(inv); assert rt.execute(inv) is actual
        assert launch.calls == 1
        disk.close()
        opened = JsonlSecurityAudit(disk.directory)
        records = opened.read_operation('session','operation')
        reconstructed = reconstruct_operation(records)
        assert reconstructed['outcome'] == actual.status.value
        assert reconstructed['effectState'] == actual.effect_state.value
        assert reconstructed['completeObservedLifecycle']
        assert not reconstructed['processInternalEffectsKnown']
        assert any(r.kind is AuditKind.PROCESS and r.data['pid'] == 123 for r in records)
        assert not any(r.kind is AuditKind.FILESYSTEM for r in records)
        assert 'dummy-output-not-audited' not in json.dumps(reconstructed)
        assert sum(e[0] in (EventKind.TOOL_COMPLETED,EventKind.TOOL_FAILED) for e in events) == 1
        opened.close()
    finally:
        rt.close(); disk.close()


def test_durable_deny_and_exact_human_approval(tmp_path):
    work, disk, audit = disk_audit(tmp_path)
    pending, ready = [], Event()
    gate = ApprovalGate(on_required=lambda r: (pending.append(r),ready.set()))
    actor = gate.register_actor('desktop_host',lambda:True)
    rt, exe, _ = runtime(work, gate=gate, security_audit=audit)
    denied = invocation(work,arguments={'command':'Format-Volume D:'})
    assert rt.execute(denied).status is ToolStatus.DENIED
    assert reconstruct_operation(disk.read_operation('session','operation'))['outcome'] == 'denied'
    inv = invocation(work,arguments={'command':'Remove-Item build -Recurse'})
    inv = replace(inv,operation_id='approved-operation',
                  context=replace(inv.context,operation_id='approved-operation'))
    output = []
    worker = Thread(target=lambda:output.append(rt.execute(inv)),daemon=True)
    worker.start()
    try:
        assert ready.wait(2)
        gate.resolve(**response(pending[0],actor))
        worker.join(5); assert not worker.is_alive()
        exe.run.assert_called_once()
        disk.close()
        reopened = JsonlSecurityAudit(disk.directory)
        rows = reopened.read_operation('session','approved-operation')
        required = next(r for r in rows if r.kind is AuditKind.APPROVAL_REQUIRED)
        resolved = next(r for r in rows if r.kind is AuditKind.APPROVAL_RESOLVED)
        grant = next(r for r in rows if r.kind is AuditKind.GRANT)
        assert required.data['requestDigest'] == resolved.data['requestDigest'] == grant.data['requestDigest']
        assert resolved.data['actor'] == 'desktop_host'
        assert reconstruct_operation(rows)['outcome'] == 'completed'
        assert not any(k in json.dumps([r.to_dict() for r in rows]) for k in ('bearer','issuerSecret','hostApprovalProof'))
        reopened.close()
    finally:
        inv.context.cancellation_token.request(); worker.join(5); rt.close(); disk.close()


@pytest.mark.parametrize('failure', ['none','before','after'])
def test_fs_effect_known_even_if_terminal_audit_lost(tmp_path, failure):
    work, disk, audit = disk_audit(tmp_path)
    class Plan(FakePlan):
        def execute(self, guard):
            guard(); self.broker.effects.append(self.inv.name)
            return ToolResult(ToolStatus.COMPLETED, EffectState.APPLIED, legacy_text='done',
                metadata={'filesystemAfterHash':'fixture-after-hash','filesystemObjectIdentity':'fixture-after-object'})
    class Broker(FakeBroker):
        def prepare(self, root, inv):
            plan = Plan(self,root,inv); self.plans.append(plan); return plan
    class Port:
        def append(self, row):
            if failure == 'before' or failure == 'after' and row.kind is AuditKind.TERMINAL:
                raise OSError('dummy-private-adapter-error')
            disk.append(row)
        def flush(self):
            disk.flush()
    audit.port = Port()
    broker = Broker(); events = []
    rt = ToolRuntime(ToolRegistry([WriteTool(cwd=work)]),filesystem_broker=broker,
                     security_audit=audit,publish=events.append)
    inv = invocation(work,'write',{'file_path':'fixture.txt','content':'dummy-body-not-audited'})
    try:
        result = rt.execute(inv)
        assert rt.execute(inv) is result
        assert len(broker.effects) == (0 if failure == 'before' else 1)
        assert result.status is (ToolStatus.DENIED if failure == 'before' else ToolStatus.COMPLETED)
        assert result.effect_state is (EffectState.NONE if failure == 'before' else EffectState.APPLIED)
        assert result.metadata['securityAudit']['gap'] is (failure != 'none')
        disk.close()
        opened = JsonlSecurityAudit(disk.directory)
        records = opened.read_operation('session','operation')
        reconstructed = reconstruct_operation(records)
        if failure == 'none':
            assert reconstructed['outcome'] == 'completed'
            assert reconstructed['effectState'] == 'applied'
            fs = next(r for r in records if r.kind is AuditKind.FILESYSTEM)
            assert fs.data['afterHash'] == 'fixture-after-hash'
        else:
            assert reconstructed['outcome'] == 'not_observed'
        assert 'dummy-body-not-audited' not in json.dumps(reconstructed)
        assert sum(e[0] in (EventKind.TOOL_COMPLETED,EventKind.TOOL_FAILED) for e in events) == 1
        opened.close()
    finally:
        rt.close(); disk.close()


def test_normal_cli_composition_activates_jsonl_outside_workspace(tmp_path):
    from local_cli.bootstrap_cli import create_cli_application
    from local_cli.application.providers import ProviderManager
    from local_cli.application.rag import RAGService
    from local_cli.config import Config
    from tests.test_nova_core_phase4_session import ScriptedProvider
    work = tmp_path/'work'; work.mkdir()
    rt, exe, _ = runtime(work)
    call = {'role':'assistant','content':'','tool_calls':[{'function':{'name':'bash','arguments':{'command':'echo audit'}}}]}
    provider = ScriptedProvider([call,'done'])
    config = Config(); config.model='fixture'
    console = create_cli_application(config=config, provider_manager=ProviderManager(provider,'fixture'),
        tools=[rt.registry.tool('bash')],workspace=work,base_messages=[{'role':'system','content':'fixture'}],
        persistence=None,rag_service=RAGService(None),write=lambda _:None)
    disk = console.application.security_audit.port
    try:
        assert isinstance(disk,JsonlSecurityAudit)
        assert not disk.directory.resolve().is_relative_to(work)
        console.submit_user_input('test')
        exe.run.assert_called_once()
        operation = next(iter(console.application._session.turns[0].tool_operations))
        records = disk.read_operation(console.session_id,operation)
        assert reconstruct_operation(records)['outcome'] == 'completed'
        assert console.snapshot().services['securityAudit']['deliveryFailures'] == 0
    finally:
        console.close(); disk.close(); rt.close()


def test_normal_desktop_backend_composition_uses_same_durable_backend(tmp_path,monkeypatch):
    from tests.test_server import _make_server
    from tests.test_nova_core_phase4_session import ScriptedProvider
    from tests.test_nova_core_phase11_adapter import _wait_for
    work = tmp_path/'work'; work.mkdir()
    rt, exe, _ = runtime(work)
    call = {'role':'assistant','content':'','tool_calls':[{'function':{'name':'bash','arguments':{'command':'echo audit'}}}]}
    server = _make_server(ScriptedProvider([call,'done']),[rt.registry.tool('bash')])
    server._cwd = work
    sent = []; monkeypatch.setattr('local_cli.server._send',sent.append)
    server._compose_test_application()
    disk = server._application.security_audit.port
    try:
        assert isinstance(disk,JsonlSecurityAudit)
        server._app_adapter.start()
        server._app_adapter.handle({'id':1,'type':'chat','content':'test'})
        _wait_for(sent,'done',request_id=1)
        exe.run.assert_called_once()
        operation = next(iter(server._application._session.turns[0].tool_operations))
        rows = disk.read_operation(server._app_adapter.session_id,operation)
        assert reconstruct_operation(rows)['outcome'] == 'completed'
        assert not disk.directory.resolve().is_relative_to(work)
    finally:
        server._app_adapter.close(); disk.close(); rt.close()


def test_network_redirect_provenance_reopens_without_query_or_body(tmp_path):
    from tests.security_v12.test_s5_runtime import runtime as web_runtime, fetch
    from tests.security_v12.network_fixtures import ScriptedHTTPPort
    from local_cli.core.network import HttpHop
    work,disk,audit = disk_audit(tmp_path)
    http = ScriptedHTTPPort([HttpHop(302,'','https://next.test/final?unknown-secret=abc',b''),
                             HttpHop(200,'text/plain',None,b'dummy-body-private')])
    rt,_,_ = web_runtime(work,http,security_audit=audit)
    inv = fetch(work,'https://example.test/start?unknown-secret=abc')
    try:
        result = rt.execute(inv); assert result.status is ToolStatus.COMPLETED
        disk.close(); opened = JsonlSecurityAudit(disk.directory)
        rows = opened.read_operation('session','operation')
        network = next(r for r in rows if r.kind is AuditKind.NETWORK)
        assert network.data['effectiveUrl'] == 'https://next.test/final'
        assert len(http.gets) == 2 and reconstruct_operation(rows)['outcome'] == 'completed'
        assert all(s not in json.dumps([r.to_dict() for r in rows]) for s in ('unknown-secret','dummy-body-private'))
        opened.close()
    finally:
        rt.close(); disk.close()


def test_actual_subagent_common_runtime_persists_subject(tmp_path):
    from local_cli.sub_agent import SubAgent
    from tests.test_nova_core_phase4_session import ScriptedProvider
    work,disk,audit = disk_audit(tmp_path)
    rt,exe,_ = runtime(work)
    call = {'role':'assistant','content':'','tool_calls':[{'function':{'name':'bash','arguments':{'command':'echo child'}}}]}
    child = SubAgent(ScriptedProvider([call,'done']),'fixture',[rt.registry.tool('bash')],
        'dummy-child-task-not-audited',cwd=work,environment={},security_audit=audit,redactor=audit.redactor)
    try:
        assert child.run().status == 'success'
        exe.run.assert_called_once(); disk.close()
        # Strict validated rows are located by subject; no in-memory audit cache.
        from local_cli.core.security_audit import SecurityAuditRecord
        raw = [SecurityAuditRecord.from_dict(json.loads(line)) for p in disk.directory.glob('*.closed.jsonl')
               for line in p.read_text(encoding='utf-8').splitlines()[1:]]
        subject = raw[0]
        opened = JsonlSecurityAudit(disk.directory)
        rows = opened.read_operation(subject.session_id,subject.operation_id)
        assert all(r.agent_id == child.agent_id and r.origin == 'subagent_runtime' for r in rows)
        assert reconstruct_operation(rows)['outcome'] == 'completed'
        assert 'dummy-child-task-not-audited' not in json.dumps([r.to_dict() for r in rows])
        opened.close()
    finally:
        rt.close(); disk.close()


def test_cli_gap_warning_visible_and_core_outcome_unchanged(tmp_path):
    from local_cli.application.session import AgentSessionCoordinator
    from local_cli.interfaces.cli_application import CliApplicationClient
    from local_cli.application.events import EventBufferConfig
    from tests.test_nova_core_phase4_session import ScriptedProvider,start
    from tests.security_v12.test_s7_contracts import FixtureAuditPort
    class Port(FixtureAuditPort):
        def append(self,row):
            if row.kind is AuditKind.TERMINAL:
                raise OSError()
            super().append(row)
    rt,exe,_ = runtime(tmp_path)
    call = {'role':'assistant','content':'','tool_calls':[{'function':{'name':'bash','arguments':{'command':'echo audit'}}}]}
    app = AgentSessionCoordinator(provider=ScriptedProvider([call,'done']),model='fixture',
        tool_factory=lambda _:[rt.registry.tool('bash')],security_audit_port=Port(),event_config=EventBufferConfig())
    sid = start(app,tmp_path).session_id
    warnings = []; cli = CliApplicationClient(app,sid,write=lambda _:None,write_error=warnings.append)
    try:
        cli.submit_user_input('run')
        assert 'SECURITY_AUDIT_DELIVERY_FAILED' in ''.join(warnings)
        assert app.get_snapshot(sid).turns[0]['status'] == 'completed'
        assert app.get_snapshot(sid).turns[0]['terminalCount'] == 1
        exe.run.assert_called_once()
    finally:
        cli.close(); rt.close()


def test_start_subagent_audit_failure_is_typed_denial_no_child_submission(tmp_path):
    from unittest.mock import Mock
    from local_cli.application.session import AgentSessionCoordinator
    from local_cli.application.commands import ApplicationCommand,CommandKind
    from local_cli.core.contracts import new_command_id
    from local_cli.application.events import EventBufferConfig
    from tests.test_nova_core_phase4_session import ScriptedProvider,start,submit
    from tests.security_v12.test_s7_contracts import FixtureAuditPort
    from local_cli.application.providers import ProviderManager
    class Port(FixtureAuditPort):
        def flush(self):
            raise OSError()
    entered,release = Event(),Event()
    def run(*args,**kwargs):
        entered.set(); assert release.wait(5); return 'done'
    runner = Mock()
    shell_runtime,_,_ = runtime(tmp_path)
    shell = shell_runtime.registry.tool('bash')
    provider = ScriptedProvider([])
    manager = ProviderManager(provider,'fixture',clone_factory=lambda _:lambda:ScriptedProvider([]))
    app = AgentSessionCoordinator(provider=provider,model='fixture',tool_factory=lambda _:[shell],provider_manager=manager,
        run_agent_fn=run,security_audit_port=Port(),event_config=EventBufferConfig(),
        provider_factory=lambda _:ScriptedProvider([]),
        sub_agent_runner=runner,sub_agent_tool_factory=lambda _:[shell])
    sid = start(app,tmp_path).session_id
    parent = submit(app,sid,'wait')
    try:
        assert entered.wait(2)
        child = app.handle(ApplicationCommand(new_command_id(),CommandKind.START_SUB_AGENT,
            {'parentTurnId':parent.created_ids['turnId'],'task':'child','mode':'default'},session_id=sid))
        assert not child.accepted and child.error.code == 'SECURITY_AUDIT_PRE_EFFECT_FAILED'
        runner.submit.assert_not_called()
        assert not app._session.agent_operations
    finally:
        release.set(); assert app.wait_for_turn(parent.created_ids['turnId'],5)
        shell_runtime.close()
