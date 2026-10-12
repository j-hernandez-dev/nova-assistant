"""Exact Windows V1.2 host selections/permits behind the Application seam."""
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

from local_cli.infrastructure.active_web.webview2_file_selection import WebView2TransferService
from local_cli.core.active_web import BrowserActionKind as A
from local_cli.core.active_web_transfers import BrowserTransferError


class V12BrowserTransferService(WebView2TransferService):
    def __init__(self,*args,observations,**kwargs):
        super().__init__(*args,**kwargs);self.observations=observations;self._scopes={};self._operations={};self._scope_digests={}

    def host_select_for(self,owner,invocation,path,*,task_id,actor):
        """Trusted picker seam: no model path/handle/Knowledge source accepted."""
        view=super().host_select(owner,invocation.arguments['browserSessionRef'],path,actor=actor,deadline=invocation.context.deadline)
        session=self.manager.session(owner,view.browser_session_ref)
        scope=dict(ownerAgentSessionId=owner.agent_session_id,workspace=owner.workspace_id,taskId=task_id,
            operationId=invocation.operation_id,turnId=invocation.context.turn_id,browserSessionRef=view.browser_session_ref,
            pageRef=invocation.arguments['pageRef'],elementRef=invocation.arguments['elementRef'],
            observationRef=invocation.arguments['observationRef'],navigationEpoch=invocation.arguments['navigationEpoch'],
            observationVersion=invocation.arguments['observationVersion'],browserContextEpoch=session.browser_context_epoch,
            expiresAt=invocation.context.deadline.isoformat(),selectedPathIdentity=hashlib.sha256(str(Path(path).resolve()).encode()).hexdigest())
        # Pin actual cached origin/fingerprint as well as all opaque identities.
        from local_cli.core.active_web import BrowserActionRequest
        request=BrowserActionRequest(invocation.operation_id,invocation.context.turn_id,view.browser_session_ref,scope['pageRef'],
            A.UPLOAD_FILE,invocation.context.deadline,scope['observationRef'],scope['elementRef'],scope['navigationEpoch'],scope['observationVersion'],
            hashlib.sha256(view.file_ref.encode()).hexdigest(),'NORMAL')
        target=self.observations.approval_target(owner,request)
        scope.update(targetOrigin=target['origin'],targetFingerprint=target['targetFingerprint'])
        with self._lock:
            self._scopes[view.file_ref]=(view,scope)
            self._scope_digests[view.file_ref]=hashlib.sha256(json.dumps(scope,sort_keys=True).encode()).hexdigest()
        return view

    def bind_operation(self,owner,request,task_id):
        with self._lock:
            existing=self._operations.get(request.operation_id)
            value=(owner,request,task_id)
            if existing is not None and existing!=value:raise BrowserTransferError('V12_TRANSFER_OPERATION_MISMATCH')
            self._operations[request.operation_id]=value

    def _scope(self,owner,request,payload):
        operation=self._operations.get(request.operation_id)
        if operation is None or operation[:2]!=(owner,request):raise BrowserTransferError('V12_TRANSFER_OPERATION_MISMATCH')
        session=self.manager.session(owner,request.browser_session_ref)
        if request.action_kind is A.DOWNLOAD:
            return dict(capabilityId='INTERACTIVE_BROWSER_V1_2',owner=owner.agent_session_id,workspace=owner.workspace_id,
                taskId=operation[2],operationId=request.operation_id,browserSessionRef=request.browser_session_ref,
                pageRef=request.page_ref,elementRef=request.element_ref,observationRef=request.observation_ref,
                navigationEpoch=request.expected_navigation_epoch,observationVersion=request.expected_observation_version,
                browserContextEpoch=session.browser_context_epoch,deadline=request.deadline.isoformat(),maxBytes=self.limits.max_bytes,
                maxMimeChars=128,oneUse=True)
        pair=self._scopes.get(payload)
        if pair is None:raise BrowserTransferError('V12_SELECTION_NOT_ISSUED')
        view,scope=pair;record=self._files.get(payload)
        if hashlib.sha256(json.dumps(scope,sort_keys=True).encode()).hexdigest()!=self._scope_digests.get(payload):
            raise BrowserTransferError('V12_SELECTION_BINDING_CHANGED')
        if (record is None or record[3] is not view or scope['taskId']!=operation[2] or
            scope['ownerAgentSessionId']!=owner.agent_session_id or scope['workspace']!=owner.workspace_id or
            scope['operationId']!=request.operation_id or scope['turnId']!=request.turn_id or
            scope['browserSessionRef']!=request.browser_session_ref or scope['pageRef']!=request.page_ref or
            scope['elementRef']!=request.element_ref or scope['observationRef']!=request.observation_ref or
            scope['navigationEpoch']!=request.expected_navigation_epoch or scope['observationVersion']!=request.expected_observation_version or
            scope['browserContextEpoch']!=session.browser_context_epoch or datetime.now(timezone.utc)>=datetime.fromisoformat(scope['expiresAt'])):
            raise BrowserTransferError('V12_SELECTION_OWNER_OPERATION_EPOCH_OR_EXPIRY_MISMATCH')
        return {**view.to_dict(),**scope}

    def binding(self,owner,request,payload):
        value=super().binding(owner,request,payload)
        scope=self._scope(owner,request,payload)
        if request.action_kind is A.UPLOAD_FILE:value['fileSelection']=scope
        else:value['downloadPermit']=scope
        return value

    def prepare(self,owner,request,payload,binding,*,deadline,cancellation):
        # Same native locked read and hash/revision verification; not a new IO policy.
        prepared=super().prepare(owner,request,payload,binding,deadline=deadline,cancellation=cancellation)
        if request.action_kind is A.UPLOAD_FILE:return prepared
        from local_cli.core.active_web_transfers import DownloadPermit
        original=prepared.stage
        used=False
        def stage(data,filename,mime):
            nonlocal used
            if used:raise BrowserTransferError('V12_DOWNLOAD_PERMIT_CONSUMED')
            used=True
            if len(mime)>128:raise BrowserTransferError('V12_DOWNLOAD_MIME_LIMIT')
            result=original(data,filename,mime)
            result.update(capabilityId='INTERACTIVE_BROWSER_V1_2',operationId=request.operation_id,
                browserSessionRef=request.browser_session_ref,pageRef=request.page_ref,
                browserContextEpoch=binding['browserContextEpoch'],provenance='WEBVIEW2_COMPLETED_OWNED_STAGING',
                **self.staging.ownership(owner,result['downloadRef']))
            with self._lock:self._downloads[request.operation_id]=dict(result)
            return result
        return DownloadPermit(prepared.max_bytes,stage,prepared.origin)
