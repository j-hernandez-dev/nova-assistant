"""Native S8 attacks on OWNED temporary fixtures; approval actor is test-only."""
from threading import Event, Thread
import os
import pytest
from local_cli.application.interactions import ApprovalGate, InteractionError
from local_cli.application.tool_runtime import ToolRegistry, ToolRuntime
from local_cli.application.security_audit import SecurityAuditService, reconstruct_operation
from local_cli.application.secrets import SecretRedactor
from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit
from local_cli.tools.shell_tool import ShellTool
from local_cli.tools.read_tool import ReadTool
from local_cli.shell_executor import detect_shell
from local_cli.core.contracts import ToolStatus, EffectState, EventKind
from tests.security_v12.test_s2_policy import invocation
from tests.security_v12.test_s2_runtime import response

pytestmark=pytest.mark.skipif(os.name!='nt' or os.environ.get('NOVA_S4_HOST_REAL')!='1',
                             reason='S8 Windows private host opt-in')


def execute(work,state,command,approved):
    shell=ShellTool(descriptor=detect_shell('native'),cwd=work,environment=dict(os.environ))
    disk=JsonlSecurityAudit(state,workspace=work)
    audit=SecurityAuditService(disk,redactor=SecretRedactor(source={}))
    pending=[];ready=Event();events=[]
    gate=ApprovalGate(on_required=lambda r:(pending.append(r),ready.set()))
    actor=gate.register_actor('desktop_host',lambda:True) # NOT a native human dialog
    rt=ToolRuntime(ToolRegistry([shell,ReadTool(cwd=work)]),approval_gate=gate,
                   security_audit=audit,publish=events.append)
    inv=invocation(work,arguments={'command':command},environment=shell.environment)
    result=[];worker=Thread(target=lambda:result.append(rt.execute(inv)),daemon=True);worker.start()
    try:
        assert ready.wait(5),'Risk requires an exact approval, not ALLOW'
        with pytest.raises(InteractionError,match='APPROVAL_ACTOR_INVALID'):
            gate.resolve(**response(pending[0],'desktop_host'))
        assert not result and not any(e[0] is EventKind.TOOL_STARTED for e in events)
        gate.resolve(**{**response(pending[0],actor),'approved':approved})
        worker.join(20);assert result and not worker.is_alive()
        assert rt.execute(inv) is result[0]
        rows=disk.read_operation('session','operation')
        assert reconstruct_operation(rows)['outcome']==result[0].status.value
        assert sum(e[0] in (EventKind.TOOL_COMPLETED,EventKind.TOOL_FAILED) for e in events)==1
        return result[0],rt,rows,disk
    except BaseException:
        inv.context.cancellation_token.request();worker.join(10);rt.close();disk.close();raise


@pytest.mark.parametrize('approved',[False,True])
def test_native_destructive_fixture_requires_exact_consent_and_audits(tmp_path,approved,record_property):
    work=tmp_path/'workspace';work.mkdir()
    target=work/'owned_deletion_fixture';target.mkdir();(target/'sentinel.txt').write_text('owned fixture')
    # Explicit verified leaf within pytest's private root; never user/workspace root.
    assert target.resolve().parent==work.resolve() and target.name=='owned_deletion_fixture'
    command="Remove-Item -LiteralPath '"+str(target).replace("'","''")+"' -Recurse -Force"
    result,rt,rows,disk=execute(work,tmp_path/'audit',command,approved)
    try:
        assert target.exists() is (not approved)
        assert result.status is (ToolStatus.COMPLETED if approved else ToolStatus.DENIED)
        assert result.effect_state is (EffectState.UNKNOWN if approved else EffectState.NONE)
        assert bool(result.metadata.get('pid')) is approved
        assert result.metadata.get('processModel','HOST_UNISOLATED')=='HOST_UNISOLATED'
        assert not any(r.kind.value=='filesystem_observation' for r in rows),'No invented shell FS provenance'
        record_property('s8.approval_actor','in-process test host, not native human dialog')
        record_property('s8.fixture_deleted',approved)
    finally:rt.close();disk.close()


def test_native_shell_can_read_external_owned_fixture_while_s3_denies(tmp_path,record_property):
    work=tmp_path/'workspace';work.mkdir()
    outside=tmp_path/'external-owned.txt';outside.write_text('S8_EXTERNAL_PRIVATE_SENTINEL')
    command="Get-Content -LiteralPath '"+str(outside).replace("'","''")+"'"
    result,rt,rows,disk=execute(work,tmp_path/'audit',command,True)
    try:
        assert result.status is ToolStatus.COMPLETED and 'S8_EXTERNAL_PRIVATE_SENTINEL' in result.stdout
        assert result.metadata['processModel']=='HOST_UNISOLATED'
        inv=invocation(work,'read',{'file_path':str(outside)},operation_id='mediated')
        from dataclasses import replace
        inv=replace(inv,operation_id='mediated')
        read=rt.execute(inv)
        assert read.status is ToolStatus.DENIED and read.effect_state is EffectState.NONE
        assert 'S8_EXTERNAL_PRIVATE_SENTINEL' not in read.legacy_text
        assert outside.read_text()=='S8_EXTERNAL_PRIVATE_SENTINEL'
        record_property('s8.shell_external_read_real',True)
        record_property('s8.s3_external_read_denied',True)
    finally:rt.close();disk.close()
