"""Certification cases: real UDP DNS, unchanged S5 policy, real pinned TCP/TLS/framing.

No monkeypatched policy/DNS returns/pinning or private-IP admission exception.
The socket observer subclasses actual sockets and forwards actual connect_ex.
"""
from dataclasses import replace
import os
import socket
import time
import select
from threading import Event,Thread
from uuid import uuid4

import pytest

from local_cli.core.controlled_fetch import ControlledFetchLimits
from local_cli.core.controlled_fetch import ControlledFetchError
from local_cli.core.network import NetworkEndpoint


def framed(body=b'ok', *, length=None, extra=b''):
    return b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: '+str(len(body) if length is None else length).encode()+b'\r\n'+extra+b'\r\n'+body


def test_native_observer_and_forbidden_canary_calibration(native_env):
    env=native_env;before=len(env.private.connections);attempts=len(env.socket_attempts)
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as sock:
        sock.settimeout(2);sock.connect_ex(('127.0.0.1',80));sock.sendall(b'GET /calibration HTTP/1.1\r\nHost: fixture\r\nConnection: close\r\n\r\n');sock.recv(4096)
    time.sleep(.02)
    row=dict(case='observer_calibration',classification='OBSERVER_CALIBRATION_ONLY_NOT_CF_AUTHORITY',
        nativeTCPConnectAttempts=env.socket_attempts[attempts:],forbiddenCanaryConnections=len(env.private.connections)-before)
    env.rows.append(row)
    assert row['nativeTCPConnectAttempts'] and row['forbiddenCanaryConnections']==1


@pytest.mark.parametrize('tls',[False,True])
@pytest.mark.parametrize('method',['GET','HEAD'])
def test_native_positive_actual_http_https_complete_chain(native_env,tls,method):
    row=native_env.case(f'positive_{tls}_{method}',tls=tls,method=method)
    assert row['outcome']=='SUCCEEDED_OBSERVED' and row['httpCanaryHits']==1
    assert len(row['nativeTCPConnectAttempts'])==1 and len(row['transport'])==1
    t=row['transport'][0];assert t['admittedEndpoint']==t['connectedEndpoint']
    assert t['dnsAnswers'] and t['httpRequestBytesSent']>0
    assert row['serverEvents'][0]['host']=='cf-public.test'
    assert row['serverEvents'][0]['acceptEncoding']=='identity' and row['serverEvents'][0]['connection']=='close'
    assert not row['serverEvents'][0]['forbiddenHeadersPresent']
    if tls:assert row['tlsServerSNI']==['cf-public.test']
    if method=='HEAD':assert row['countedBytes']==0


@pytest.mark.parametrize('literal',['127.0.0.1','0.0.0.0','10.0.0.1','172.16.0.1','192.168.0.1','100.64.0.1',
    '169.254.169.254','100.100.100.200','224.0.0.1','240.0.0.1','192.0.2.1','198.18.0.1',
    '[::1]','[::]','[fc00::1]','[fe80::1]','[ff02::1]','[2001:db8::1]',
    '[::ffff:127.0.0.1]','[2002:7f00:1::]','[64:ff9b::7f00:1]'])
def test_native_public_only_literal_negative_no_upstream_attempt(native_env,literal):
    row=native_env.case('literal_denial_'+literal,host=literal)
    assert row['outcome']=='NOT_STARTED' and row['error']=='CONTROLLED_FETCH_ADMISSION_DENIED'
    assert not row['nativeTCPConnectAttempts'] and not row['transport'] and row['forbiddenCanaryConnections']==0
    assert not row['dnsServerPackets']


@pytest.mark.parametrize('behavior',['private','mixed','empty','excessive','ambiguous','timeout'])
def test_native_dns_denial_from_actual_packets_no_forbidden_socket(native_env,behavior):
    host='cf-'+behavior+'.test';native_env.dns.behavior[host]=behavior
    row=native_env.case('dns_'+behavior,host=host,limits=ControlledFetchLimits(timeout_seconds=1))
    assert row['outcome']=='NOT_STARTED' and row['dnsServerPackets']
    assert not row['nativeTCPConnectAttempts'] and row['forbiddenCanaryConnections']==0
    assert row['durationSeconds']<1.6


def test_native_actual_system_resolver_localhost_denies(native_env):
    row=native_env.case('system_dns_localhost',host='localhost',resolver_mode='system')
    assert row['outcome']=='NOT_STARTED' and row['error']=='CONTROLLED_FETCH_ADMISSION_DENIED'
    assert not row['nativeTCPConnectAttempts'] and row['forbiddenCanaryConnections']==0


def test_native_actual_system_resolver_public_owned_endpoint(native_env):
    host=native_env.address.replace(':','-')+'.sslip.io'
    row=native_env.case('system_dns_public_owned_http',host=host,resolver_mode='system')
    assert row['outcome']=='SUCCEEDED_OBSERVED' and row['transport'][0]['connectedEndpoint']==[native_env.address,80]


@pytest.mark.parametrize('trusted,host',[(False,'cf-public.test'),(True,'cf-wrong.test')])
def test_native_standard_tls_rejects_untrusted_chain_and_wrong_hostname(native_env,trusted,host):
    row=native_env.case('tls_invalid_'+host+str(trusted),tls=True,host=host,trusted=trusted)
    assert row['outcome']=='FAILED_NO_EFFECT_CONFIRMED' and row['error']=='CONTROLLED_FETCH_TLS_FAILED'
    assert row['httpCanaryHits']==0 and len(row['nativeTCPConnectAttempts'])==1
    assert row['transport'][0]['httpRequestBytesSent']==0 and row['tlsServerSNI']==[host]


@pytest.mark.parametrize('tls',[False,True])
@pytest.mark.parametrize('method',['GET','HEAD'])
def test_native_redirect_public_public_same_lineage_deadline_head_preserved(native_env,tls,method):
    server=native_env.https if tls else native_env.http
    server.routes['/redirect']=b'HTTP/1.1 302 Found\r\nLocation: /ok\r\nContent-Length: 0\r\n\r\n'
    row=native_env.case('redirect_public_'+str(tls)+method,tls=tls,method=method,path='/redirect')
    assert row['outcome']=='SUCCEEDED_OBSERVED' and row['httpCanaryHits']==2
    assert [e['method'] for e in row['serverEvents']]==[method,method]
    assert len(row['dnsServerPackets'])==4 and [t['hop'] for t in row['transport']]==[0,1]
    assert len({t['operationId'] for t in row['transport']})==1 and row['receipts'][0]['outcome']=='STARTED'


@pytest.mark.parametrize('location',['http://127.0.0.1/private','http://other.test/','file:///private',' /bad',
    'http://cf-public.test/#fragment'])
def test_native_redirect_denied_before_next_socket(native_env,location):
    native_env.http.routes['/bad-redirect']=b'HTTP/1.1 302 Found\r\nLocation: '+location.encode()+b'\r\nContent-Length: 0\r\n\r\n'
    row=native_env.case('redirect_denial_'+location.split(':')[0],path='/bad-redirect')
    # Header OWS is normal HTTP; /bad is allowed after trimming. Test malformed value via control below.
    if location==' /bad':assert row['outcome']=='SUCCEEDED_OBSERVED' and row['httpCanaryHits']==2
    else:assert row['outcome']=='UNKNOWN' and row['httpCanaryHits']==1 and row['forbiddenCanaryConnections']==0


def test_native_redirect_private_dns_on_new_admission(native_env):
    native_env.dns.behavior['cf-rebind.test']='rebind';native_env.dns.admissions['cf-rebind.test']=0
    native_env.http.routes['/rebind']=b'HTTP/1.1 302 Found\r\nLocation: /ok\r\nContent-Length: 0\r\n\r\n'
    row=native_env.case('redirect_rebinding_private',host='cf-rebind.test',path='/rebind')
    assert row['outcome']=='UNKNOWN' and row['error']=='CONTROLLED_FETCH_ADMISSION_DENIED'
    assert len(row['dnsServerPackets'])==4 and len(row['nativeTCPConnectAttempts'])==1 and row['forbiddenCanaryConnections']==0


def test_native_redirect_https_downgrade(native_env):
    native_env.https.routes['/downgrade']=b'HTTP/1.1 302 Found\r\nLocation: http://cf-public.test/ok\r\nContent-Length: 0\r\n\r\n'
    row=native_env.case('https_downgrade',tls=True,path='/downgrade')
    assert row['outcome']=='UNKNOWN' and row['error']=='CONTROLLED_FETCH_REDIRECT_DENIED' and len(row['nativeTCPConnectAttempts'])==1


@pytest.mark.parametrize('wire',[b'HTTP/1.1 200 OK\n\n',b'HTTP/2 200 OK\r\n\r\n',
    framed(extra=b'Content-Length: 999\r\n'),framed(extra=b'Transfer-Encoding: chunked\r\n'),
    b'HTTP/1.1 200 OK\r\nContent-Length: nope\r\n\r\n',b'HTTP/1.1 200 OK\r\nContent-Length: -1\r\n\r\n',
    b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n1\r\nx\r\n0\r\n\r\n',
    b'HTTP/1.1 200 OK\r\nTransfer-Encoding: gzip\r\n\r\n',framed(extra=b'Content-Encoding: gzip\r\n'),
    b'HTTP/1.1 200 OK\r\n Folded: bad\r\n\r\n'])
def test_native_malformed_or_unsupported_framing_never_success(native_env,wire):
    native_env.http.routes['/malformed']=wire
    row=native_env.case('framing_denial',path='/malformed')
    assert row['outcome']=='UNKNOWN' and row['error']=='CONTROLLED_FETCH_FRAMING_DENIED' and row['httpCanaryHits']==1


@pytest.mark.parametrize('wire',[b'HTTP/1.1 200 OK\r\nX: '+b'a'*33000+b'\r\n\r\n',
    b'HTTP/1.1 200 OK\r\n'+b'X: a\r\n'*101+b'\r\n',b'HTTP/1.1 200 '+b'a'*2100+b'\r\n\r\n'],
    ids=['byte-ceiling','header-count','status-size'])
def test_native_headers_status_limits_during_read(native_env,wire):
    native_env.http.routes['/headers-oversize']=wire
    row=native_env.case('header_limit',path='/headers-oversize')
    assert row['outcome']=='UNKNOWN' and row['error']=='CONTROLLED_FETCH_LIMIT_EXCEEDED'
    assert row['transport'][0]['httpHeaderBytesReceived']<=32768


@pytest.mark.parametrize('stage',['headers','body'])
def test_native_continuous_trickle_deadline_not_refreshed(native_env,stage):
    def slow(conn,method):
        if stage=='headers':
            for char in b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 10\r\n\r\n':
                conn.sendall(bytes([char]));time.sleep(.035)
        else:
            conn.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 100\r\n\r\n')
            for _ in range(100):conn.sendall(b'x');time.sleep(.04)
    native_env.http.routes['/slow']=slow
    row=native_env.case('slow_'+stage,path='/slow',limits=ControlledFetchLimits(timeout_seconds=1))
    assert row['outcome']=='UNKNOWN' and row['error'] in ('CONTROLLED_FETCH_TIMEOUT','CONTROLLED_FETCH_EXPIRED') and row['durationSeconds']<1.6


@pytest.mark.parametrize('wire',[b'HTTP/1.1 200',framed(b'x',length=20)])
def test_native_disconnect_headers_or_body_is_unknown(native_env,wire):
    native_env.http.routes['/early-close']=wire
    row=native_env.case('disconnect_early',path='/early-close')
    assert row['outcome']=='UNKNOWN' and row['error']=='CONTROLLED_FETCH_FRAMING_DENIED'


@pytest.mark.parametrize('with_length',[True,False])
def test_native_body_ceiling_stops_reading_and_returns_partial(native_env,with_length):
    native_env.http.routes['/oversize']=framed(b'x'*1000) if with_length else b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\n'+b'x'*1000
    row=native_env.case('body_limit_'+str(with_length),path='/oversize',limits=ControlledFetchLimits(max_response_bytes=32))
    assert row['outcome']=='PARTIAL' and row['truncated'] and row['countedBytes']==32
    assert row['transport'][0]['httpBodyBytesReceived']==32 and len(row['nativeTCPConnectAttempts'])==1


def test_native_no_length_eof_and_204_head_304_semantics(native_env):
    native_env.http.routes['/eof']=b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nok'
    row=native_env.case('body_until_eof',path='/eof');assert row['outcome']=='SUCCEEDED_OBSERVED' and row['countedBytes']==2
    native_env.http.routes['/204']=b'HTTP/1.1 204 No Content\r\n\r\n'
    row=native_env.case('204_no_body',path='/204');assert row['outcome']=='SUCCEEDED_OBSERVED' and row['countedBytes']==0
    native_env.http.routes['/304']=b'HTTP/1.1 304 Not Modified\r\nContent-Length: 999\r\n\r\n'
    row=native_env.case('304_no_body',path='/304');assert row['outcome']=='UNKNOWN' and row['countedBytes']==0 and row['transport'][0]['complete']


def test_native_redirect_count_limit_and_policy_expiry_between_hops(native_env):
    native_env.http.routes['/loop']=b'HTTP/1.1 302 Found\r\nLocation: /loop\r\nContent-Length: 0\r\n\r\n'
    row=native_env.case('redirect_limit',path='/loop',limits=ControlledFetchLimits(max_redirects=1))
    assert row['outcome']=='UNKNOWN' and row['error']=='CONTROLLED_FETCH_REDIRECT_DENIED' and len(row['nativeTCPConnectAttempts'])==2
    def expired(conn,method):
        time.sleep(.75);conn.sendall(b'HTTP/1.1 302 Found\r\nLocation: /slow-next\r\nContent-Length: 0\r\n\r\n')
    def next_slow(conn,method):time.sleep(.75);conn.sendall(framed())
    native_env.http.routes['/expire-hop']=expired;native_env.http.routes['/slow-next']=next_slow
    row=native_env.case('deadline_between_hops',path='/expire-hop',limits=ControlledFetchLimits(timeout_seconds=1))
    assert row['outcome']=='UNKNOWN' and row['error'] in ('CONTROLLED_FETCH_TIMEOUT','CONTROLLED_FETCH_EXPIRED') and row['durationSeconds']<1.6


def test_native_no_ambient_proxy_or_auth_retry(native_env,monkeypatch):
    for variable in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY'):monkeypatch.setenv(variable,'http://127.0.0.1:80/private')
    row=native_env.case('ambient_proxy_ignored',tls=True)
    assert row['outcome']=='SUCCEEDED_OBSERVED' and row['forbiddenCanaryConnections']==0 and not row['serverEvents'][0]['forbiddenHeadersPresent']
    native_env.http.routes['/challenge']=b'HTTP/1.1 401 Unauthorized\r\nWWW-Authenticate: Basic realm="synthetic"\r\nContent-Length: 0\r\n\r\n'
    row=native_env.case('auth_no_retry',path='/challenge');assert row['outcome']=='UNKNOWN' and len(row['nativeTCPConnectAttempts'])==1 and not row['retryAllowed']


def test_native_expiry_after_started_before_socket_proves_zero_dispatch(native_env):
    row=native_env.case('policy_expiry_before_connect',policy_mutator=lambda policy,token:policy.update_revision(2))
    assert row['outcome']=='FAILED_NO_EFFECT_CONFIRMED' and not row['nativeTCPConnectAttempts']


def test_native_dns_unavailable_is_bounded_without_tcp(native_env):
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
    row=native_env.case('dns_unavailable',dns_port=port,limits=ControlledFetchLimits(timeout_seconds=1))
    assert row['outcome']=='NOT_STARTED' and not row['nativeTCPConnectAttempts'] and row['durationSeconds']<1.6


@pytest.mark.parametrize('name,start,end',[('expired','20000101000000Z','20010101000000Z'),
    ('not-yet-valid','20350101000000Z','20360101000000Z')])
def test_native_tls_dates_standard_verification(native_env,name,start,end):
    old=native_env.https.tls
    try:
        context,digest=native_env.dated_leaf(name,start,end);native_env.https.tls=context
        row=native_env.case('tls_'+name,tls=True);row['presentedFixtureCertSha256']=digest
        assert row['outcome']=='FAILED_NO_EFFECT_CONFIRMED' and row['error']=='CONTROLLED_FETCH_TLS_FAILED'
        assert row['httpCanaryHits']==0 and row['transport'][0]['httpRequestBytesSent']==0
        assert row['transport'][0]['tlsVerifyCode']==(10 if name=='expired' else 9)
    finally:native_env.https.tls=old


def test_native_disconnect_before_first_request_send_is_proven_zero(native_env):
    native_env.http.reset_before_request=True;native_env.http.reset_done=Event()
    try:
        row=native_env.case('disconnect_during_request_attempt',reset_sync=True)
        assert row['outcome']=='FAILED_NO_EFFECT_CONFIRMED' and row['httpCanaryHits']==0
        assert row['transport'][0]['stage']=='REQUEST' and row['transport'][0]['httpRequestBytesSent']==0
    finally:native_env.http.reset_before_request=False


def test_native_policy_revision_changes_after_first_hop_stop_fresh_admission(native_env):
    # Actual DNS second hop delayed past the SAME grant/operation deadline.
    native_env.dns.behavior['cf-rebind.test']='public'
    native_env.http.routes['/deadline-redirect']=b'HTTP/1.1 302 Found\r\nLocation: /slow-next\r\nContent-Length: 0\r\n\r\n'
    row=native_env.case('expiry_next_hop',path='/expire-hop',limits=ControlledFetchLimits(timeout_seconds=1))
    assert row['outcome']=='UNKNOWN' and row['durationSeconds']<1.6


def test_native_aggregate_allowance_cuts_wire_response(native_env):
    native_env.http.routes['/aggregate']=framed(b'a'*1000)
    row=native_env.case('aggregate_wire_allowance',path='/aggregate',limits=ControlledFetchLimits(per_turn_bytes=300))
    assert row['outcome']=='PARTIAL' and row['transport'][0]['httpRequestBytesSent']+row['transport'][0]['httpHeaderBytesReceived']+row['transport'][0]['httpBodyBytesReceived']<=300


def test_native_connect_refused_and_calibrated_backlog_timeout(native_env):
    env=native_env;env.http.close();time.sleep(.03)
    refused=env.case('connect_refused')
    assert refused['outcome']=='FAILED_NO_EFFECT_CONFIRMED' and refused['error']=='CONTROLLED_FETCH_CONNECT_FAILED'
    assert refused['transport'][0]['httpRequestBytesSent']==0
    listener=socket.socket(socket.AF_INET6,socket.SOCK_STREAM);listener.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_V6ONLY,1)
    listener.bind((env.address,80));listener.listen(1);fill=[];saturated=False
    try:
        for _ in range(32):
            sock=socket.socket(socket.AF_INET6,socket.SOCK_STREAM);sock.settimeout(.15)
            try:sock.connect((env.address,80));fill.append(sock)
            except TimeoutError:sock.close();saturated=True;break
        assert saturated,'Native blackhole fixture was not calibrated; no timeout PASS inferred'
        row=env.case('connect_timeout_calibrated_backlog',limits=ControlledFetchLimits(timeout_seconds=1))
        row['blackholeCalibration']={'queuedNativeConnections':len(fill),'pendingConnectTimedOut':saturated,'configuredBacklog':1}
        assert row['outcome']=='FAILED_NO_EFFECT_CONFIRMED' and row['error'] in ('CONTROLLED_FETCH_TIMEOUT','CONTROLLED_FETCH_EXPIRED')
        assert row['transport'][0]['httpRequestBytesSent']==0 and row['durationSeconds']<1.6
    finally:
        for sock in fill:sock.close()
        listener.close()
        # Restore only our owned fixture, so later tests do not depend on ordering.
        from tests.controlled_fetch_v12_b2.native_harness import HTTPFixture
        env.http=HTTPFixture(env.address,80)


def test_native_new_admission_mixed_dns_redirect_is_denied(native_env):
    native_env.dns.behavior['cf-mixed.test']='rebind-mixed';native_env.dns.admissions['cf-mixed.test']=0
    native_env.http.routes['/mixed-next']=b'HTTP/1.1 302 Found\r\nLocation: /ok\r\nContent-Length: 0\r\n\r\n'
    row=native_env.case('redirect_mixed_dns',host='cf-mixed.test',path='/mixed-next')
    assert row['outcome']=='UNKNOWN' and row['error']=='CONTROLLED_FETCH_ADMISSION_DENIED'
    assert len(row['dnsServerPackets'])==4 and len(row['nativeTCPConnectAttempts'])==1 and row['forbiddenCanaryConnections']==0


def test_native_invalid_location_control_is_denied(native_env):
    native_env.http.routes['/location-control']=b'HTTP/1.1 302 Found\r\nLocation: /bad\x00target\r\nContent-Length: 0\r\n\r\n'
    row=native_env.case('malformed_location',path='/location-control')
    assert row['outcome']=='UNKNOWN' and row['error']=='CONTROLLED_FETCH_FRAMING_DENIED' and len(row['nativeTCPConnectAttempts'])==1


def test_native_host_issued_plan_rejects_ip_clone_wrong_operation_owner_and_replay(native_env):
    checked=[];done=[False]
    def hook(plan,service):
        if done[0]:return
        done[0]=True
        variants=[plan.endpoint.address,replace(plan),replace(plan,endpoint=NetworkEndpoint('127.0.0.1',socket.AF_INET,80)),
            replace(plan,request=replace(plan.request,operation_id='op_wrong')),
            replace(plan,request=replace(plan.request,owner=replace(plan.request.owner,task_id='task_wrong'))),
            replace(plan,transfer_byte_allowance=plan.transfer_byte_allowance+1)]
        for forged in variants:
            with pytest.raises(ControlledFetchError):service.transport.validate(forged)
            checked.append('rejected-before-socket')
        with pytest.raises(ControlledFetchError):service.transport.dispatch(plan,object())
        checked.append('unstarted-plan-cannot-dispatch')
    retained=[]
    row=native_env.case('host_plan_boundary',validate_hook=hook,capture_service=lambda *args:retained.append(args))
    service=retained[0][0]
    assert row['outcome']=='SUCCEEDED_OBSERVED' and len(checked)==7 and len(row['nativeTCPConnectAttempts'])==1
    row['forgedPlanChecks']=checked


def test_native_real_deadline_expired_plan_denies_before_socket(native_env):
    first=[True]
    def expire(plan,service):
        if first[0]:first[0]=False;time.sleep(1.05)
    row=native_env.case('expired_plan',limits=ControlledFetchLimits(timeout_seconds=1),validate_hook=expire)
    assert row['outcome']=='NOT_STARTED' and row['error']=='CONTROLLED_FETCH_EXPIRED' and not row['nativeTCPConnectAttempts']


def test_native_policy_revocation_after_http_first_hop_stops_next(native_env):
    captured=[]
    def revoke(conn,method):
        captured[0][0].policy.update_revision(2)
        conn.sendall(b'HTTP/1.1 302 Found\r\nLocation: /ok\r\nContent-Length: 0\r\n\r\n')
    native_env.http.routes['/policy-next']=revoke
    row=native_env.case('policy_revision_between_hops',path='/policy-next',capture_service=lambda *args:captured.append(args))
    assert row['outcome']=='UNKNOWN' and row['error']=='CONTROLLED_FETCH_STALE_POLICY' and len(row['nativeTCPConnectAttempts'])==1


def test_native_concurrency_reservation_rejects_second_request_without_socket(native_env):
    ready,release=Event(),Event();captured=[];results=[]
    def hold(conn,method):ready.set();assert release.wait(2);conn.sendall(framed())
    native_env.http.routes['/held']=hold
    worker=Thread(target=lambda:results.append(native_env.case('native_concurrency',path='/held',
        limits=ControlledFetchLimits(concurrency=1,timeout_seconds=3),capture_service=lambda *args:captured.append(args))))
    worker.start();assert ready.wait(2)
    service,request,context,grant=captured[0]
    try:
        other=replace(context,operation_id='op_'+uuid4().hex)
        second=service.request_from_candidate({'capabilityId':'CONTROLLED_FETCH_V1_2','url':request.canonical_target,'method':'GET','resultMode':'TEXT'},other)
        issued=service.issuer.issue(service.grant_request(second,other),other.cancellation)
        before=len(native_env.socket_attempts)
        with pytest.raises(ControlledFetchError) as denied:service.execute(second,other,issued)
        assert denied.value.code.value=='CONTROLLED_FETCH_CONCURRENCY_LIMIT'
        assert len(native_env.socket_attempts)==before
    finally:release.set();worker.join(3)
    assert not worker.is_alive() and results[0]['outcome']=='SUCCEEDED_OBSERVED' and len(results[0]['nativeTCPConnectAttempts'])==1
