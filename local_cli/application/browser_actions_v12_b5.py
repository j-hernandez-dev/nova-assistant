"""Focal B5 transfers/takeover over B4 authority; no productive registration."""
from dataclasses import asdict
import hashlib

from local_cli.application.browser_actions_v12 import V12BrowserActions,V12BrowserTool,V12FixedActionPort,SCHEMAS as B4_SCHEMAS
from local_cli.application.browser_actions import BrowserActions,payload_digest
from local_cli.application.policy import PolicyInputError,validate_arguments,EffectResourceIntent,ToolPolicyAction
from local_cli.core.active_web import BrowserActionRequest,BrowserActionKind as A,BrowserOutcomeState as O
from local_cli.core.active_web_policy import BrowserDispatchReport
from local_cli.core.contracts import EffectState,json_safe_copy
from local_cli.core.browser_transfers_v12 import PROFILE,validate_binding

_s={'type':'string'}
_target={k:_s for k in ('capabilityId','browserSessionRef','pageRef','observationRef','elementRef')}
_target['capabilityId']={'type':'string','enum':['INTERACTIVE_BROWSER_V1_2']}
_target.update(navigationEpoch={'type':'integer'},observationVersion={'type':'integer'})
SCHEMAS={**B4_SCHEMAS,
 'browser_upload':dict(type='object',properties={**_target,'fileRef':_s},required=[*_target,'fileRef'],additionalProperties=False),
 'browser_download':dict(type='object',properties=_target,required=list(_target),additionalProperties=False),
 'browser_takeover':dict(type='object',properties={k:_target[k] for k in ('capabilityId','browserSessionRef','pageRef')}|{'reason':{'type':'string','enum':['LOGIN','CAPTCHA','USER_INTERACTION']}},required=['capabilityId','browserSessionRef','pageRef','reason'],additionalProperties=False)}

class V12B5BrowserTool(V12BrowserTool):
    def __init__(self,name):
        if name not in SCHEMAS:raise PolicyInputError('UNSUPPORTED_V12_B5_ACTION')
        self._name=name
    @property
    def parameters(self):return json_safe_copy(SCHEMAS[self.name])

class B5TransferActionPort(V12FixedActionPort):
    def dispatch(self,request,handle,*,payload,deadline,cancellation,started):
        if request.action_kind not in (A.UPLOAD_FILE,A.DOWNLOAD):
            return super().dispatch(request,handle,payload=payload,deadline=deadline,cancellation=cancellation,started=started)
        ack=False
        def begin():
            nonlocal ack
            ack=True;started()
        self.calls.append(dict(operationId=request.operation_id,action=request.action_kind.value,page=request.page_ref))
        report=self.engine.dispatch(request,handle,payload=payload,deadline=deadline,cancellation=cancellation,started=begin)
        if ack and report.outcome is O.FAILED_NO_EFFECT_CONFIRMED:return BrowserDispatchReport(O.UNKNOWN,EffectState.UNKNOWN)
        return report

class V12B5BrowserActions(V12BrowserActions):
    def __init__(self,observations,engine,*,transfers,takeovers):
        super().__init__(observations,engine);self.transfers=transfers;self.takeovers=takeovers;self.port=B5TransferActionPort(engine)
    def authority_restrictions(self):
        return dict(capabilityId='INTERACTIVE_BROWSER_V1_2',networkIsolation='NOT_PROVIDED',controlClass='HOST_UNISOLATED',profile=PROFILE)
    def prepare_invocation(self,inv):
        if inv.name in B4_SCHEMAS:return super().prepare_invocation(inv)
        with self._lock:
            ticket=self._authority(inv.context)
            if inv.name not in SCHEMAS:raise PolicyInputError('UNSUPPORTED_V12_B5_ACTION')
            args=json_safe_copy(inv.arguments);validate_arguments(args,SCHEMAS[inv.name])
            if inv.operation_id in self._arguments:
                if self._arguments[inv.operation_id]!=args:raise PolicyInputError('IDEMPOTENCY_CONFLICT')
                return
            if len(self._arguments)>=256:raise PolicyInputError('BROWSER_PLAN_QUOTA')
            action={'browser_upload':A.UPLOAD_FILE,'browser_download':A.DOWNLOAD,'browser_takeover':A.HUMAN_TAKEOVER}[inv.name]
            payload=args.get('fileRef',args.get('reason',''))
            req=BrowserActionRequest(inv.operation_id,inv.context.turn_id,args['browserSessionRef'],args['pageRef'],action,inv.context.deadline,
                args.get('observationRef'),args.get('elementRef'),args.get('navigationEpoch'),args.get('observationVersion'),
                payload_digest(payload) if payload else None,'NORMAL' if payload else None)
            destination=None
            if action is not A.HUMAN_TAKEOVER:
                self.transfers.bind_operation(ticket.owner,req,ticket.task)
                obs=self.observations._registry.get((req.browser_session_ref,req.page_ref))
                element=next((e for e in obs[0].interactive_elements if e.element_ref==req.element_ref),None) if obs else None
                destination=element.href_summary if element else None
                if destination in self._fetch_denials:raise PolicyInputError('CONTROLLED_FETCH_DENIAL_NO_BROWSER_BYPASS')
            BrowserActions.register_plan(self,ticket.owner,req,payload=payload,explicit_user_intent=True)
            self._arguments[inv.operation_id]=args;self._destinations[inv.operation_id]=destination
    def validate_action_binding(self,plan,binding):
        binding['transferLimits']=dict(maxBytes=self.transfers.limits.max_bytes,maxSelections=self.transfers.limits.max_selections,
            maxDownloads=self.transfers.limits.max_downloads,maxMimeChars=128)
        if plan.request.action_kind is A.HUMAN_TAKEOVER:
            page=self.observations.manager.page(plan.owner,plan.request.browser_session_ref,plan.request.page_ref)
            binding['navigationEpoch']=page.navigation_epoch
        return validate_binding(binding)
    def approval_display(self,inv,request):
        view=super().approval_display(inv,request);_,binding=self.binding(inv)
        for field in ('fileSelection','downloadPermit','transferLimits','takeoverReason'):
            if field in binding:view[field]=binding[field]
        return view
    def validate_prepared_transfer(self,inv,plan,binding,grant,issuer):
        self._authority(inv.context);issuer.validate_claimed(grant,grant.request)
        intent=EffectResourceIntent(grant.request.capabilities,plan.request.action_kind.value,
            '+'.join(e.value for e in plan.effects),dict(grant.request.network_intent))
        decision=self._runtime.policy.evaluate(inv,self._runtime.registry,issuer.ceiling,intent,parent=self._runtime._parent_grant)
        if decision.action is ToolPolicyAction.DENY:raise PolicyInputError(decision.reason)
        if self._destinations[inv.operation_id] in self._fetch_denials:raise PolicyInputError('CONTROLLED_FETCH_DENIAL_NO_BROWSER_BYPASS')
