"""V4 actual ToolRuntime + durable JSONL. No model quality claims."""
from dataclasses import replace
import platform
import pytest
from local_cli.application.tool_runtime import ToolRuntime, ToolRegistry
from local_cli.application.turn_effects import resolve_turn_effects, TurnEffectConstraints
from local_cli.application.security_audit import SecurityAuditService, reconstruct_operation
from local_cli.application.secrets import SecretRedactor
from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit
from local_cli.core.contracts import ToolStatus, EffectState
from local_cli.core.security_audit import AuditKind, SecurityAuditRecord
from local_cli.tools.write_tool import WriteTool
from local_cli.tools.edit_tool import EditTool
from tests.security_v12.test_s2_policy import invocation


@pytest.mark.parametrize('tool', ['write', 'edit'])
@pytest.mark.parametrize('child', [False, True])
def test_turn_deny_durable_policy_no_gap_repeated_and_inherited(tmp_path, tool, child):
    work=tmp_path/'work';work.mkdir()
    target=work/'ledger.txt';target.write_text('synthetic ledger unchanged',encoding='utf-8')
    sentinel=tmp_path/'external';sentinel.write_text('external unchanged',encoding='utf-8')
    disk=JsonlSecurityAudit(tmp_path/'audit',workspace=work)
    audit=SecurityAuditService(disk,redactor=SecretRedactor(source={}))
    constraints=resolve_turn_effects('Do not modify any files.')
    runtime=ToolRuntime(ToolRegistry([WriteTool(cwd=work),EditTool(cwd=work)]),
        security_audit=audit,turn_effect_constraints=constraints if child else None)
    args={'file_path':'ledger.txt','content':'forbidden replacement'} if tool=='write' else {
        'file_path':'ledger.txt','old_string':'unchanged','new_string':'forbidden'}
    inv=invocation(work,tool,args,agent_id='child-v4' if child else None)
    try:
        runtime.install_authority(work,inv.context.session_id)
        before=runtime._issuer.ceiling.fingerprint
        runtime.bind_turn_effects(inv.context.session_id,inv.context.turn_id,
            TurnEffectConstraints() if child else constraints)
        for number in range(2):
            ctx=replace(inv.context,operation_id=f'denied-{number}')
            current=replace(inv,operation_id=ctx.operation_id,context=ctx)
            result=runtime.execute(current)
            assert runtime.execute(current) is result
            assert result.status is ToolStatus.DENIED and result.effect_state is EffectState.NONE
            assert result.metadata['turnConstraintCode']=='TURN_FILESYSTEM_MUTATION_DENIED'
            assert not result.metadata['securityAudit']['gap']
            rows=disk.read_operation(ctx.session_id,ctx.operation_id)
            assert [r.kind for r in rows]==[AuditKind.REQUEST,AuditKind.POLICY,AuditKind.TERMINAL]
            policy=rows[1]
            assert policy.origin==('subagent_runtime' if child else 'agent_runtime')
            assert policy.data['decision']=='DENY'
            assert policy.data['reason']=='TURN_FILESYSTEM_MUTATION_DENIED'
            assert 'origin' not in policy.data
            assert SecurityAuditRecord.from_dict(policy.to_dict())==policy
            assert reconstruct_operation(rows)['effectState']=='none'
        assert not runtime._issuer._issued
        assert runtime._issuer.ceiling.fingerprint==before
        assert target.read_text(encoding='utf-8')=='synthetic ledger unchanged'
        assert sentinel.read_text(encoding='utf-8')=='external unchanged'
        assert audit.health()['deliveryFailures']==0
        disk.close()
        reopened=JsonlSecurityAudit(disk.directory)
        try:
            for number in range(2):
                rows=reopened.read_operation(inv.context.session_id,f'denied-{number}')
                assert reconstruct_operation(rows)['completeObservedLifecycle']
                assert reconstruct_operation(rows)['outcome']=='denied'
        finally:reopened.close()
    finally:runtime.close();disk.close()


def test_authorized_real_write_durable_normal_audit(tmp_path):
    work=tmp_path/'work';work.mkdir()
    disk=JsonlSecurityAudit(tmp_path/'audit',workspace=work)
    audit=SecurityAuditService(disk,redactor=SecretRedactor(source={}))
    runtime=ToolRuntime(ToolRegistry([WriteTool(cwd=work)]),security_audit=audit)
    inv=invocation(work,'write',{'file_path':'verified.txt','content':'synthetic permission preserved'})
    try:
        runtime.install_authority(work,inv.context.session_id)
        runtime.bind_turn_effects(inv.context.session_id,inv.context.turn_id,
            resolve_turn_effects('Create verified.txt.'))
        before=runtime._issuer.ceiling.fingerprint
        result=runtime.execute(inv)
        assert runtime.execute(inv) is result
        assert runtime._issuer.ceiling.fingerprint==before
        if platform.system()=='Windows':
            assert result.status is ToolStatus.COMPLETED and result.effect_state is EffectState.APPLIED
            assert (work/'verified.txt').read_text(encoding='utf-8')=='synthetic permission preserved'
            assert not result.metadata['securityAudit']['gap']
            rows=disk.read_operation(inv.context.session_id,inv.operation_id)
            assert next(r for r in rows if r.kind is AuditKind.POLICY).data['decision']=='ALLOW'
            assert any(r.kind is AuditKind.GRANT for r in rows)
            assert any(r.kind is AuditKind.FILESYSTEM for r in rows)
            disk.close();reopened=JsonlSecurityAudit(disk.directory)
            try:
                actual=reconstruct_operation(reopened.read_operation(inv.context.session_id,inv.operation_id))
                assert actual['completeObservedLifecycle'] and actual['effectState']=='applied'
            finally:reopened.close()
        else:
            # S3 remains Windows/NTFS only. This is fail-closed coverage, not a skip
            # nor a claim that POSIX performed an authorized filesystem effect.
            assert result.metadata['securityErrorCode']=='FILESYSTEM_PLATFORM_UNSUPPORTED'
            assert result.effect_state is EffectState.NONE and not (work/'verified.txt').exists()
    finally:runtime.close();disk.close()
