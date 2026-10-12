"""AW5 opt-in Chromium adapter. No public tools, policy or authority issuer.

The host installs the optional extra/engine explicitly and supplies a session
broker factory. No personal/desktop profile, remote CDP, installer or persistent
storage API. Sync Application ports bridge to one private asyncio worker; pages
never supply selectors/JS. Fixed inspection scripts below are adapter-owned.
Engine/network exclusivity remains UNKNOWN, not inferred from launch flags.
"""
from __future__ import annotations

import asyncio
from collections import deque
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
import os
import sys
from threading import Event, Thread
from urllib.parse import urlsplit
from uuid import uuid4

from local_cli.application.network import canonical_url
from local_cli.core.active_web import BrowserActionKind as Action, BrowserOutcomeState as Outcome
from local_cli.core.active_web_lifecycle import (
    BrowserLifecycleError, BrowserLifecycleErrorCode as Code, aware, ref,
)
from local_cli.core.active_web_observation import CapturedElement, CapturedPage, TargetState
from local_cli.core.active_web_policy import BrowserDispatchReport
from local_cli.core.contracts import BrowserCapabilitySnapshot, Observation, EffectState
from local_cli.infrastructure.active_web.egress_broker import BrowserEgressBroker
from local_cli.infrastructure.active_web.capability_probe import probe_browser_broker
from local_cli.core.active_web_transfers import UploadBuffer, DownloadPermit


# No user args/paths/profiles/extension flags can be added through this adapter.
CHROMIUM_ARGS = (
    '--proxy-bypass-list=<-loopback>', '--disable-quic',
    # Broker endpoint is numeric loopback. Target DNS belongs to the broker,
    # never Chromium's speculative/raw resolver. Process-local, not OS policy.
    '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1',
    '--force-webrtc-ip-handling-policy=disable_non_proxied_udp',
    '--disable-background-networking', '--disable-component-update',
    '--disable-sync', '--no-first-run', '--no-default-browser-check',
    '--disable-extensions',
    '--disable-features=WebRtc,WebRtcHideLocalIpsWithMdns,WebTransport',
    '--disable-domain-reliability', '--dns-prefetch-disable',
)
_ENV_KEYS = ('SystemRoot', 'WINDIR', 'PATH', 'COMSPEC', 'TEMP', 'TMP',
             'PROGRAMFILES', 'PROGRAMFILES(X86)')

# Read rendered text with finite DOM traversal; never serialize HTML, inputs,
# storage, headers, hidden nodes or arbitrary caller code. Long text is marked
# truncated by AW2 by returning at most max_text_chars+1.
_TEXT = """({limit}) => {
  const w=document.createTreeWalker(document.body||document.documentElement,NodeFilter.SHOW_TEXT);
  let text='',n,count=0;
  while((n=w.nextNode()) && ++count<=20000 && text.length<=limit) {
    const p=n.parentElement;
    if(!p || p.closest('script,style,noscript,template,input,textarea,[hidden],[aria-hidden="true"]')) continue;
    if(!p.getClientRects().length || getComputedStyle(p).visibility==='hidden') continue;
    text+=(n.textContent||'').slice(0,limit+1-text.length)+' ';
  }
  return text.slice(0,limit+1);
}"""
_NODES = """({limit}) => Array.from(document.querySelectorAll(
 'a[href],button,input:not([type=hidden]),textarea,select,form,[role=button],[role=link]'
)).slice(0,limit)"""
_META = """(e, {bound}) => {
  const tag=e.tagName.toLowerCase(),type=(e.getAttribute('type')||'').toLowerCase();
  const labelIds=(e.getAttribute('aria-labelledby')||'').split(/\\s+/).filter(Boolean);
  const labelled=labelIds.slice(0,16).map(id=>document.getElementById(id)?.textContent||'').join(' ');
  const name=(e.getAttribute('aria-label')||labelled||Array.from(e.labels||[]).slice(0,8)
    .map(x=>x.textContent||'').join(' ')||e.textContent||'').trim().slice(0,bound+1);
  const secret=tag==='input' && (['password','hidden'].includes(type) ||
    /password|passwd|otp|one-time|recovery|card|cvv|token|secret|private.?key/i.test(
      [e.name,e.id,e.autocomplete,name].join(' ')));
  const form=tag==='form'?e:e.form;
  const credentialForm=!!form?.querySelector('input[type=password],input[autocomplete=one-time-code],input[autocomplete^=cc-]');
  let kind=tag==='input'?type||'text':tag;
  let caps=[];
  if(!secret && !e.disabled && !e.readOnly) {
    if(tag==='a' && e.href) caps=['NAVIGATE','DOWNLOAD'];
    else if(tag==='input' && kind==='file' && !credentialForm) caps=['UPLOAD_FILE'];
    else if(tag==='textarea'||tag==='input'&&['text','search','email','url','tel','number'].includes(kind)) caps=['INPUT_TEXT','PRESS_KEY'];
    else if(tag==='select') caps=['SELECT_OPTION'];
    else if(tag==='form' && !credentialForm) caps=['FORM_SUBMIT'];
    else if((tag==='button'||['button','link'].includes(e.getAttribute('role'))) && !credentialForm) caps=['CLICK','PRESS_KEY'];
  }
  return {tag,kind,name,role:e.getAttribute('role')||({a:'link',button:'button',input:'textbox',textarea:'textbox',select:'combobox',form:'form'}[tag]||tag),
    href:tag==='a'?e.href:null,formAction:e.form?.action||(tag==='form'?e.action:null),
    formMethod:e.form?.method||(tag==='form'?e.method:null),connected:e.isConnected,
    visible:e.isConnected&&!!e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden',
    disabled:!!e.disabled,readOnly:!!e.readOnly,secret,credentialForm,caps,
    state:e.disabled?'disabled':e.readOnly?'readonly':'enabled'};
}"""
_HARDEN = """(() => {
 for (const key of ['RTCPeerConnection','webkitRTCPeerConnection','WebTransport'])
   try { Object.defineProperty(globalThis,key,{value:undefined,writable:false,configurable:false}); } catch {}
 // service_workers='block' prevents engine execution but may resolve register()
 // with a stub registration. Explicit Core V1 refusal in EVERY frame/context.
 // Retain the SDK's existing refusal diagnostic when its blocked-register
 // stub is already installed, but never call a native register implementation.
 const sdkRefusal = navigator.serviceWorker?.register;
 const sdkBlocked = typeof sdkRefusal === 'function' &&
   Function.prototype.toString.call(sdkRefusal).includes('Service Worker registration blocked by Playwright');
 const refuseWorker = function() {
   if (sdkBlocked) try { sdkRefusal.apply(navigator.serviceWorker,arguments); } catch {}
   return Promise.reject(new DOMException('Service workers disabled in Active Web V1','SecurityError'));
 };
 for (const container of [globalThis.ServiceWorkerContainer?.prototype, navigator.serviceWorker])
   if (container) try { Object.defineProperty(container,'register',{
     value: refuseWorker, writable:false,configurable:false}); } catch {}
})()"""


def _seconds(deadline):
    aware(deadline)
    return (deadline-datetime.now(timezone.utc)).total_seconds()


def _check(deadline, token=None):
    if token is not None and token.is_cancel_requested():
        raise BrowserLifecycleError(Code.CANCELLED)
    if _seconds(deadline) <= 0:
        raise BrowserLifecycleError(Code.DEADLINE)


def _url(url):
    try:
        return canonical_url(url)
    except Exception:
        raise BrowserLifecycleError(Code.INVALID) from None


def _fingerprint(meta):
    # Values excluded; identity, capabilities, form destination and visible
    # state bound. ElementHandle identity also prevents replacement/rebinding.
    return hashlib.sha256(json.dumps(meta,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


@dataclass
class _Page:
    engine: object = field(repr=False)
    bindings: dict = field(default_factory=dict, repr=False)
    dialogs: deque = field(default_factory=lambda: deque(maxlen=32))
    epoch: int = 0
    expected_download: str | None = None
    permitted_download: object = field(default=None,repr=False)
    download_mime: str = 'application/octet-stream'


@dataclass
class _Context:
    live: Event = field(repr=False)
    broker: object = field(repr=False)
    playwright: object = field(default=None, repr=False)
    browser: object = field(default=None, repr=False)
    context: object = field(default=None, repr=False)
    pages: dict = field(default_factory=dict, repr=False)
    tasks: dict = field(default_factory=dict, repr=False)
    retired: bool = False
    engine_version: str = ''
    browser_version: str = ''
    human_takeover: bool = False


class PlaywrightBrowserAdapter:
    """Private Infrastructure port. Host/ToolRuntime owns every user action.

    broker_factory(session_ref, live_event) must return a fresh AW4 broker whose
    host proof is bounded/nonblocking (do not take Application locks in proxy
    threads). The event is cleared on close/failure. It is lifetime proof only,
    never a grant; actual actions still use AW3 exact claim/approval.
    """
    def __init__(self, broker_factory, *, headful=True):
        if not callable(broker_factory) or type(headful) is not bool:
            raise BrowserLifecycleError(Code.INVALID)
        self._factory, self._headful = broker_factory, headful
        self._contexts, self._retired = {}, set()
        self._loop = asyncio.new_event_loop()
        self._ready, self._closed = Event(), Event()
        self._thread = Thread(target=self._worker, name='nova-playwright-port', daemon=True)
        self._thread.start()
        if not self._ready.wait(1):
            raise BrowserLifecycleError(Code.PORT)

    def _worker(self):
        asyncio.set_event_loop(self._loop)
        self._ready.set()
        try:
            self._loop.run_forever()
        finally:
            self._loop.close(); self._closed.set()

    def _call(self, factory, deadline, token=None):
        _check(deadline, token)
        if self._closed.is_set() or not self._thread.is_alive():
            raise BrowserLifecycleError(Code.PORT)
        async def invoke():
            _check(deadline, token)
            return await factory()
        future = asyncio.run_coroutine_threadsafe(invoke(), self._loop)
        try:
            while True:
                _check(deadline, token)
                try:
                    result = future.result(timeout=min(.02,max(.001,_seconds(deadline))))
                    _check(deadline, token)
                    return result
                except FutureTimeout:
                    if future.done():
                        raise BrowserLifecycleError(Code.PORT) from None
        except BrowserLifecycleError:
            future.cancel(); raise
        except Exception:
            future.cancel(); raise BrowserLifecycleError(Code.PORT) from None

    def _context(self, session):
        ref(session,'bws')
        ctx = self._contexts.get(session)
        if ctx is None or ctx.retired or not ctx.live.is_set() or ctx.browser is None or not ctx.browser.is_connected():
            raise BrowserLifecycleError(Code.STATE)
        return ctx

    def _page(self, session, page):
        ref(page,'bwp')
        ctx=self._context(session); p=ctx.pages.get(page)
        if ctx.human_takeover:
            raise BrowserLifecycleError(Code.BUSY)
        if p is None or p.engine.is_closed():
            raise BrowserLifecycleError(Code.NOT_FOUND)
        return ctx,p

    @staticmethod
    def _dirty(p, preserve=None):
        kept = preserve if isinstance(preserve, tuple) else (preserve,)
        for handle, *_ in p.bindings.values():
            if not any(handle is item for item in kept):
                async def dispose(node=handle):
                    try: await node.dispose()
                    except Exception: pass  # disposed/closed is not an effect
                asyncio.create_task(dispose())
        p.bindings.clear(); p.epoch+=1

    def create_context(self, session, *, deadline, cancellation):
        ref(session,'bws')
        async def create():
            if session in self._contexts or session in self._retired:
                raise BrowserLifecycleError(Code.STATE)
            live=Event(); live.set()
            # Missing optional dependency fails before listener/engine launch.
            try:
                from playwright.async_api import async_playwright
            except ImportError:
                raise BrowserLifecycleError(Code.PORT) from None
            broker=self._factory(session,live)
            if not isinstance(broker,BrowserEgressBroker):
                live.clear();raise BrowserLifecycleError(Code.PORT)
            ctx=_Context(live,broker); self._contexts[session]=ctx
            try:
                config=broker.start()
                proof=probe_browser_broker(broker,timeout_seconds=max(.001,min(1,_seconds(deadline))))
                if proof.network_broker.value is not True:
                    raise BrowserLifecycleError(Code.PORT)
                ctx.playwright=await async_playwright().start()
                ctx.engine_version=version('playwright')
                _check(deadline,cancellation)
                ctx.browser=await ctx.playwright.chromium.launch(
                    headless=not self._headful, args=list(CHROMIUM_ARGS),
                    proxy=dict(server=config.server,username=config.username,password=config.password,bypass=''),
                    timeout=max(1,_seconds(deadline)*1000),
                    env={k:os.environ[k] for k in _ENV_KEYS if k in os.environ})
                ctx.browser_version=ctx.browser.version
                ctx.browser.on('disconnected',live.clear)
                ctx.context=await ctx.browser.new_context(
                    service_workers='block',accept_downloads=True,permissions=[])
                await ctx.context.add_init_script(_HARDEN)
                async def route(request_route):
                    try:
                        if not live.is_set():
                            raise BrowserLifecycleError(Code.STATE)
                        _url(request_route.request.url)
                        await request_route.continue_()
                    except Exception:
                        await request_route.abort('blockedbyclient')
                await ctx.context.route('**/*',route)
                # Both WS/WSS are unsupported in this adapter, rather than
                # offer unverified direct/opaque connections as certified.
                await ctx.context.route_web_socket('**/*',lambda ws: ws.close())
                _check(deadline,cancellation)
            except BaseException:
                live.clear()  # late launch/cancel can never retain egress proof
                raise
        self._call(create,deadline,cancellation)

    def create_page(self, session, page, *, deadline, cancellation):
        ref(page,'bwp')
        async def create():
            ctx=self._context(session)
            if ctx.human_takeover:raise BrowserLifecycleError(Code.BUSY)
            if page in ctx.pages or len(ctx.pages)>=3:
                raise BrowserLifecycleError(Code.QUOTA)
            engine=await ctx.context.new_page(); p=_Page(engine);ctx.pages[page]=p
            def navigated(frame):
                if frame is engine.main_frame:
                    self._dirty(p)
                    # about:blank is internal creation only, never agent target.
                    if frame.url!='about:blank':
                        try: _url(frame.url)
                        except BrowserLifecycleError: asyncio.create_task(engine.close())
            engine.on('framenavigated',navigated)
            async def dialog(d):
                self._dirty(p); p.dialogs.append(d.type+': '+d.message[:512])
                await d.dismiss()  # default refusal, not confirmation/approval
            async def popup(child):
                # No automatic new ref/owner/grant. Host new_page uses AW1 quota.
                self._dirty(p);p.dialogs.append('popup: blocked')
                await child.close()
            async def download(d):
                self._dirty(p)
                if p.expected_download is not None and d.url==p.expected_download and p.permitted_download is None:
                    p.permitted_download=d
                else:
                    p.dialogs.append('download: blocked')
                    await d.cancel()  # no authorized slot, no staging/import
            def response(r):
                if p.expected_download==r.url:
                    mime=r.headers.get('content-type','application/octet-stream').split(';')[0].strip()
                    if mime and len(mime)<=128:p.download_mime=mime
            engine.on('dialog',dialog);engine.on('popup',popup);engine.on('download',download)
            engine.on('response',response)
            engine.on('close',lambda: self._dirty(p))
            _check(deadline,cancellation)
        self._call(create,deadline,cancellation)

    def navigate(self, session, page, url, *, deadline, cancellation):
        """Host initial-navigation seam; not exposed to model/frontend/tools.

        Later user tool composition uses ToolRuntime; link navigation through
        dispatch already uses AW3. URL canonicalization does not grant access:
        the real browser request must still be admitted by the AW4 broker.
        """
        clean=_url(url)
        async def navigate():
            _,p=self._page(session,page);self._dirty(p)
            await p.engine.goto(clean,wait_until='domcontentloaded',timeout=max(1,_seconds(deadline)*1000))
        self._call(navigate,deadline,cancellation)

    async def _meta(self, handle, bound):
        meta=await handle.evaluate(_META,dict(bound=bound))
        caps=tuple(Action(c) for c in meta['caps'])
        return meta,caps

    def capture(self, session, page, *, limits, deadline, cancellation):
        async def capture():
            _,p=self._page(session,page);self._dirty(p);epoch=p.epoch
            text=await p.engine.evaluate(_TEXT,dict(limit=limits.max_text_chars))
            title=(await p.engine.title())[:limits.max_field_chars+1]
            array=await p.engine.evaluate_handle(_NODES,dict(limit=limits.max_elements+1))
            elements=[];bindings={}
            try:
                for handle in (await array.get_properties()).values():
                    node=handle.as_element()
                    if node is None: continue
                    _check(deadline,cancellation)
                    meta,caps=await self._meta(node,limits.max_field_chars)
                    if not meta['visible'] or meta['secret'] or not caps:
                        await node.dispose();continue
                    binding='engine_'+uuid4().hex;fp=_fingerprint(meta)
                    bindings[binding]=(node,fp,meta,limits.max_field_chars,epoch)
                    elements.append(CapturedElement(binding,fp,meta['role'],meta['name'],meta['kind'],
                        caps,meta['state'],meta['href'],True,'NORMAL',meta['tag']=='form'))
                if epoch!=p.epoch: raise BrowserLifecycleError(Code.STATE)
                p.bindings=bindings
                return CapturedPage(p.engine.url,title,text,tuple(elements),tuple(p.dialogs))
            finally:
                await array.dispose()
        return self._call(capture,deadline,cancellation)

    async def _resolve(self, p, binding):
        entry=p.bindings.get(binding)
        if not entry or entry[4]!=p.epoch:return None
        node,fp,old,bound,_=entry
        try:
            meta,caps=await self._meta(node,bound)
            if (p.bindings.get(binding) is not entry or entry[4]!=p.epoch or
                    not meta['connected'] or not meta['visible'] or meta['secret'] or _fingerprint(meta)!=fp):return None
            parts=urlsplit(p.engine.url)
            origin=parts.scheme+'://'+parts.netloc
            return TargetState(binding,fp,origin,caps,True)
        except Exception:return None  # no rebinding, detail or action on failure

    def resolve(self, session, page, engine_binding, *, deadline, cancellation):
        async def resolve():
            _,p=self._page(session,page)
            return await self._resolve(p,engine_binding)
        return self._call(resolve,deadline,cancellation)

    def dispatch(self, request, engine_binding, *, payload, deadline, cancellation, started):
        """Only called by claimed AW3 BrowserActions; never mints/claims grants.

        Fresh proof repeated in worker immediately before one engine attempt.
        Errors AFTER boundary remain UNKNOWN. No retry or heuristic rebind.
        """
        acknowledged=Event()
        async def dispatch():
            ctx,p=self._page(request.browser_session_ref,request.page_ref)
            action=request.action_kind
            page_actions=(Action.NAVIGATE,Action.BACK,Action.FORWARD,Action.SCROLL,Action.WAIT)
            node=meta=None
            if engine_binding is not None:
                proof=await self._resolve(p,engine_binding)
                if proof is None or action not in proof.capabilities:
                    return BrowserDispatchReport(Outcome.FAILED_NO_EFFECT_CONFIRMED,EffectState.NONE,True)
                node,_,meta,_,_=p.bindings[engine_binding]
            elif action not in page_actions:
                return BrowserDispatchReport(Outcome.FAILED_NO_EFFECT_CONFIRMED,EffectState.NONE,True)
            _check(deadline,cancellation)
            timeout=max(1,_seconds(deadline)*1000)
            clean=None
            form_fields=[]
            if action is Action.FORM_SUBMIT:
                from local_cli.application.active_web_service import FormFields
                if isinstance(payload, FormFields):
                    for field_binding, value in payload.fields:
                        proof=await self._resolve(p,field_binding)
                        if proof is None or Action.INPUT_TEXT not in proof.capabilities:
                            return BrowserDispatchReport(Outcome.FAILED_NO_EFFECT_CONFIRMED,EffectState.NONE,True)
                        field_node=p.bindings[field_binding][0]
                        if not await field_node.evaluate('(field, form) => field.form === form', node):
                            return BrowserDispatchReport(Outcome.FAILED_NO_EFFECT_CONFIRMED,EffectState.NONE,True)
                        form_fields.append((field_node,value))
            if action is Action.NAVIGATE:clean=_url(meta['href'] if meta else payload)
            elif action is Action.UPLOAD_FILE and not isinstance(payload,UploadBuffer):
                return BrowserDispatchReport(Outcome.FAILED_NO_EFFECT_CONFIRMED,EffectState.NONE,True)
            elif action is Action.DOWNLOAD:
                if not isinstance(payload,DownloadPermit) or meta is None:
                    return BrowserDispatchReport(Outcome.FAILED_NO_EFFECT_CONFIRMED,EffectState.NONE,True)
                clean=_url(meta['href']);parts=urlsplit(clean)
                if parts.scheme+'://'+parts.netloc!=payload.origin:
                    return BrowserDispatchReport(Outcome.FAILED_NO_EFFECT_CONFIRMED,EffectState.NONE,True)
            elif action is Action.SCROLL and payload not in ('up','down'):
                return BrowserDispatchReport(Outcome.FAILED_NO_EFFECT_CONFIRMED,EffectState.NONE,True)
            elif action is Action.WAIT:
                try: wait=float(payload)
                except (TypeError,ValueError): wait=float('nan')
                if not math.isfinite(wait) or not 0<wait<=_seconds(deadline):
                    return BrowserDispatchReport(Outcome.FAILED_NO_EFFECT_CONFIRMED,EffectState.NONE,True)
            elif action is Action.PRESS_KEY and payload not in ('Enter','Tab','Escape','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Space'):
                return BrowserDispatchReport(Outcome.FAILED_NO_EFFECT_CONFIRMED,EffectState.NONE,True)
            elif action not in (*page_actions,Action.CLICK,Action.INPUT_TEXT,Action.SELECT_OPTION,Action.FORM_SUBMIT,Action.PRESS_KEY,Action.UPLOAD_FILE):
                return BrowserDispatchReport(Outcome.FAILED_NO_EFFECT_CONFIRMED,EffectState.NONE,True)
            self._dirty(p,preserve=(node,*(field_node for field_node,_ in form_fields)))
            started();acknowledged.set()
            task=asyncio.current_task();ctx.tasks[task]=request.page_ref
            try:
                if action is Action.NAVIGATE:await p.engine.goto(clean,wait_until='domcontentloaded',timeout=timeout)
                elif action is Action.CLICK:await node.click(timeout=timeout,no_wait_after=True)
                elif action is Action.INPUT_TEXT:await node.fill(payload,timeout=timeout)
                elif action is Action.SELECT_OPTION:await node.select_option(value=payload,timeout=timeout)
                elif action is Action.PRESS_KEY:await node.press(payload,timeout=timeout)
                elif action is Action.UPLOAD_FILE:
                    await node.set_input_files(dict(name=payload.selection.filename,
                        mimeType=payload.selection.mime,buffer=payload.buffer),timeout=timeout)
                elif action is Action.DOWNLOAD:
                    p.expected_download=clean;p.permitted_download=None;p.download_mime='application/octet-stream'
                    download=None
                    try:
                        async with p.engine.expect_download(timeout=timeout) as info:
                            try:await p.engine.goto(clean,wait_until='domcontentloaded',timeout=timeout)
                            except Exception:pass  # Download aborts navigation; event must still prove success.
                        download=await info.value
                        if download is not p.permitted_download or await download.failure() is not None:
                            raise BrowserLifecycleError(Code.PORT)
                        path=await download.path()
                        # Reuse only the hardened bounded host file reader,
                        # never Knowledge extraction/store/import.
                        from local_cli.infrastructure.knowledge_acquisition import LocalHostFileAcquisition
                        def read():
                            return b''.join(LocalHostFileAcquisition(max_bytes=payload.max_bytes).read(str(path),
                                cancelled=lambda:cancellation.is_cancel_requested() or _seconds(deadline)<=0 or not ctx.live.is_set(),
                                progress=lambda size:None))
                        data=await asyncio.to_thread(read)
                        _check(deadline,cancellation)
                        payload.stage(data,download.suggested_filename,p.download_mime)
                    finally:
                        p.expected_download=None;p.permitted_download=None
                        if download is not None:
                            try:await download.delete()
                            except Exception:pass  # Receipt remains UNKNOWN if outer deadline/cancel fails.
                elif action is Action.BACK:await p.engine.go_back(wait_until='domcontentloaded',timeout=timeout)
                elif action is Action.FORWARD:await p.engine.go_forward(wait_until='domcontentloaded',timeout=timeout)
                elif action is Action.SCROLL:
                    await p.engine.evaluate('(direction) => window.scrollBy(0,direction*innerHeight)',-1 if payload=='up' else 1)
                elif action is Action.WAIT:await asyncio.sleep(wait)
                elif action is Action.FORM_SUBMIT:
                    for field_node,value in form_fields:
                        await field_node.fill(value,timeout=timeout)
                    # Fixed adapter code, never a snippet from model/page.
                    await node.evaluate('(form) => form.requestSubmit()')
                _check(deadline,cancellation)
                return BrowserDispatchReport(Outcome.SUCCEEDED_OBSERVED,
                    EffectState.NONE if action in page_actions else EffectState.APPLIED)
            except BaseException:
                return BrowserDispatchReport(Outcome.UNKNOWN,EffectState.UNKNOWN)
            finally:
                ctx.tasks.pop(task,None)
                if node:
                    try:await node.dispose()
                    except Exception:pass
        try:return self._call(dispatch,deadline,cancellation)
        except BrowserLifecycleError:
            return BrowserDispatchReport(Outcome.UNKNOWN,EffectState.UNKNOWN) if acknowledged.is_set() else BrowserDispatchReport(Outcome.NOT_STARTED,EffectState.NONE,True)

    def begin_takeover(self, session, page, *, deadline):
        """Private host handoff. No credential API, selectors or login automation."""
        async def begin():
            ctx=self._context(session)
            if not self._headful or ctx.human_takeover or ctx.tasks or page not in ctx.pages:
                raise BrowserLifecycleError(Code.STATE)
            ctx.human_takeover=True
            for p in ctx.pages.values():self._dirty(p)
            await ctx.pages[page].engine.bring_to_front()
        return self._call(begin,deadline)

    def end_takeover(self, session, *, deadline):
        async def end():
            ctx=self._context(session)
            if not ctx.human_takeover:raise BrowserLifecycleError(Code.STATE)
            for p in ctx.pages.values():self._dirty(p)
            ctx.human_takeover=False
        return self._call(end,deadline)

    def cancel_page(self, session, page, *, operation_id, deadline):
        async def cancel():
            ctx,p=self._page(session,page);self._dirty(p)
            # Acknowledges cancellation of work only, never remote rollback.
            for task,task_page in tuple(ctx.tasks.items()):
                if task_page==page:task.cancel()
            return True
        return self._call(cancel,deadline)

    def close_page(self, session, page, *, deadline):
        async def close():
            ctx=self._contexts.get(session)
            if ctx is None:return session in self._retired
            p=ctx.pages.get(page)
            if p is None:return True
            self._dirty(p)
            await p.engine.close()
            if not p.engine.is_closed():return False
            del ctx.pages[page];return True
        try:return self._call(close,deadline)
        except BrowserLifecycleError:return False

    def close_context(self, session, *, deadline):
        async def close():
            ctx=self._contexts.get(session)
            if ctx is None:return session in self._retired
            ctx.retired=True;ctx.live.clear()
            for task in tuple(ctx.tasks):task.cancel()
            confirmed=ctx.browser is not None and ctx.browser.is_connected()
            try:
                if ctx.context:await ctx.context.close()
                if ctx.browser:await ctx.browser.close()
                if ctx.playwright:await ctx.playwright.stop()
            except Exception:confirmed=False
            # Do not block the asyncio event loop waiting for proxy IO workers.
            remaining=max(.001,_seconds(deadline))
            receipt=await asyncio.to_thread(ctx.broker.close,timeout_seconds=remaining)
            confirmed=confirmed and receipt.confirmed and not ctx.browser.is_connected()
            if confirmed:
                self._contexts.pop(session,None);self._retired.add(session)
            return bool(confirmed)
        try:return self._call(close,deadline)
        except BrowserLifecycleError:return False

    def capabilities(self, session, *, deadline):
        async def capture():
            ctx=self._context(session)
            proof=probe_browser_broker(ctx.broker,timeout_seconds=max(.001,min(1,_seconds(deadline))))
            return BrowserCapabilitySnapshot(
                engine=Observation.known('PLAYWRIGHT_CHROMIUM'),engine_version=Observation.known(ctx.engine_version),
                browser_version=Observation.known(ctx.browser_version),headful=Observation.known(self._headful),
                control_class=Observation.known('HOST_UNISOLATED'),
                network_broker=proof.network_broker,
                # These are adapter contracts, not network exclusivity proof.
                # No persistent context/profile/storageState API exists here.
                manual_takeover=Observation.known(self._headful),
                upload=Observation.known(True), download=Observation.known(True),
                persistent_session=Observation.known(False),
                platform=Observation.known(sys.platform), max_pages=Observation.known(3),
                screenshot=Observation.known(False),
                public_only=Observation.unknown('engine exclusive egress not certified'),
                available=Observation.unknown('AW5 adapter is not ACTIVE_WEB_CORE READY'))
        return self._call(capture,deadline)

    def inspect_control_environment(self, session, page, *, deadline):
        """Fixed host probe only; no caller script/selector/URL or model API.

        A page-local check is not proof of engine-wide exclusive egress. The
        probe report preserves that distinction; capabilities remain UNKNOWN.
        """
        async def inspect():
            ctx,p=self._page(session,page)
            values=await p.engine.evaluate("""() => ({
                rtc: typeof globalThis.RTCPeerConnection,
                prefixedRtc: typeof globalThis.webkitRTCPeerConnection,
                secureContext: globalThis.isSecureContext,
                webTransport: typeof globalThis.WebTransport,
                serviceWorkerApi: typeof navigator.serviceWorker
            })""")
            return dict(engine=ctx.browser_version, sdk=ctx.engine_version,
                fixedArguments=list(CHROMIUM_ARGS), pageEnvironment=values,
                brokerLive=ctx.live.is_set(), browserConnected=ctx.browser.is_connected())
        return self._call(inspect,deadline)

    def shutdown(self, *, deadline):
        """Host cleanup only. False never masquerades as confirmed CLOSED."""
        for session in tuple(self._contexts):
            if not self.close_context(session,deadline=deadline):return False
        if self._closed.is_set():return True
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(max(0,_seconds(deadline)))
        return self._closed.is_set()
