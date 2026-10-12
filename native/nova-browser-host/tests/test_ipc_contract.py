"""IPC_CONTRACT_TEST: deterministic codec/ownership; no engine evidence."""
import copy
import json
import struct
from threading import Event, Thread
import time

import pytest

from local_cli.infrastructure.active_web.host_ipc_protocol import (
    HostIpcError, IpcCode, MAX_FRAME_BYTES, MAX_DEADLINE_MS, decode, encode,
    envelope, opaque, correlate, validate,
)
from local_cli.infrastructure.active_web.browser_host import BrowserHostClient, HostState
from local_cli.infrastructure.active_web.host_named_pipe import NamedPipeTransport


def request():
    return envelope(opaque('bws'), {'command':'ping'})


def response(r):
    return dict(r, messageType='response', payload={}, result={'kind':'ping','state':'READY','hostPid':19})


def test_exact_utf8_length_prefixed_little_endian_contract():
    r=request(); frame=encode(r)
    assert struct.unpack('<I',frame[:4])[0]==len(frame[4:])
    assert decode(frame[4:])==r
    assert json.loads(frame[4:])==r


@pytest.mark.parametrize('field', ['approval','approvalToken','grant','grantId','authority',
                                  'password','cookie','providerCredentials','javascript','selector','url'])
def test_no_authority_or_untyped_content_in_either_direction(field):
    for m in (request(),response(request())):
        m[field]='untrusted synthetic value'
        with pytest.raises(HostIpcError): validate(m)


@pytest.mark.parametrize('key', ['schemaVersion','messageType','payload','result','error','deadline'])
def test_missing_fields_rejected(key):
    m=request(); del m[key]
    with pytest.raises(HostIpcError): validate(m)


@pytest.mark.parametrize('body', [b'{', b'\xff', b'[]', b'null', b'"word"', b'{"x":NaN}'])
def test_malformed_json_and_utf8(body):
    with pytest.raises(HostIpcError): decode(body)


def test_duplicate_json_keys_are_never_last_wins():
    body=json.dumps(request()).encode()
    body=body.replace(b'{',b'{"schemaVersion":1,',1)
    with pytest.raises(HostIpcError): decode(body)


def test_oversized_and_empty_body():
    for b in (b'',b'a'*(MAX_FRAME_BYTES+1)):
        with pytest.raises(HostIpcError) as e: decode(b)
        assert e.value.code is IpcCode.OVERSIZED_FRAME


@pytest.mark.parametrize('version', [2,0,True,1.0,'1'])
def test_protocol_version_is_strict_integer(version):
    m=request();m['schemaVersion']=version
    with pytest.raises(HostIpcError) as e: validate(m)
    assert e.value.code is IpcCode.PROTOCOL_MISMATCH


@pytest.mark.parametrize('kind', ['execute','navigation','grant','HOST_READY',''])
def test_unknown_messages_rejected(kind):
    m=request();m['messageType']=kind
    with pytest.raises(HostIpcError) as e: validate(m)
    assert e.value.code is IpcCode.UNKNOWN_MESSAGE


@pytest.mark.parametrize('field,prefix', [('requestId','bhr'),('browserSessionRef','bws'),('operationId','op')])
def test_response_correlation_is_exact(field,prefix):
    r=request();reply=response(r);reply[field]=opaque(prefix)
    with pytest.raises(HostIpcError) as e: correlate(r,reply)
    assert e.value.code is IpcCode.CORRELATION_MISMATCH


def test_deadline_and_page_correlation():
    r=request();reply=response(r);reply['deadline']+=1
    with pytest.raises(HostIpcError): correlate(r,reply)
    reply=response(r);reply['pageRef']=opaque('bwp')
    with pytest.raises(HostIpcError): correlate(r,reply)


@pytest.mark.parametrize('command', ['navigate','eval','write','shell','browser_open'])
def test_no_functional_browser_commands(command):
    with pytest.raises(HostIpcError) as e: envelope(opaque('bws'), {'command':command})
    assert e.value.code is IpcCode.UNSUPPORTED_COMMAND


def test_reserved_browser_has_no_payload_authority():
    m=envelope(opaque('bws'), {'command':'reserved_browser'},page=opaque('bwp'))
    assert decode(encode(m)[4:])==m
    m['payload']['url']='https://synthetic.invalid'
    with pytest.raises(HostIpcError): validate(m)


def test_cancelled_and_timeout_transport_checks_are_deterministic():
    cancelled=Event();cancelled.set()
    with pytest.raises(HostIpcError) as e: NamedPipeTransport.check(time.monotonic()+10,cancel=cancelled)
    assert e.value.code is IpcCode.CANCELLED
    with pytest.raises(HostIpcError) as e: NamedPipeTransport.check(0)
    assert e.value.code is IpcCode.TIMEOUT


def test_host_never_started_and_clean_no_process_shutdown():
    client=BrowserHostClient('/missing/dotnet','/missing/nova-browser-host.dll',opaque('bws'))
    with pytest.raises(HostIpcError) as e: client.ping()
    assert e.value.code is IpcCode.HOST_NOT_STARTED
    client.shutdown();client.shutdown()
    assert client.state is HostState.STOPPED and client.process is None


def test_start_failed_and_prestart_cancellation_do_not_create_a_process():
    c=BrowserHostClient('/missing/dotnet','/missing/nova-browser-host.dll',opaque('bws'))
    with pytest.raises(HostIpcError) as e:c.start()
    assert e.value.code is IpcCode.PROCESS_START_FAILED and c.state is HostState.FAILED
    c=BrowserHostClient('/missing/dotnet','/missing/nova-browser-host.dll',opaque('bws'));cancel=Event();cancel.set()
    with pytest.raises(HostIpcError) as e:c.start(cancel=cancel)
    assert e.value.code is IpcCode.CANCELLED and c.process is None


def test_zero_timeout_is_immediate_without_clock_advancement():
    c=BrowserHostClient('/missing/dotnet','/missing/nova-browser-host.dll',opaque('bws'))
    with pytest.raises(HostIpcError) as e:c.start(timeout_ms=0)
    assert e.value.code is IpcCode.TIMEOUT and c.process is None


def test_deadline_budget_rejects_unbounded_values():
    for n in (-1,MAX_DEADLINE_MS+1,True,1.0):
        with pytest.raises(HostIpcError):BrowserHostClient._budget(n)


def test_response_cannot_announce_active_web_or_extra_features():
    r=response(request());r['result']['available']=True
    with pytest.raises(HostIpcError):validate(r)


def test_existing_application_capability_remains_closed():
    from local_cli.core.contracts import BrowserCapabilitySnapshot, CapabilityStatus
    from local_cli.application.active_web_service import usable
    cap=BrowserCapabilitySnapshot()
    assert cap.available.status is CapabilityStatus.UNKNOWN
    assert cap.public_only.status is CapabilityStatus.UNKNOWN and not usable(cap)
    assert not hasattr(BrowserHostClient,'tools') and not hasattr(BrowserHostClient,'navigate')


def test_waiting_for_ipc_owner_cannot_escape_deadline():
    c=BrowserHostClient('/missing/dotnet','/missing/nova-browser-host.dll',opaque('bws'))
    held,release=Event(),Event()
    def holder():
        with c._lock:
            held.set();assert release.wait(2)
    t=Thread(target=holder);t.start();assert held.wait(1)
    try:
        with pytest.raises(HostIpcError) as e:c.ping(timeout_ms=20)
        assert e.value.code is IpcCode.TIMEOUT
        assert c.process is None and c.state is HostState.NOT_STARTED
    finally:release.set();t.join(2)


def test_late_reply_is_never_committed_or_retried():
    c=BrowserHostClient('/missing/dotnet','/missing/nova-browser-host.dll',opaque('bws'))
    r=request();calls=[]
    class LateTransport:
        def write(self,frame,**kwargs):calls.append('write')
        def receive(self,**kwargs):
            time.sleep(.02)
            return response(r)
    c.transport=LateTransport()
    with pytest.raises(HostIpcError) as e:c._exchange(r,time.monotonic()+.005)
    assert e.value.code is IpcCode.TIMEOUT and calls==['write'] and c._last is None
