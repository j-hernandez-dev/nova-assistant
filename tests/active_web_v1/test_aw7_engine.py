"""AW7 real Chromium rendering/receipts; synthetic fixture, not PUBLIC_ONLY proof."""
import json
from dataclasses import replace
from datetime import datetime, timezone
import pytest

from local_cli.application.browser_actions import BrowserActions
from local_cli.application.browser_projection import BrowserFrontendProjection, BrowserFrontendBinding
from local_cli.application.secrets import SecretRedactor
from local_cli.core.contracts import EventKind, CapabilityStatus
from tests.active_web_v1.test_aw5_engine import engine, navigate, capture, end


def test_native_sdk_receipt_durable_audit_and_shared_projection(tmp_path):
    from local_cli.application.browser_actions import BrowserPolicyEngine
    from local_cli.application.tool_runtime import ToolRuntime, ToolRegistry
    from local_cli.application.grants import GrantIssuer
    from local_cli.application.policy import host_ceiling
    from local_cli.application.security_audit import SecurityAuditService
    from local_cli.application.cancellation import CancellationController
    from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit
    from local_cli.core.security import Capability, Permission, ResourceScope, ScopeKind, ControlClass
    from local_cli.core.contracts import ExecutionContext, RuntimeCapabilitySnapshot, ToolInvocation, new_tool_call_id, new_operation_id, new_turn_id
    from local_cli.core.active_web import BrowserActionRequest, BrowserActionKind as Action
    from local_cli.core.security_audit import AuditKind
    from tests.active_web_v1.test_aw3_policy import ContractOnlyBrowserTool
    events=[]
    with engine(tmp_path) as data:
        port,manager,obs,owner,session,page,*_=data
        p=BrowserFrontendProjection(publish=lambda *a,**kw:events.append((a,kw)),redactor=obs.redactor,owner_session_id=owner.agent_session_id)
        actions=BrowserActions(obs,port);BrowserFrontendBinding(manager,obs,actions,p)
        p.emit('BrowserSessionCreated',session.to_dict())
        navigate(data);observation=capture(data)
        target=next(e for e in observation.interactive_elements if e.accessible_name=='Next ledger')
        deadline=end();req=BrowserActionRequest(new_operation_id(),new_turn_id(),session.browser_session_ref,page,
            Action.NAVIGATE,deadline,observation.observation_ref,target.element_ref,observation.navigation_epoch,observation.observation_version)
        actions.register_plan(owner,req,explicit_user_intent=True)
        descriptor=ContractOnlyBrowserTool();descriptor.name='browser_navigate'
        registry=ToolRegistry([descriptor]);ceiling=host_ceiling(registry,tmp_path,owner.agent_session_id)
        cap=Capability(Permission('browser.read'),ResourceScope(ScopeKind.SESSION,session.browser_session_ref),ControlClass.APPLICATION_ENFORCED,{'network':'PUBLIC_ONLY'})
        store=JsonlSecurityAudit(tmp_path.parent/(tmp_path.name+'-aw7-audit'),workspace=tmp_path)
        runtime=ToolRuntime(registry,policy=BrowserPolicyEngine(actions),issuer=GrantIssuer(replace(ceiling,capabilities=(*ceiling.capabilities,cap)),policy_revision=1),
            browser_actions=actions,browser_projection=p,security_audit=SecurityAuditService(store,redactor=obs.redactor))
        context=ExecutionContext(workspace=tmp_path,cwd=tmp_path,environment={},session_id=owner.agent_session_id,turn_id=req.turn_id,
            operation_id=req.operation_id,cancellation_token=CancellationController(),deadline=deadline,
            capabilities=RuntimeCapabilitySnapshot(captured_at=datetime.now(timezone.utc),source='AW7-synthetic-real-engine'))
        result=runtime.execute(ToolInvocation(descriptor.name,{'request':req.to_dict()},new_tool_call_id(),req.operation_id,context))
        assert result.metadata['browserReceipt']['outcome']=='SUCCEEDED_OBSERVED'
        assert result.metadata['securityAudit']['gap'] is False
        assert p.snapshot()['receipts'][-1]['outcome']=='SUCCEEDED_OBSERVED'
        rows=store.read_operation(owner.agent_session_id,req.operation_id)
        assert next(r for r in rows if r.kind is AuditKind.DISPATCH).data['action']=='NAVIGATE'
        assert rows[-1].kind is AuditKind.TERMINAL
        assert all(s not in json.dumps([r.to_dict() for r in rows]) for s in ('Lantern ledger','fake-password','<html'))


@pytest.mark.parametrize('headful',[False,True])
def test_native_engine_application_metadata_no_privileged_desktop_surface(tmp_path,headful):
    events=[]
    with engine(tmp_path,headful=headful) as data:
        port,manager,obs,owner,session,page,*_=data
        caps=port.capabilities(session.browser_session_ref,deadline=end())
        p=BrowserFrontendProjection(publish=lambda *a,**kw:events.append((a,kw)),redactor=SecretRedactor(),capabilities=caps)
        BrowserFrontendBinding(manager,obs,BrowserActions(obs,port),p)
        # Context was opened before binding this display-only observer.
        p.emit('BrowserSessionCreated',session.to_dict())
        navigate(data);actual=capture(data)
        state=p.snapshot();wire=json.dumps(state)
        assert state['pages'][0]['title']=='Synthetic AW5'
        assert state['pages'][0]['observationRef']==actual.observation_ref
        assert all(s not in wire for s in ('fake-password','fake-hidden','fake-otp','Lantern ledger','engineHandle','preload','cookie'))
        assert caps.available.status is caps.public_only.status is CapabilityStatus.UNKNOWN
        manager.close(owner,session.browser_session_ref)
        assert p.snapshot()['cleanup']['contextConfirmed'] is True
        assert events[-1][0][0] is EventKind.BROWSER_SESSION_CLOSED
