"""WEBVIEW2_NATIVE_HOST_TEST: real installed engine; offline about:blank only."""
from datetime import datetime, timedelta, timezone
import json
import os
import subprocess
import time
from threading import Event

import pytest

from local_cli.infrastructure.active_web.webview2_adapter import WebView2BrowserAdapter, WebView2PortError, WebView2HostClient
from local_cli.infrastructure.active_web.host_ipc_protocol import opaque, HostIpcError, IpcCode
from local_cli.infrastructure.active_web.browser_host import HostState
from local_cli.infrastructure.active_web.webview2_ipc import EngineCode
from local_cli.infrastructure.active_web.host_named_pipe import NamedPipeTransport
from local_cli.infrastructure.active_web.host_process_job import ProcessJob
from local_cli.infrastructure.active_web import webview2_ipc as wire


def deadline(): return datetime.now(timezone.utc)+timedelta(seconds=20)


@pytest.fixture
def port(host_build,tmp_path):
    assert os.name=='nt'
    a=WebView2BrowserAdapter(*host_build,tmp_path)
    yield a
    for c in a._sessions.values():
        c.shutdown(timeout_ms=10000)
        assert c.cleanup_confirmed


def create(a):
    s,p=opaque('bws'),opaque('bwp')
    a.create_context(s,deadline=deadline(),cancellation=None)
    a.create_page(s,p,deadline=deadline(),cancellation=None)
    return s,p


def test_real_runtime_two_unique_sessions_owned_pages_and_cleanup(port,tmp_path):
    s,p=create(port); other,q=create(port)
    c,d=port._sessions[s],port._sessions[other]
    assert c.udf!=d.udf and c.udf.is_dir() and d.udf.is_dir()
    assert c.instance!=d.instance and c.process.pid!=d.process.pid
    m=port.runtime_metadata(s,deadline=deadline()); n=port.runtime_metadata(other,deadline=deadline())
    assert m['sdkVersion']=='1.0.4258.31' and m['runtimeVersion'] and m['architecture']=='X64'
    assert m['udfIdentity']!=n['udfIdentity']
    assert all(c.job.contains(x['pid']) for x in m['processes'])
    assert not {x['pid'] for x in m['processes']} & {x['pid'] for x in n['processes']}
    assert m['configuration']['initialContent']=='about:blank'
    acl=subprocess.run(['C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-NonInteractive','-Command',
        '$ErrorActionPreference="Stop"; $a=Get-Acl -LiteralPath "'+str(c.udf)+'"; [pscustomobject]@{protected=$a.AreAccessRulesProtected; rules=@($a.Access|ForEach-Object{[string]$_.IdentityReference})}|ConvertTo-Json -Compress'],
        env={k:v for k,v in os.environ.items() if k.upper()!='PSMODULEPATH'},
        capture_output=True,text=True,timeout=10)
    assert acl.returncode==0,acl.stderr
    acl_result=json.loads(acl.stdout);assert acl_result['protected'] is True and len(acl_result['rules'])==1
    (tmp_path/'runtime.json').write_text(json.dumps(dict(runtime=m,secondRuntime=n,hostPid=c.process.pid,
        ownership='PID-bound Named Pipe + lifetime Job Object',available='UNKNOWN',publicOnly='UNKNOWN',
        networkEgressControl='UNKNOWN',externalProtocolGuard='UNKNOWN',udfAcl=acl_result),indent=2),encoding='utf-8')
    assert port.page_metadata(s,p,deadline=deadline())['contextEpoch']==1
    with pytest.raises(WebView2PortError): port.page_metadata(other,p,deadline=deadline())
    assert port.close_page(s,p,deadline=deadline())
    with pytest.raises(WebView2PortError): port.create_page(s,p,deadline=deadline(),cancellation=None)
    assert port.close_context(s,deadline=deadline()) and not c.udf.exists() and c.process.poll()==0
    assert port.close_context(other,deadline=deadline()) and not d.udf.exists()
    with pytest.raises(WebView2PortError): port.create_context(s,deadline=deadline(),cancellation=None)
    assert c.history==['NOT_STARTED','STARTING','READY','STOPPING','STOPPED']


def test_three_owned_pages_limit(port):
    s,p=create(port)
    for _ in range(2): port.create_page(s,opaque('bwp'),deadline=deadline(),cancellation=None)
    with pytest.raises(WebView2PortError) as e: port.create_page(s,opaque('bwp'),deadline=deadline(),cancellation=None)
    assert e.value.engine_code is EngineCode.OWNERSHIP_MISMATCH
    assert port._sessions[s].state is HostState.FAILED


def test_host_crash_invalidates_no_retry_no_orphan_udf(port):
    s,p=create(port); c=port._sessions[s]
    port.runtime_metadata(s,deadline=deadline()); pid=c.process.pid
    c.process.kill();c.process.wait(timeout=5)
    with pytest.raises(WebView2PortError) as e: port.page_metadata(s,p,deadline=deadline())
    assert e.value.engine_code is IpcCode.PROCESS_EXIT_UNEXPECTED
    assert c.state is HostState.FAILED and c.process.pid==pid and c.cleanup_confirmed and not c.udf.exists()
    with pytest.raises(WebView2PortError): port.page_metadata(s,p,deadline=deadline())


def test_disconnect_invalidates_no_fallback(port):
    s,p=create(port);c=port._sessions[s];c.transport.close()
    with pytest.raises(WebView2PortError): port.page_metadata(s,p,deadline=deadline())
    assert c.state is HostState.FAILED and c.cleanup_confirmed and not c.udf.exists()


def test_native_cancel_and_deadline_do_not_publish_late_resource(port):
    s,p=create(port);c=port._sessions[s]
    assert c.cancel_last()['disposition']=='ALREADY_COMPLETED'
    cancel=Event();cancel.set()
    with pytest.raises(HostIpcError) as e: c.call('page_create',page=opaque('bwp'),cancel=cancel)
    assert e.value.code is IpcCode.CANCELLED and c.state is HostState.FAILED and c.cleanup_confirmed


def test_native_timeout_no_automatic_retry(port):
    s,p=create(port);c=port._sessions[s]
    with pytest.raises(HostIpcError) as e: c.call('page_create',page=opaque('bwp'),timeout_ms=0)
    assert e.value.code is IpcCode.TIMEOUT
    assert c.state is HostState.FAILED and c.cleanup_confirmed and not c.udf.exists()


def test_browser_process_failure_is_typed_and_invalidates(port):
    import ctypes
    s,p=create(port);c=port._sessions[s];metadata=port.runtime_metadata(s,deadline=deadline())
    browser=next(x['pid'] for x in metadata['processes'] if x['kind']=='Browser')
    assert c.job.contains(browser)
    k=c.job.api;k.TerminateProcess.argtypes=(ctypes.c_void_p,ctypes.c_uint);k.TerminateProcess.restype=ctypes.c_int
    h=k.OpenProcess(1,False,browser);assert h
    try: assert k.TerminateProcess(h,1)
    finally:k.CloseHandle(h)
    time.sleep(.3) # bounded harness wait for the engine's ProcessFailed callback.
    with pytest.raises(WebView2PortError) as e:port.page_metadata(s,p,deadline=deadline())
    assert e.value.engine_code is EngineCode.WEBVIEW2_PROCESS_FAILED
    assert c.state is HostState.FAILED and c.cleanup_confirmed and not c.udf.exists()


def test_real_udf_file_lock_reports_cleanup_unconfirmed(port):
    import ctypes
    s,p=create(port);c=port._sessions[s]
    port.runtime_metadata(s,deadline=deadline())
    lockfile=c.udf/'controlled-lock';lockfile.write_text('synthetic',encoding='utf-8')
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.CreateFileW.argtypes=(ctypes.c_wchar_p,ctypes.c_uint,ctypes.c_uint,ctypes.c_void_p,ctypes.c_uint,ctypes.c_uint,ctypes.c_void_p)
    k.CreateFileW.restype=ctypes.c_void_p;k.CloseHandle.argtypes=(ctypes.c_void_p,)
    h=k.CreateFileW(str(lockfile),0x80000000,0,None,3,0,None);assert h not in (None,ctypes.c_void_p(-1).value)
    try:
        with pytest.raises(WebView2PortError) as e:port.close_context(s,deadline=deadline())
        assert e.value.engine_code is IpcCode.CLEANUP_UNCONFIRMED
        assert not c.cleanup_confirmed and c.state is HostState.CLEANUP_UNCONFIRMED and c.udf.exists()
    finally:k.CloseHandle(h)
    # Explicit maintenance cleanup, not an operation retry or false earlier PASS.
    c._cleanup();assert c.cleanup_confirmed and not c.udf.exists()


def test_real_sdk_missing_runtime_override_is_fail_closed(host_build,tmp_path):
    # Harness-only process environment override; product startup strips WEBVIEW2_*.
    # No Runtime uninstall/install, registry change, or application flag.
    c=WebView2HostClient(*host_build,opaque('bws'),tmp_path)
    env=dict(os.environ,WEBVIEW2_BROWSER_EXECUTABLE_FOLDER=str(tmp_path/'nonexistent-runtime'))
    c.process=subprocess.Popen([str(host_build[0]),str(host_build[1]),'--pipe',c._pipe_name,
        '--owner-pid',str(os.getpid()),'--session',c.session,'--instance',c.instance,*c._bootstrap_arguments()],
        env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW)
    c.job=ProcessJob(c.process)
    try:
        end=time.monotonic()+5
        c.transport=NamedPipeTransport.connect(c._pipe_name,c.process.pid,end=end,process=c.process)
        r=wire.envelope(c.session,dict(command='handshake',clientPid=os.getpid(),expectedHostPid=c.process.pid,
            hostInstanceRef=c.instance,protocol='nova-browser-host-ipc'))
        hello=c._exchange(r,end);assert hello['activeWebAvailable'] is False
        wire.correlate(r,c._receive(end=end),event='HOST_READY');c._state(HostState.READY)
        with pytest.raises(HostIpcError) as e:c.call('session_create')
        assert e.value.code is EngineCode.RUNTIME_ABSENT and not c.udf.exists() and c.cleanup_confirmed
    finally:c._cleanup()


@pytest.mark.parametrize('mutation', ['version','extra','unknown','wrong_session','duplicate'])
def test_native_v2_protocol_rejects_before_effect(host_build,tmp_path,mutation):
    import struct
    c=WebView2HostClient(*host_build,opaque('bws'),tmp_path);c.start()
    try:
        r=wire.envelope(c.session,{'command':'ping'})
        if mutation=='version':r['schemaVersion']=3
        elif mutation=='extra':r['payload']['grant']='synthetic'
        elif mutation=='unknown':r['payload']['command']='navigate'
        elif mutation=='wrong_session':r['browserSessionRef']=opaque('bws')
        elif mutation=='duplicate':r=c._last
        body=json.dumps(r).encode('utf-8');end=time.monotonic()+5
        c.transport.write(struct.pack('<I',len(body))+body,end=end)
        response=c._receive(end=end)
        assert response['error']['code'] in ('PROTOCOL_MISMATCH','INVALID_MESSAGE','UNSUPPORTED_COMMAND','CORRELATION_MISMATCH','DUPLICATE_REQUEST')
        assert not c.udf.exists()
    finally:c._cleanup();assert c.cleanup_confirmed


def test_existing_udf_is_never_reused(host_build,tmp_path):
    c=WebView2HostClient(*host_build,opaque('bws'),tmp_path);c.udf.mkdir()
    marker=c.udf/'unowned-marker';marker.write_text('unowned',encoding='utf-8')
    c.start()
    try:
        with pytest.raises(HostIpcError) as e:c.call('session_create')
        assert e.value.code is EngineCode.OWNERSHIP_MISMATCH
        # Refusal must preserve a pre-existing folder, not remove someone else's UDF.
        assert marker.read_text(encoding='utf-8')=='unowned'
    finally:
        with pytest.raises(HostIpcError):c.shutdown()
        assert c.job.active()==0 and c.state is HostState.CLEANUP_UNCONFIRMED
        c.job.close() # Harness releases an empty lifetime handle; unowned data stays.
