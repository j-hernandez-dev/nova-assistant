"""HOST_PROCESS_TEST: real .NET process/Named Pipes on Windows; no WebView2."""
import ctypes
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
from threading import Event, Timer
import time

import pytest

from local_cli.infrastructure.active_web.browser_host import BrowserHostClient, HostState
from local_cli.infrastructure.active_web.host_named_pipe import NamedPipeTransport
from local_cli.infrastructure.active_web.host_ipc_protocol import (
    HostIpcError,IpcCode,MAX_FRAME_BYTES,PROTOCOL,encode,decode,envelope,opaque,correlate,
)


@pytest.fixture
def client(host_build):
    c=BrowserHostClient(*host_build,opaque('bws'))
    yield c
    c.shutdown()


@pytest.fixture
def raw(host_build):
    c=BrowserHostClient(*host_build,opaque('bws'))
    c.process=subprocess.Popen([str(host_build[0]),str(host_build[1]),'--pipe',c._pipe_name,
        '--owner-pid',str(os.getpid()),'--session',c.session,'--instance',c.instance],
        stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW)
    c.transport=NamedPipeTransport.connect(c._pipe_name,c.process.pid,end=time.monotonic()+5,process=c.process)
    yield c
    c._cleanup()


def handshake(c):
    r=envelope(c.session,dict(command='handshake',clientPid=os.getpid(),expectedHostPid=c.process.pid,
                            hostInstanceRef=c.instance,protocol=PROTOCOL))
    c.transport.write(encode(r),end=time.monotonic()+5)
    reply=c.transport.receive(end=time.monotonic()+5)
    result=correlate(r,reply)
    correlate(r,c.transport.receive(end=time.monotonic()+5),event='HOST_READY')
    assert decode(encode(reply)[4:])==reply
    return result


def send_raw(c,m):
    body=json.dumps(m,separators=(',',':')).encode()
    c.transport.write(struct.pack('<I',len(body))+body,end=time.monotonic()+5)
    return c.transport.receive(end=time.monotonic()+5)


def test_success_handshake_health_shutdown_and_serialization(client):
    hello=client.start()
    assert hello['hostPid']==client.process.pid and hello['ownerPid']==os.getpid()
    assert hello['ipcVersion']==1 and hello['activeWebAvailable'] is False
    assert client.ping()['hostPid']==client.process.pid
    client.shutdown()
    assert client.history==['NOT_STARTED','STARTING','READY','STOPPING','STOPPED']
    assert client.process.returncode==0 and client.transport.handle is None
    client.shutdown()


def test_completed_health_cancellation_is_not_rollback(client):
    client.start();client.ping()
    assert client.cancel_last()=={'kind':'cancel','disposition':'ALREADY_COMPLETED'}
    assert client.ping()['state']=='READY'


def test_cancel_before_dispatch_closes_without_late_results(client):
    client.start();cancel=Event();cancel.set()
    with pytest.raises(HostIpcError) as e:client.ping(cancel=cancel)
    assert e.value.code is IpcCode.CANCELLED
    assert client.state is HostState.FAILED and client.process.poll() is not None
    with pytest.raises(HostIpcError):client.ping()


def test_zero_timeout_has_no_retry_or_late_result(client):
    client.start()
    with pytest.raises(HostIpcError) as e:client.ping(timeout_ms=0)
    assert e.value.code is IpcCode.TIMEOUT and client.transport.handle is None
    assert client.state is HostState.FAILED and client.process.poll() is not None


@pytest.mark.parametrize('version',[2,0,True,1.0,'1'])
def test_native_version_mismatch_fail_closed(raw,version):
    m=envelope(raw.session,dict(command='handshake',clientPid=os.getpid(),expectedHostPid=raw.process.pid,
                              hostInstanceRef=raw.instance,protocol=PROTOCOL));m['schemaVersion']=version
    r=send_raw(raw,m)
    assert r['messageType']=='protocol_error'
    assert r['error']['code'] in ('PROTOCOL_MISMATCH','INVALID_MESSAGE')
    assert raw.process.wait(timeout=3)!=0


@pytest.mark.parametrize('body',[b'{',b'\xff',b'null',b'[]',b'{"x":NaN}'])
def test_native_malformed_frame_rejected(raw,body):
    raw.transport.write(struct.pack('<I',len(body))+body,end=time.monotonic()+5)
    reply=raw.transport.receive(end=time.monotonic()+5)
    assert reply['messageType']=='protocol_error'
    assert raw.process.wait(timeout=3)!=0


@pytest.mark.parametrize('length',[0,MAX_FRAME_BYTES+1,2**32-1])
def test_native_oversized_frame_denied_before_body_allocation(raw,length):
    raw.transport.write(struct.pack('<I',length),end=time.monotonic()+5)
    reply=raw.transport.receive(end=time.monotonic()+5)
    assert reply['error']['code']=='OVERSIZED_FRAME'
    assert raw.process.wait(timeout=3)!=0


def test_native_partial_frame_timeout(raw):
    raw.transport.write(struct.pack('<I',200)+b'{',end=time.monotonic()+1)
    assert raw.process.wait(timeout=7)==14


@pytest.mark.parametrize('field',['browserSessionRef','clientPid','expectedHostPid','hostInstanceRef'])
def test_native_wrong_handshake_correlation(raw,field):
    m=envelope(raw.session,dict(command='handshake',clientPid=os.getpid(),expectedHostPid=raw.process.pid,
                              hostInstanceRef=raw.instance,protocol=PROTOCOL))
    if field=='browserSessionRef':m[field]=opaque('bws')
    elif field=='hostInstanceRef':m['payload'][field]=opaque('bhi')
    else:m['payload'][field]+=1
    try:
        r=send_raw(raw,m)
        assert r['error']['code']=='CORRELATION_MISMATCH'
    except HostIpcError as e:
        assert e.code is IpcCode.DISCONNECTED
    assert raw.process.wait(timeout=3)==13


def test_native_duplicate_request_id(raw):
    handshake(raw);m=envelope(raw.session,{'command':'ping'})
    assert send_raw(raw,m)['result']['state']=='READY'
    assert send_raw(raw,m)['error']['code']=='DUPLICATE_REQUEST'
    assert raw.process.wait(timeout=3)==13


def test_native_duplicate_operation_id(raw):
    handshake(raw);m=envelope(raw.session,{'command':'ping'});send_raw(raw,m)
    m['requestId']=opaque('bhr')
    assert send_raw(raw,m)['error']['code']=='DUPLICATE_REQUEST'


@pytest.mark.parametrize('kind',['navigate','execute','grant',''])
def test_native_unknown_message(raw,kind):
    m=envelope(raw.session,{'command':'ping'});m['messageType']=kind
    assert send_raw(raw,m)['error']['code']=='UNKNOWN_MESSAGE'


@pytest.mark.parametrize('field',['grant','approvalToken','password','cookie','javascript','available'])
def test_native_extra_authority_fields_rejected(raw,field):
    m=envelope(raw.session,{'command':'ping'});m[field]='synthetic-untrusted'
    assert send_raw(raw,m)['messageType']=='protocol_error'
    assert raw.process.wait(timeout=3)==13


def test_native_secret_like_payload_rejected(raw):
    m=envelope(raw.session,{'command':'ping'});m['payload']['providerCredentials']='synthetic-only'
    assert send_raw(raw,m)['error']['code']=='INVALID_MESSAGE'


def test_native_reserved_browser_returns_unsupported_not_ready(raw):
    handshake(raw)
    m=envelope(raw.session,{'command':'reserved_browser'},page=opaque('bwp'))
    assert send_raw(raw,m)['error']['code']=='UNSUPPORTED_COMMAND'
    assert send_raw(raw,envelope(raw.session,{'command':'ping'}))['result']['state']=='READY'


def test_native_expired_deadline_is_not_health_success(raw):
    handshake(raw);m=envelope(raw.session,{'command':'ping'});m['deadline']=1
    assert send_raw(raw,m)['error']['code']=='TIMEOUT'


def test_native_handshake_required_before_health(raw):
    assert send_raw(raw,envelope(raw.session,{'command':'ping'}))['error']['code']=='HANDSHAKE_FAILED'
    assert raw.process.wait(timeout=3)==13


def test_native_protocol_identity_mismatch(raw):
    m=envelope(raw.session,dict(command='handshake',clientPid=os.getpid(),expectedHostPid=raw.process.pid,
                              hostInstanceRef=raw.instance,protocol=PROTOCOL))
    m['payload']['protocol']='other-protocol'
    assert send_raw(raw,m)['error']['code']=='PROTOCOL_MISMATCH'


def test_native_duplicate_json_keys_are_rejected(raw):
    m=envelope(raw.session,{'command':'ping'})
    body=json.dumps(m,separators=(',',':')).encode().replace(b'{',b'{"schemaVersion":1,',1)
    raw.transport.write(struct.pack('<I',len(body))+body,end=time.monotonic()+3)
    assert raw.transport.receive(end=time.monotonic()+3)['error']['code']=='INVALID_MESSAGE'


def test_native_pipe_dacl_is_protected_network_denied_and_user_only(client):
    client.start()
    from ctypes import wintypes as w
    a=ctypes.WinDLL('advapi32',use_last_error=True)
    a.GetKernelObjectSecurity.argtypes=(w.HANDLE,w.DWORD,ctypes.c_void_p,w.DWORD,ctypes.POINTER(w.DWORD))
    a.GetKernelObjectSecurity.restype=w.BOOL
    a.GetSecurityDescriptorControl.argtypes=(ctypes.c_void_p,ctypes.POINTER(w.WORD),ctypes.POINTER(w.DWORD))
    a.GetSecurityDescriptorControl.restype=w.BOOL
    a.GetSecurityDescriptorDacl.argtypes=(ctypes.c_void_p,ctypes.POINTER(w.BOOL),ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(w.BOOL))
    a.GetSecurityDescriptorDacl.restype=w.BOOL
    a.GetAce.argtypes=(ctypes.c_void_p,w.DWORD,ctypes.POINTER(ctypes.c_void_p));a.GetAce.restype=w.BOOL
    a.ConvertSidToStringSidW.argtypes=(ctypes.c_void_p,ctypes.POINTER(w.LPWSTR));a.ConvertSidToStringSidW.restype=w.BOOL
    a.OpenProcessToken.argtypes=(w.HANDLE,w.DWORD,ctypes.POINTER(w.HANDLE));a.OpenProcessToken.restype=w.BOOL
    a.GetTokenInformation.argtypes=(w.HANDLE,w.DWORD,ctypes.c_void_p,w.DWORD,ctypes.POINTER(w.DWORD));a.GetTokenInformation.restype=w.BOOL
    k=ctypes.WinDLL('kernel32');k.LocalFree.argtypes=(ctypes.c_void_p,);k.LocalFree.restype=ctypes.c_void_p
    required=w.DWORD();a.GetKernelObjectSecurity(client.transport.handle,4,None,0,ctypes.byref(required))
    assert required.value>0
    sd=ctypes.create_string_buffer(required.value)
    assert a.GetKernelObjectSecurity(client.transport.handle,4,sd,required.value,ctypes.byref(required))
    control=w.WORD();revision=w.DWORD()
    assert a.GetSecurityDescriptorControl(sd,ctypes.byref(control),ctypes.byref(revision))
    assert control.value & 0x1000  # SE_DACL_PROTECTED, not a null/inherited DACL.
    present,defaulted=w.BOOL(),w.BOOL();dacl=ctypes.c_void_p()
    assert a.GetSecurityDescriptorDacl(sd,ctypes.byref(present),ctypes.byref(dacl),ctypes.byref(defaulted))
    assert present.value and dacl.value and not defaulted.value
    class Acl(ctypes.Structure):
        _fields_=[('Revision',w.BYTE),('Sbz1',w.BYTE),('Size',w.WORD),('Count',w.WORD),('Sbz2',w.WORD)]
    assert Acl.from_address(dacl.value).Count==2
    def sid_text(pointer):
        out=w.LPWSTR();assert a.ConvertSidToStringSidW(pointer,ctypes.byref(out))
        try:return out.value
        finally:k.LocalFree(ctypes.cast(out,ctypes.c_void_p))
    k.GetCurrentProcess.restype=w.HANDLE
    k.CloseHandle.argtypes=(w.HANDLE,);k.CloseHandle.restype=w.BOOL
    token=w.HANDLE();assert a.OpenProcessToken(k.GetCurrentProcess(),8,ctypes.byref(token))
    try:
        size=w.DWORD();a.GetTokenInformation(token,1,None,0,ctypes.byref(size))
        info=ctypes.create_string_buffer(size.value)
        assert a.GetTokenInformation(token,1,info,size.value,ctypes.byref(size))
        user=sid_text(ctypes.c_void_p.from_buffer(info).value)
    finally:k.CloseHandle(token)
    expected=[(1,'S-1-5-2'),(0,user)]  # ACCESS_DENIED NETWORK, ACCESS_ALLOWED actual TokenUser.
    for index,(ace_type,sid) in enumerate(expected):
        ace=ctypes.c_void_p();assert a.GetAce(dacl,index,ctypes.byref(ace))
        assert w.BYTE.from_address(ace.value).value==ace_type
        assert w.BYTE.from_address(ace.value+1).value==0  # No inheritance flags.
        # Windows maps generic GA to the file/pipe object's FILE_ALL_ACCESS.
        assert w.DWORD.from_address(ace.value+4).value==0x001F01FF
        assert sid_text(ace.value+8)==sid


def test_native_owner_exit_terminates_host_without_orphan(host_build):
    # Test-only owner stdout captures PID; browser-host stdout is still DEVNULL.
    code=("import json,time; from local_cli.infrastructure.active_web.browser_host import BrowserHostClient; "
          "from local_cli.infrastructure.active_web.host_ipc_protocol import opaque; "
          f"c=BrowserHostClient({str(host_build[0])!r},{str(host_build[1])!r},opaque('bws')); "
          "c.start();print(json.dumps({'hostPid':c.process.pid}),flush=True);time.sleep(30)")
    owner=subprocess.Popen([sys.executable,'-B','-c',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                           text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    handle=None
    try:
        pid=json.loads(owner.stdout.readline())['hostPid']
        from ctypes import wintypes as w
        k=ctypes.WinDLL('kernel32',use_last_error=True)
        k.OpenProcess.argtypes=(w.DWORD,w.BOOL,w.DWORD);k.OpenProcess.restype=w.HANDLE
        k.WaitForSingleObject.argtypes=(w.HANDLE,w.DWORD);k.WaitForSingleObject.restype=w.DWORD
        k.CloseHandle.argtypes=(w.HANDLE,);k.CloseHandle.restype=w.BOOL
        k.TerminateProcess.argtypes=(w.HANDLE,w.UINT);k.TerminateProcess.restype=w.BOOL
        handle=k.OpenProcess(0x100001,False,pid);assert handle
        owner.kill();owner.wait(timeout=3)
        assert k.WaitForSingleObject(handle,3000)==0
    finally:
        if owner.poll() is None:owner.kill();owner.wait(timeout=3)
        if handle:
            if k.WaitForSingleObject(handle,0)==258:k.TerminateProcess(handle,99);k.WaitForSingleObject(handle,3000)
            k.CloseHandle(handle)
        owner.stdout.close();owner.stderr.close()


def test_native_bad_cancel_correlation(raw):
    handshake(raw)
    m=envelope(raw.session,{'targetRequestId':opaque('bhr'),'targetOperationId':opaque('op')},kind='cancel')
    assert send_raw(raw,m)['error']['code']=='CORRELATION_MISMATCH'


def test_native_second_connection_rejected(client):
    client.start()
    with pytest.raises(HostIpcError) as e:
        NamedPipeTransport.connect(client._pipe_name,client.process.pid,end=time.monotonic()+.05,process=client.process)
    assert e.value.code is IpcCode.TIMEOUT
    assert client.ping()['state']=='READY'


def test_native_server_pid_mismatch_rejects_pipe(host_build):
    # OS-reported server PID, not the reply's claimed PID, is authoritative for correlation.
    c=BrowserHostClient(*host_build,opaque('bws'))
    proc=subprocess.Popen([str(host_build[0]),str(host_build[1]),'--pipe',c._pipe_name,
        '--owner-pid',str(os.getpid()),'--session',c.session,'--instance',c.instance],
        stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        with pytest.raises(HostIpcError) as e:
            NamedPipeTransport.connect(c._pipe_name,proc.pid+1,end=time.monotonic()+5,process=proc)
        assert e.value.code is IpcCode.UNAUTHORIZED_CLIENT
        assert proc.wait(timeout=3)==15
    finally:
        if proc.poll() is None:proc.kill();proc.wait(timeout=3)


def test_native_pending_read_timeout_discards_no_late_result(client):
    client.start()
    with pytest.raises(HostIpcError) as e:
        client.transport.receive(end=time.monotonic()+.03,process=client.process)
    assert e.value.code is IpcCode.TIMEOUT
    client._fail(e.value)
    assert client.state is HostState.FAILED and client.transport.handle is None
    assert client.process.poll() is not None


def test_native_pending_read_cancellation_releases_io_and_process(client):
    client.start();cancel=Event();timer=Timer(.03,cancel.set);timer.start()
    try:
        with pytest.raises(HostIpcError) as e:
            client.transport.receive(end=time.monotonic()+3,process=client.process,cancel=cancel)
        assert e.value.code is IpcCode.CANCELLED
        client._fail(e.value)
        assert client.process.poll() is not None and client.transport.handle is None
    finally:timer.cancel();timer.join()


def test_native_unexpected_disconnect_is_not_success(client):
    client.start();client.transport.close()
    with pytest.raises(HostIpcError) as e:client.ping()
    assert e.value.code in (IpcCode.DISCONNECTED,IpcCode.PROCESS_EXIT_UNEXPECTED)
    assert client.state is HostState.FAILED


def test_native_host_crash_is_explicit_and_never_retried(client):
    client.start();pid=client.process.pid
    client.process.kill();client.process.wait(timeout=3)
    with pytest.raises(HostIpcError) as e:client.ping()
    assert e.value.code is IpcCode.PROCESS_EXIT_UNEXPECTED and client.process.pid==pid
    assert client.state is HostState.FAILED


def test_native_idle_disconnect_cleanup(raw):
    handshake(raw);raw.transport.close()
    assert raw.process.wait(timeout=3)==15


def test_unauthorized_other_process_first_client_rejected(host_build):
    c=BrowserHostClient(*host_build,opaque('bws'))
    proc=subprocess.Popen([str(host_build[0]),str(host_build[1]),'--pipe',c._pipe_name,
        '--owner-pid',str(os.getpid()),'--session',c.session,'--instance',c.instance],
        stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        code=("import time; from local_cli.infrastructure.active_web.host_named_pipe import NamedPipeTransport; "
              f"p=NamedPipeTransport.connect({c._pipe_name!r},{proc.pid},end=time.monotonic()+5,process=None); "
              "time.sleep(.1);p.close()")
        child=subprocess.run([sys.executable,'-B','-c',code],capture_output=True,text=True,timeout=8,
                             creationflags=subprocess.CREATE_NO_WINDOW)
        assert child.returncode==0,child.stderr
        assert proc.wait(timeout=3)==12
    finally:
        if proc.poll() is None:proc.kill();proc.wait(timeout=3)
