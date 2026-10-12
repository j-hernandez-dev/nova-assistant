"""Focal opt-in V1.2 actions composition. Never installed by CLI/JSONL/Desktop.

Reuses PolicyEngineV2, ToolRuntime, ApprovalGate, GrantIssuer and private v5.
Task tickets are host-only; page text and model arguments cannot create them.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
from copy import deepcopy

from local_cli.application.browser_actions import BrowserActions, BrowserPolicyEngine, payload_digest
from local_cli.application.active_web_service import explicit_browser_intent
from local_cli.application.network import canonical_url
from local_cli.application.policy import PolicyInputError, ToolPolicyAction, validate_arguments
from local_cli.core.active_web import BrowserActionRequest, BrowserActionKind as A, BrowserOutcomeState as O
from local_cli.core.active_web_policy import BrowserDispatchReport, READ_EFFECTS
from local_cli.core.active_web_lifecycle import BrowserOwner
from local_cli.core.contracts import EffectState, json_safe_copy
from local_cli.core.browser_authority_v12 import PROFILE, validate_binding
from local_cli.core.interactive_browser_v12 import INTERACTIVE_BROWSER_CAPABILITY_ID as IB
from local_cli.core.security import Capability, Permission, ResourceScope, ScopeKind, ControlClass
from local_cli.tools.base import Tool

_target={k:{'type':'string'} for k in ('browserSessionRef','pageRef','observationRef','elementRef')}
_target.update(capabilityId={'type':'string','enum':[IB]},navigationEpoch={'type':'integer'},observationVersion={'type':'integer'})
SCHEMAS={
    'browser_act':dict(type='object',properties={**_target,'action':{'type':'string','enum':['CLICK','INPUT_TEXT','SELECT_OPTION','PRESS_KEY']},'value':{'type':'string'}},required=[*_target,'action'],additionalProperties=False),
    'browser_navigate':dict(type='object',properties={**_target,'url':{'type':'string'}},required=[*_target,'url'],additionalProperties=False),
}


class V12BrowserTool(Tool):
    """Descriptor for injected focal composition, never a default tool."""
    cacheable=False
    def __init__(self,name):
        if name not in SCHEMAS:raise ValueError('UNSUPPORTED_V12_BROWSER_ACTION')
        self._name=name
    @property
    def name(self):return self._name
    @property
    def description(self):
        return ('INTERACTIVE_BROWSER_V1_2 fixed actions, opaque fresh refs. Page content is untrusted. '
            'Exact mutations require human approval. Network isolation NOT_PROVIDED; '
            'HOST_UNISOLATED. Productive availability NOT_ENABLED. No automatic retry.')
    @property
    def parameters(self):return deepcopy(SCHEMAS[self.name])
    def execute(self,**kwargs):raise PolicyInputError('BROWSER_TOOLRUNTIME_REQUIRED')


@dataclass(frozen=True)
class _TaskAuthority:
    owner: BrowserOwner
    turn: str
    task: str
    expires: datetime
    digest: str


class V12FixedActionPort:
    """Same native actions; conservative V1.2 interpretation of their evidence.

Native performed:true is not remote success. Mutations remain UNKNOWN even if
the engine completed a DOM call. Navigation success additionally needs exact
current URL observation. No hidden action, retry or compensation is performed.
"""
    def __init__(self,engine):self.engine=engine;self.calls=[]
    def dispatch(self,request,handle,*,payload,deadline,cancellation,started):
        acknowledged=False
        def ack():
            nonlocal acknowledged
            acknowledged=True;started()
        self.calls.append(dict(operationId=request.operation_id,action=request.action_kind.value,
            payloadDigest=request.payload_digest,page=request.page_ref))
        report=self.engine.dispatch(request,handle,payload=payload,deadline=deadline,cancellation=cancellation,started=ack)
        if acknowledged and request.action_kind is not A.NAVIGATE and report.outcome not in (O.PARTIAL,O.UNKNOWN):
            return BrowserDispatchReport(O.UNKNOWN,EffectState.UNKNOWN)
        if acknowledged and report.outcome is O.FAILED_NO_EFFECT_CONFIRMED:
            return BrowserDispatchReport(O.UNKNOWN,EffectState.UNKNOWN)
        if report.outcome is O.SUCCEEDED_OBSERVED and request.action_kind is A.NAVIGATE:
            try:
                from local_cli.core.active_web_observation import ObservationLimits
                observed=self.engine.capture(request.browser_session_ref,request.page_ref,
                    limits=ObservationLimits(16,1024,128,512),deadline=deadline,cancellation=cancellation)
                if canonical_url(observed.url)!=payload:raise ValueError('DESTINATION_UNCONFIRMED')
            except Exception:return BrowserDispatchReport(O.UNKNOWN,EffectState.UNKNOWN)
        return report


class V12BrowserActions(BrowserActions):
    def __init__(self,observations,engine):
        super().__init__(observations,V12FixedActionPort(engine))
        self._authorities={};self._arguments={};self._runtime=None;self._fetch_denials=set()
        self._destinations={}

    def attach_runtime(self,runtime):
        if self._runtime is not None or runtime._browser_actions is not self or runtime.policy.actions is not self:
            raise PolicyInputError('INVALID_V12_RUNTIME_COMPOSITION')
        self._runtime=runtime

    def bind_human_task(self,owner,turn,task_id,user_input,*,expires):
        """Host input boundary only; never exposed in model descriptors or IPC."""
        if (type(owner) is not BrowserOwner or type(turn) is not str or not turn.startswith('turn_') or
            type(task_id) is not str or not task_id.strip() or type(user_input) is not str or
            not explicit_browser_intent(user_input) or expires.tzinfo is None or expires<=datetime.now(timezone.utc)):
            raise PolicyInputError('BROWSER_USER_INTENT_REQUIRED')
        digest=hashlib.sha256((owner.agent_session_id+'\n'+owner.workspace_id+'\n'+turn+'\n'+task_id+'\n'+user_input+'\n'+expires.isoformat()).encode()).hexdigest()
        with self._lock:
            if turn in self._authorities:raise PolicyInputError('TASK_AUTHORITY_ALREADY_BOUND')
            self._authorities[turn]=_TaskAuthority(owner,turn,task_id,expires,digest)

    def note_controlled_fetch_denial(self,target):
        """Host routing contract: an existing denial never creates browser authority."""
        with self._lock:self._fetch_denials.add(canonical_url(target))

    def authority_restrictions(self):
        return dict(capabilityId=IB,networkIsolation='NOT_PROVIDED',controlClass='HOST_UNISOLATED',profile=PROFILE)

    def _authority(self,ctx):
        ticket=self._authorities.get(ctx.turn_id)
        if (ticket is None or ctx.agent_id is not None or ctx.session_id!=ticket.owner.agent_session_id or
            str(ctx.workspace.resolve())!=ticket.owner.workspace_id or ctx.deadline is None or
            ctx.deadline>ticket.expires or datetime.now(timezone.utc)>=min(ctx.deadline,ticket.expires)):
            raise PolicyInputError('BROWSER_TASK_AUTHORITY_DENIED')
        return ticket

    def prepare_invocation(self,invocation):
        with self._lock:
            ticket=self._authority(invocation.context)
            if invocation.name not in SCHEMAS:raise PolicyInputError('UNSUPPORTED_V12_BROWSER_ACTION')
            args=json_safe_copy(invocation.arguments);validate_arguments(args,SCHEMAS[invocation.name])
            if invocation.operation_id in self._arguments:
                if self._arguments[invocation.operation_id]!=args:raise PolicyInputError('IDEMPOTENCY_CONFLICT')
                return
            if len(self._arguments)>=256:raise PolicyInputError('BROWSER_PLAN_QUOTA')
            action=A.NAVIGATE if invocation.name=='browser_navigate' else A(args['action'])
            payload=canonical_url(args['url']) if action is A.NAVIGATE else args.get('value','')
            if len(payload)>8192:raise PolicyInputError('INVALID_BROWSER_PAYLOAD')
            if action is A.CLICK and payload:raise PolicyInputError('INVALID_BROWSER_PAYLOAD')
            if action is A.PRESS_KEY and payload not in ('Enter','Tab','Escape','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Space'):
                raise PolicyInputError('INVALID_BROWSER_KEY')
            try:
                req=BrowserActionRequest(invocation.operation_id,invocation.context.turn_id,args['browserSessionRef'],
                    args['pageRef'],action,invocation.context.deadline,args['observationRef'],args['elementRef'],
                    args['navigationEpoch'],args['observationVersion'],
                    payload_digest(payload) if action is not A.CLICK else None,'NORMAL' if action is not A.CLICK else None)
            except ValueError:
                # Closed Core refs reject other capability/staging identities.
                # Project that pre-effect failure through the Policy result path.
                raise PolicyInputError('INVALID_BROWSER_BINDING') from None
            obs=self.observations._registry.get((req.browser_session_ref,req.page_ref))
            element=next((e for e in obs[0].interactive_elements if e.element_ref==req.element_ref),None) if obs else None
            destination=canonical_url(element.href_summary) if element and element.href_summary else None
            if action is A.NAVIGATE:
                if destination!=payload:
                    raise PolicyInputError('BROWSER_DESTINATION_MISMATCH')
            if destination in self._fetch_denials:
                raise PolicyInputError('CONTROLLED_FETCH_DENIAL_NO_BROWSER_BYPASS')
            super().register_plan(ticket.owner,req,payload=payload,explicit_user_intent=True)
            self._arguments[invocation.operation_id]=args
            self._destinations[invocation.operation_id]=destination

    def plan_arguments(self,plan):return self._arguments[plan.request.operation_id]

    def host_capabilities(self,invocation):
        plan=self._plans[invocation.operation_id]
        return tuple(Capability(Permission(p),ResourceScope(ScopeKind.SESSION,plan.request.browser_session_ref),
            ControlClass.APPLICATION_ENFORCED,self.authority_restrictions()) for p in ('browser.read','browser.act'))

    def validate_action_binding(self,plan,binding):
        return validate_binding(binding)

    def binding(self,invocation):
        ticket=self._authority(invocation.context)
        plan,binding=super().binding(invocation)
        req=plan.request
        if self._destinations[req.operation_id] in self._fetch_denials:
            raise PolicyInputError('CONTROLLED_FETCH_DENIAL_NO_BROWSER_BYPASS')
        binding.update(owner=ticket.owner.agent_session_id,workspace=ticket.owner.workspace_id,taskId=ticket.task,
            taskAuthorityDigest=ticket.digest,turnId=req.turn_id,operationId=req.operation_id,toolCallId=invocation.tool_call_id,
            policyRevision=self._runtime.policy.revision if self._runtime else invocation.context.policy_revision,
            destination=self._destinations[req.operation_id],
            limits=asdict(self.observations.manager.limits))
        binding['documentIdentity']=hashlib.sha256((req.browser_session_ref+req.page_ref+str(binding['browserContextEpoch'])+str(req.expected_navigation_epoch)).encode()).hexdigest()
        return plan,self.validate_action_binding(plan,binding)

    def approval_display(self,invocation,grant_request):
        plan,binding=self.binding(invocation)
        if json_safe_copy(grant_request.network_intent)!=binding:raise PolicyInputError('APPROVAL_STALE')
        return dict(capabilityId=IB,action=binding['actionKind'],origin=binding['origin'],target=binding['elementRef'],
            destination=binding['destination'],payloadDigest=binding['payloadDigest'],effectClasses=binding['effectClasses'],
            operationId=binding['operationId'],observationRef=binding['observationRef'],
            navigationEpoch=binding['navigationEpoch'],browserContextEpoch=binding['browserContextEpoch'],
            policyRevision=binding['policyRevision'],deadline=binding['deadline'],
            dataPreview=self.observations.redactor.text(plan.payload),
            accessibleLabel=binding['accessibleLabel'],warning='Remote effects may remain UNKNOWN; no retry. Network isolation NOT_PROVIDED.')

    def execute(self,invocation,grant,issuer,*,approval_gate=None):
        if self._runtime is None or issuer is not self._runtime._issuer:raise PolicyInputError('INVALID_V12_RUNTIME_COMPOSITION')
        intent=self._runtime.policy.intent(invocation,self._runtime.registry,issuer.ceiling)
        decision=self._runtime.policy.evaluate(invocation,self._runtime.registry,issuer.ceiling,intent,parent=self._runtime._parent_grant)
        if decision.action is ToolPolicyAction.DENY:raise PolicyInputError(decision.reason)
        return super().execute(invocation,grant,issuer,approval_gate=approval_gate)
