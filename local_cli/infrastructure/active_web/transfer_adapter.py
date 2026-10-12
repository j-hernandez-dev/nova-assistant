"""Windows WebView2 transfers/UI. Infrastructure, no availability/Policy claims."""
import hashlib
import os
from pathlib import Path
from . import transfer_ipc as wire
from .observation_adapter import WebView2ObservationAdapter,ObservationHostClient,_Cancellation
from .host_ipc_protocol import HostIpcError,IpcCode,require,opaque
from .webview2_file_selection import detected_mime
from local_cli.core.active_web import BrowserActionKind as Action,BrowserOutcomeState as Outcome
from local_cli.core.active_web_policy import BrowserDispatchReport
from local_cli.core.active_web_transfers import UploadBuffer,DownloadPermit
from local_cli.core.contracts import EffectState

class TransferHostClient(ObservationHostClient):
    wire=wire
    max_transfer_bytes=0
    def typed_call(self,*args,**kwargs):
        try:return super().typed_call(*args,**kwargs)
        except HostIpcError as error:
            recoverable={'NOT_SUPPORTED_IN_CURRENT_BLOCK','STALE_TARGET','INVALID_ACTION','OBSERVATION_LIMIT','BUSY','TAKEOVER_ACTIVE','HUMAN_CONTROL_INCOMPLETE','TRANSFER_STALE'}
            if error.code in self.wire.ERRORS and error.code not in recoverable:self._fail(error)
            raise
    def _bootstrap_arguments(self):
        args=['--ipc-version','5','--udf',str(self.udf),'--transfer-max-bytes',str(self.max_transfer_bytes)]
        if self.local_content_root is not None:args+=['--local-content-root',str(self.local_content_root)]
        return args
    def call(self,command,*,page=None,timeout_ms=5000,cancel=None):
        r=self.typed_call(dict(command=command),page=page,timeout_ms=timeout_ms,cancel=cancel)
        require(r['kind']==command,IpcCode.CORRELATION_MISMATCH)
        if'hostInstanceRef'in r:require(r['hostInstanceRef']==self.instance,IpcCode.CORRELATION_MISMATCH)
        if command=='runtime_metadata':require(all(self.job.contains(p['pid'])for p in r['processes']),IpcCode.CLEANUP_UNCONFIRMED);self.metadata=r
        return r

class WebView2TransferAdapter(WebView2ObservationAdapter):
    def __init__(self,*args,max_transfer_bytes,local_content_root=None):
        super().__init__(*args,local_content_root=local_content_root)
        require(type(max_transfer_bytes)is int and max_transfer_bytes>0,IpcCode.INVALID_MESSAGE)
        root=local_content_root;limit=max_transfer_bytes
        class OwnedClient(TransferHostClient):local_content_root=root;max_transfer_bytes=limit
        self.client_type=OwnedClient;self._human=set();self._max_bytes=limit
    def begin_takeover(self,session,page,*,deadline):
        r=self._typed(session,page,dict(command='takeover_begin'),deadline);require(r['humanActive']is True)
        self._human.add(session);self._epochs={k:v for k,v in self._epochs.items()if k[0]!=session}
    def takeover_state(self,session,*,deadline):return self._client(session).call('takeover_state',timeout_ms=self._budget(deadline))
    def end_takeover(self,session,*,deadline):
        r=self._client(session).call('takeover_end',timeout_ms=self._budget(deadline));require(r['humanActive']is False)
        self._human.discard(session);self._epochs={k:v for k,v in self._epochs.items()if k[0]!=session}
    def transfer_metadata(self,session,page,*,deadline):return self._typed(session,page,dict(command='transfer_metadata'),deadline)
    def dispatch(self,request,engine_binding,*,payload,deadline,cancellation,started):
        if request.action_kind not in(Action.UPLOAD_FILE,Action.DOWNLOAD):return super().dispatch(request,engine_binding,payload=payload,deadline=deadline,cancellation=cancellation,started=started)
        none=lambda:BrowserDispatchReport(Outcome.FAILED_NO_EFFECT_CONFIRMED,EffectState.NONE,True)
        lock=self._action_locks.setdefault(request.browser_session_ref,__import__('threading').Lock())
        if not lock.acquire(blocking=False):return none()
        source=None
        try:
            if request.browser_session_ref in self._human or cancellation is not None and cancellation.is_cancel_requested():return none()
            self._page(request.browser_session_ref,request.page_ref);c=self._client(request.browser_session_ref)
            if request.action_kind is Action.UPLOAD_FILE:
                if not isinstance(payload,UploadBuffer):return none()
                s=payload.selection
                if(s.browser_session_ref!=request.browser_session_ref or s.size!=len(payload.buffer)or s.size>self._max_bytes or hashlib.sha256(payload.buffer).hexdigest()!=s.sha256 or detected_mime(payload.buffer,s.filename)!=s.mime):return none()
                source=opaque('wvu');root=c.udf/'_nova_transfers'/'up'/source;root.mkdir(parents=True,exist_ok=False)
                path=root/s.filename
                with path.open('xb')as stream:stream.write(payload.buffer);stream.flush();os.fsync(stream.fileno())
                args=dict(command='upload',binding=engine_binding,source=source,filename=s.filename,size=s.size,mime=s.mime,sha256=s.sha256)
            else:
                if not isinstance(payload,DownloadPermit)or payload.max_bytes>self._max_bytes:return none()
                args=dict(command='download',binding=engine_binding,maxBytes=payload.max_bytes)
            wire.envelope(request.browser_session_ref,args,page=request.page_ref)
            if self._invalidation_sink:self._invalidation_sink(request.browser_session_ref,request.page_ref,False)
            try:r=self._typed(request.browser_session_ref,request.page_ref,args,deadline,cancellation,started,request.operation_id)
            except wire.HostIpcError as e:
                if e.code in('TRANSFER_STALE','STALE_TARGET','TAKEOVER_ACTIVE'):return none()
                return BrowserDispatchReport(Outcome.UNKNOWN,EffectState.UNKNOWN)
            except Exception:return BrowserDispatchReport(Outcome.UNKNOWN,EffectState.UNKNOWN)
            if r['outcome']=='FAILED_NO_EFFECT_CONFIRMED':return none()
            if r['outcome']!='SUCCEEDED_OBSERVED':return BrowserDispatchReport(Outcome.UNKNOWN,EffectState.UNKNOWN)
            if request.action_kind is Action.DOWNLOAD:
                try:
                    from local_cli.infrastructure.knowledge_acquisition import LocalHostFileAcquisition
                    filename=r['suggestedName']
                    require(type(filename)is str and Path(filename).name==filename and filename not in('','.','..')and not any(ch in filename for ch in('/','\\',':','\x00','\r','\n')),IpcCode.INVALID_MESSAGE)
                    path=c.udf/'_nova_transfers'/'down'/r['fileToken']/filename
                    data=b''.join(LocalHostFileAcquisition(max_bytes=payload.max_bytes).read(str(path),cancelled=lambda:cancellation is not None and cancellation.is_cancel_requested(),progress=lambda n:None))
                    require(len(data)==r['size']and hashlib.sha256(data).hexdigest()==r['sha256']and r['origin']==payload.origin,IpcCode.INVALID_MESSAGE)
                    payload.stage(data,r['suggestedName'],r['mime']);path.unlink()
                except Exception:return BrowserDispatchReport(Outcome.UNKNOWN,EffectState.UNKNOWN)
            return BrowserDispatchReport(Outcome.SUCCEEDED_OBSERVED,EffectState.APPLIED)
        finally:
            if hasattr(payload,'read_lock'):payload.read_lock.close()
            lock.release()
