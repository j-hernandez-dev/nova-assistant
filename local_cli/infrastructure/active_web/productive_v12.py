"""The V1.2 WebView2 product composition; no legacy availability inference.

Only Application dispatches exact claimed authority into this seam. The engine
remains HOST_UNISOLATED / networkIsolation=NOT_PROVIDED. No request retries,
model JavaScript, selector commands, cookies or FORM_SUBMIT are exposed.
"""
from dataclasses import dataclass
from datetime import datetime,timezone,timedelta
import hashlib
from pathlib import Path
from threading import Lock

from local_cli.application.active_web import BrowserSessionManager
from local_cli.application.browser_observation import BrowserObservationService
from local_cli.application.browser_takeover import BrowserTakeoverService
from local_cli.application.browser_actions_v12_b5 import V12B5BrowserActions
from local_cli.application.network import canonical_url
from local_cli.core.active_web import BrowserOutcomeState as Outcome
from local_cli.core.active_web_lifecycle import BrowserOwner,BrowserLimits
from local_cli.core.active_web_observation import ObservationLimits
from local_cli.core.active_web_policy import BrowserDispatchReport
from local_cli.core.active_web_transfers import BrowserTransferLimits
from local_cli.core.contracts import EffectState,new_operation_id
from local_cli.infrastructure.knowledge_acquisition import LocalHostFileAcquisition
from .transfer_adapter import WebView2TransferAdapter,TransferHostClient
from .webview2_transfers_v12 import V12BrowserTransferService
from .webview2_staging import WebView2DownloadStaging
from .host_ipc_protocol import IpcCode,HostIpcError,require,ref
from . import productive_ipc_v12 as wire


class ProductiveHostClient(TransferHostClient):
    wire=wire
    def _bootstrap_arguments(self):
        return ['--ipc-version','6','--udf',str(self.udf),'--transfer-max-bytes',str(self.max_transfer_bytes)]
    def typed_call(self,payload,**kwargs):
        acknowledged=False;callback=kwargs.get('started')
        if payload.get('command')=='navigate_admitted':
            def ack():
                nonlocal acknowledged
                acknowledged=True
                require(callback is not None,IpcCode.INVALID_STATE);callback()
            kwargs['started']=ack
        result=super().typed_call(payload,**kwargs)
        if payload.get('command')=='navigate_admitted':
            require(result['started']==acknowledged,IpcCode.CORRELATION_MISMATCH)
        return result


class ProductiveWebView2Adapter(WebView2TransferAdapter):
    def __init__(self,*args,owner,max_transfer_bytes):
        require(type(owner)is BrowserOwner,IpcCode.INVALID_MESSAGE)
        super().__init__(*args,max_transfer_bytes=max_transfer_bytes)
        self._owner=owner;limit=max_transfer_bytes
        class OwnedClient(ProductiveHostClient):max_transfer_bytes=limit
        self.client_type=OwnedClient
        self._context_epoch=lambda session:0

    def navigate_initial(self,owner,session,page,url,*,operation_id,policy_revision,
                         authority_digest,expected_epoch,deadline,cancellation,started):
        """Private exact read Grant dispatch supplied by Application web routing.

        No model call or external JSON can supply this method. The owning
        Application validates its one-use claimed Grant immediately before it.
        This physical adapter supplies no Policy, Approval or Grant authority.
        """
        none=lambda:BrowserDispatchReport(Outcome.FAILED_NO_EFFECT_CONFIRMED,EffectState.NONE,True)
        require(owner==self._owner and type(owner)is BrowserOwner,IpcCode.CORRELATION_MISMATCH)
        target=canonical_url(url);ref(operation_id,'op')
        wire.v5.digest(authority_digest);wire.v1.integer(policy_revision)
        wire.v1.integer(expected_epoch,minimum=0)
        require(self._context_epoch(session)==expected_epoch,IpcCode.CORRELATION_MISMATCH)
        payload=dict(command='navigate_admitted',capabilityId='INTERACTIVE_BROWSER_V1_2',canonicalTarget=target,
            ownerSessionId=owner.agent_session_id,workspaceDigest=hashlib.sha256(owner.workspace_id.encode()).hexdigest(),
            authorityDigest=authority_digest,policyRevision=policy_revision,browserContextEpoch=expected_epoch)
        self._page(session,page);wire.envelope(session,payload,page=page)
        lock=self._action_locks.setdefault(session,Lock())
        if not lock.acquire(blocking=False):return none()
        acknowledged=False
        def ack():
            nonlocal acknowledged
            acknowledged=True;started()
        try:
            if session in self._human or cancellation is not None and cancellation.is_cancel_requested():return none()
            if self._invalidation_sink:self._invalidation_sink(session,page,True)
            self._epochs.pop((session,page),None)
            result=self._typed(session,page,payload,deadline,cancellation,ack,operation_id)
            self._epochs[(session,page)]=(result['engineEpoch'],result['engineVersion'])
            if result['outcome']=='SUCCEEDED_OBSERVED':return BrowserDispatchReport(Outcome.SUCCEEDED_OBSERVED,EffectState.APPLIED)
            if result['outcome']=='FAILED_NO_EFFECT_CONFIRMED' and not acknowledged:return none()
            return BrowserDispatchReport(Outcome.UNKNOWN,EffectState.UNKNOWN)
        except HostIpcError as error:
            if not acknowledged and error.code in ('STALE_TARGET','INVALID_ACTION','TAKEOVER_ACTIVE'):return none()
            return BrowserDispatchReport(Outcome.UNKNOWN,EffectState.UNKNOWN)
        except Exception:return BrowserDispatchReport(Outcome.UNKNOWN,EffectState.UNKNOWN)
        finally:lock.release()

    def navigate_local(self,*args,**kwargs):
        raise wire.HostIpcError('INVALID_ACTION')


@dataclass
class ProductiveBrowserComposition:
    owner:BrowserOwner
    port:ProductiveWebView2Adapter
    manager:BrowserSessionManager
    observations:BrowserObservationService
    actions:V12B5BrowserActions
    transfers:V12BrowserTransferService
    takeovers:BrowserTakeoverService
    staging:WebView2DownloadStaging
    session:object=None
    page:str|None=None

    def open(self,*,turn_id,deadline,cancellation=None):
        if self.session is None:
            self.session=self.manager.open(self.owner,turn_id=turn_id,deadline=deadline,cancellation=cancellation,
                network_policy_id='INTERACTIVE_BROWSER_V1_2_NOT_PROVIDED',capability_snapshot_id='WEB_CAPABILITIES_V12')
            self.page=self.session.page_refs[0]
        else:
            # Existing owner/lifetime/takeover checks remain fail-closed.
            self.manager._active(self.manager._get(self.owner,self.session.browser_session_ref))
        return self.session

    def navigate_initial(self,url,*,turn_id,operation_id,policy_revision,authority_digest,expected_epoch,deadline,cancellation,started):
        require(self.session is not None,IpcCode.INVALID_STATE)
        session=self.session.browser_session_ref;page=self.page
        lease=self.manager.begin_operation(self.owner,session,page,turn_id=turn_id,operation_id=operation_id,
            navigation=True,deadline=deadline,cancellation=cancellation)
        try:return self.port.navigate_initial(self.owner,session,page,url,operation_id=operation_id,
            policy_revision=policy_revision,authority_digest=authority_digest,expected_epoch=expected_epoch,deadline=lease.deadline,
            cancellation=lease.cancellation,started=started)
        finally:self.manager.finish_operation(self.owner,session,lease)

    def observe(self,*,turn_id,deadline,cancellation=None):
        require(self.session is not None,IpcCode.INVALID_STATE)
        return self.observations.capture(self.owner,self.session.browser_session_ref,self.page,
            turn_id=turn_id,operation_id=new_operation_id(),deadline=deadline,cancellation=cancellation)

    def health(self,*,deadline):
        require(self.session is not None,IpcCode.INVALID_STATE)
        session=self.session.browser_session_ref
        client=self.port._client(session)
        client.ping(timeout_ms=self.port._budget(deadline))
        takeover=self.port.takeover_state(session,deadline=deadline)
        if takeover['humanActive']:
            # This already-running instance cannot swap its loaded SDK/runtime.
            # Agent-inhibited metadata APIs are not a lost host certificate.
            # Liveness and guard are still observed now, never cached true.
            require(client.metadata is not None,IpcCode.INVALID_STATE)
            runtime=client.metadata
        else:runtime=self.port.runtime_metadata(session,deadline=deadline)
        guard=self.port.guard_metadata(session,deadline=deadline)
        require(runtime['hostInstanceRef']==guard['hostInstanceRef']==self.port._client(session).instance,IpcCode.CORRELATION_MISMATCH)
        require(guard['externalProtocolGuard']=='HOST_PRE_EFFECT_DENY'and guard['policy']=='DENY_ALL'and
            guard['popupPolicy']=='DENY_ALL'and not guard['auditGap']and bool(guard['installations']),IpcCode.INVALID_STATE)
        return dict(runtime=runtime,guard=guard,takeoverState=takeover,ipcVersion=6,
            runtimeIdentityObservedBeforeTakeover=bool(takeover['humanActive']),networkIsolation='NOT_PROVIDED',controlClass='HOST_UNISOLATED')

    def close_browser(self):
        if self.session is None:return None
        return self.manager.close(self.owner,self.session.browser_session_ref)

    def close(self):
        # Retained staging has its own lifetime and survives close_browser.
        receipt=self.close_browser();self.staging.close();return receipt


def create_productive_browser(owner,*,dotnet_executable,host_assembly,owned_root,redactor,
        browser_limits=None,observation_limits=None,transfer_limits=None,staging_lifetime_seconds=600):
    """Host composition only; does not activate tools or derive availability."""
    root=Path(owned_root).resolve();require(root.is_absolute()and root.is_dir(),IpcCode.INVALID_STATE)
    bl=browser_limits or BrowserLimits(600,25,20,15)
    ol=observation_limits or ObservationLimits(24,1800,128,512)
    tl=transfer_limits or BrowserTransferLimits(2*1024*1024,8,4)
    port=ProductiveWebView2Adapter(dotnet_executable,host_assembly,root,owner=owner,max_transfer_bytes=tl.max_bytes)
    manager=BrowserSessionManager(port,limits=bl)
    observations=BrowserObservationService(manager,port,limits=ol,redactor=redactor)
    port.attach_invalidation_sink(lambda s,p,n:manager.invalidate_page_observation(owner,s,p,navigation=n))
    port._context_epoch=lambda s:manager.session(owner,s).browser_context_epoch
    staging=WebView2DownloadStaging(root,max_bytes=tl.max_bytes,max_downloads=tl.max_downloads,lifetime_seconds=staging_lifetime_seconds)
    transfers=V12BrowserTransferService(manager,LocalHostFileAcquisition(max_bytes=tl.max_bytes),staging,
        limits=tl,redactor=redactor,observations=observations)
    takeovers=BrowserTakeoverService(manager,port)
    actions=V12B5BrowserActions(observations,port,transfers=transfers,takeovers=takeovers)
    return ProductiveBrowserComposition(owner,port,manager,observations,actions,transfers,takeovers,staging)
