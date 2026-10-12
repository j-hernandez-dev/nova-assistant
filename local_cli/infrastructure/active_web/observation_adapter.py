"""WebView2 observation/action Infrastructure. No policy or tool activation.

Only the authorized Application port path dispatches; host IPC is closed and
never accepts JS/selectors/CDP. Native bindings stay private behind AW2 refs.
"""
from threading import Lock
import time
from . import action_ipc as wire
from .guard_adapter import GuardHostClient,GuardWebView2Adapter
from .webview2_adapter import WebView2PortError
from .browser_host import HostState
from .host_ipc_protocol import HostIpcError,require,IpcCode
from .host_named_pipe import NamedPipeTransport
from local_cli.core.active_web import BrowserActionKind as Action,BrowserOutcomeState as Outcome
from local_cli.core.active_web_policy import BrowserDispatchReport
from local_cli.core.active_web_observation import CapturedElement,CapturedPage,TargetState,ObservationError,ObservationErrorCode
from local_cli.core.contracts import EffectState

class ObservationHostClient(GuardHostClient):
    wire=wire
    local_content_root=None
    def _bootstrap_arguments(self):
        args=['--ipc-version','4','--udf',str(self.udf)]
        if self.local_content_root is not None:args+=['--local-content-root',str(self.local_content_root)]
        return args
    def typed_call(self,payload,*,page,timeout_ms=5000,cancel=None,started=None,operation_id=None):
        with self._exclusive(timeout_ms,cancel) as end:
            codec=self.wire
            self._ready();request=codec.envelope(self.session,payload,page=page,timeout_ms=max(1,int((end-time.monotonic())*1000)))
            if operation_id is not None:request['operationId']=operation_id;codec.validate(request)
            try:
                self.transport.write(codec.encode(request),end=end,process=self.process,cancel=cancel)
                reply=self._receive(end=end,process=self.process,cancel=cancel);ack=False
                if reply['messageType']=='event':
                    codec.correlate(request,reply,event='ACTION_STARTED');require(started is not None,IpcCode.INVALID_MESSAGE)
                    ack=True;started();reply=self._receive(end=end,process=self.process,cancel=cancel)
                result=codec.correlate(request,reply)
                if payload['command'] in ('act','upload','download'):require(result['started']==ack,IpcCode.CORRELATION_MISMATCH)
                NamedPipeTransport.check(end,self.process,cancel);self._last=request;return result
            except wire.HostIpcError as e:
                if e.code in codec.ERRORS:raise
                self._fail(e);raise
            except HostIpcError as e:self._fail(e);raise

class WebView2ObservationAdapter(GuardWebView2Adapter):
    client_type=ObservationHostClient
    def __init__(self,*args,local_content_root=None):
        super().__init__(*args);self._local_root=local_content_root;self._action_locks={};self._epochs={};self._invalidation_sink=None
        # Per-instance trusted factory; no global config or model-selected path.
        root=local_content_root
        class OwnedClient(ObservationHostClient):local_content_root=root
        self.client_type=OwnedClient
    def _typed(self,session,page,payload,deadline,cancellation=None,started=None,operation_id=None):
        self._page(session,page)
        return self._client(session).typed_call(payload,page=page,timeout_ms=self._budget(deadline),cancel=_Cancellation(cancellation),started=started,operation_id=operation_id)
    def navigate_local(self,session,page,path,*,deadline,cancellation=None):
        """Trusted offline test/Infrastructure seam, not browser_navigate tool."""
        if self._invalidation_sink:self._invalidation_sink(session,page,True)
        self._epochs.pop((session,page),None)
        return self._typed(session,page,dict(command='navigate_local',path=path),deadline,cancellation)
    def attach_invalidation_sink(self,sink):
        """Trusted composition-only freshness notification, never authority."""
        require(callable(sink),IpcCode.INVALID_STATE);self._invalidation_sink=sink
    def _sync_epoch(self,session,page,r):
        previous=self._epochs.get((session,page));current=(r['engineEpoch'],r['engineVersion'])
        # Capture increments the native observation version itself; epoch is the
        # externally meaningful navigation signal. Resolve also reports dirty
        # versions (popup/actions), before Application can yield a usable target.
        if previous is not None and (current[0]!=previous[0]or r['kind']=='resolve'and current[1]!=previous[1])and self._invalidation_sink:
            self._invalidation_sink(session,page,current[0]!=previous[0])
        self._epochs[(session,page)]=current
    def capture(self,session,page,*,limits,deadline,cancellation):
        # Never silently clamp a host request then publish truncated=false.
        # This closed IPC profile refuses larger requests, not Core ceilings.
        if limits.max_elements>32 or limits.max_text_chars>8192 or limits.max_field_chars>512:raise ObservationError(ObservationErrorCode.BUDGET)
        r=self._typed(session,page,dict(command='capture',maxElements=limits.max_elements,maxText=limits.max_text_chars,maxField=limits.max_field_chars),deadline,cancellation)
        self._sync_epoch(session,page,r)
        return CapturedPage(r['url'],r['title'],r['text'],tuple(CapturedElement(e['binding'],e['fingerprint'],e['role'],e['name'],e['kind'],tuple(Action(c) for c in e['capabilities']),e['state'],e['href'],is_form=e['isForm'])for e in r['elements']),tuple(r['dialogs']))
    def resolve(self,session,page,engine_binding,*,deadline,cancellation):
        r=self._typed(session,page,dict(command='resolve',binding=engine_binding),deadline,cancellation)
        self._sync_epoch(session,page,r)
        return TargetState(engine_binding,r['fingerprint'],r['origin'],tuple(Action(c) for c in r['capabilities']))if r['found'] else None
    def dispatch(self,request,engine_binding,*,payload,deadline,cancellation,started):
        lock=self._action_locks.setdefault(request.browser_session_ref,Lock())
        none=lambda:BrowserDispatchReport(Outcome.FAILED_NO_EFFECT_CONFIRMED,EffectState.NONE,True)
        if not lock.acquire(blocking=False):return none()
        try:
            if cancellation is not None and cancellation.is_cancel_requested():return none()
            fields=[];text=payload
            if request.action_kind is Action.FORM_SUBMIT:
                from local_cli.application.active_web_service import FormFields
                if not isinstance(payload,FormFields):return none()
                fields=[dict(binding=b,value=v)for b,v in payload.fields];text=''
            if not isinstance(text,str)or request.action_kind.value not in wire.ACTIONS:return none()
            try:
                self._page(request.browser_session_ref,request.page_ref);self._client(request.browser_session_ref);self._budget(deadline)
                args=dict(command='act',action=request.action_kind.value,binding=engine_binding,text=text,fields=fields)
                # Validate before any write. No-effect evidence is possible here.
                wire.envelope(request.browser_session_ref,args,page=request.page_ref)
            except HostIpcError:return none()
            try:
                if self._invalidation_sink:self._invalidation_sink(request.browser_session_ref,request.page_ref,request.action_kind in (Action.BACK,Action.FORWARD,Action.NAVIGATE))
                r=self._typed(request.browser_session_ref,request.page_ref,args,deadline,cancellation,started,request.operation_id)
                self._epochs[(request.browser_session_ref,request.page_ref)]=(r['engineEpoch'],r['engineVersion'])
                if r['outcome']=='FAILED_NO_EFFECT_CONFIRMED':return none()
                if r['outcome']=='UNKNOWN':return BrowserDispatchReport(Outcome.UNKNOWN,EffectState.UNKNOWN)
                if r['outcome']=='PARTIAL':return BrowserDispatchReport(Outcome.PARTIAL,EffectState.PARTIAL)
                return BrowserDispatchReport(Outcome.SUCCEEDED_OBSERVED,EffectState.NONE if request.action_kind in (Action.WAIT,Action.SCROLL)else EffectState.APPLIED)
            except wire.HostIpcError as e:
                if e.code in wire.ERRORS:return none() # explicit host pre-effect proof
                return BrowserDispatchReport(Outcome.UNKNOWN,EffectState.UNKNOWN)
            except Exception:return BrowserDispatchReport(Outcome.UNKNOWN,EffectState.UNKNOWN)
        finally:lock.release()

class _Cancellation:
    def __init__(self,token):self.token=token
    def is_set(self):return self.token is not None and self.token.is_cancel_requested()
