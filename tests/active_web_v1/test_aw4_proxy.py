"""AW4 real local proxy sockets + explicit controlled upstream substitutions.

Productive PUBLIC_ONLY rejects these private fixtures. Positive transport tests
substitute ONLY the admitted numeric endpoint for a selected local fixture;
that is not evidence of Internet or exclusive Chromium mediation.
"""
import base64
from contextlib import contextmanager
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socket
import ssl
from threading import Event, Thread
from urllib.parse import urlsplit

import pytest

from local_cli.application.browser_network import BrowserNetworkPolicy
from local_cli.core.active_web_network import BrowserBrokerLimits, BrowserEgressError
from local_cli.core.contracts import CapabilityStatus
from local_cli.infrastructure.active_web.egress_broker import BrowserEgressBroker
from local_cli.infrastructure.active_web.capability_probe import probe_browser_broker
from local_cli.infrastructure.http_fetch import HttpFetchBroker
from tests.active_web_v1.test_aw4_network import ResolverDouble, endpoint

LIMITS = BrowserBrokerLimits(2, 8192, 4096, 65536, 4)
TLS = Path(__file__).parents[1]/'security_v12/network_tls_fixture'


@contextmanager
def upstream(*, tls=False, handler=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_GET(self):
            self.server.hits.append((self.command, self.path, dict(self.headers), b''))
            try:
                if handler:
                    handler(self)
                else:
                    self.send_response(200); self.send_header('Content-Length','9'); self.end_headers()
                    self.wfile.write(b'synthetic')
            except (OSError, ssl.SSLError):
                pass  # Expected peer abort after bounded timeout/cancel.
        def do_POST(self):
            data = self.rfile.read(int(self.headers['Content-Length']))
            self.server.hits.append((self.command, self.path, dict(self.headers), data))
            self.send_response(200); self.send_header('Content-Length','9'); self.end_headers()
            self.wfile.write(b'synthetic')
    class Server(ThreadingHTTPServer):
        daemon_threads = True
        def get_request(self):
            client, address = super().get_request()
            self.connections += 1
            return client, address
    server = Server(('127.0.0.1',0),Handler)
    server.hits, server.connections = [], 0
    if tls:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(TLS/'server_test_cert.pem', TLS/'server_test_key.pem')
        server.socket = ctx.wrap_socket(server.socket,server_side=True)
    thread = Thread(target=server.serve_forever,kwargs={'poll_interval':.02},daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown(); server.server_close(); thread.join(1)


class FixtureAdmission:
    """Test-only endpoint substitution, not a relaxed product PUBLIC_ONLY rule."""
    def __init__(self, server, proof=lambda: True):
        self.server, self.proof = server, proof
        self.base = BrowserNetworkPolicy(ResolverDouble(),validate_session=proof,
            http_ports=(server.server_port,),connect_ports=(server.server_port,))
        self.http_ports = self.base.http_ports
    def validate_current(self):
        self.base.validate_current()
    def authorize(self, method,target,host,budget):
        plan = self.base.authorize(method,target,host,budget)
        assert plan.host == 'server.test', 'Fixture substitution restricted to exact synthetic source'
        return replace(plan,endpoint=endpoint('127.0.0.1',self.server.server_port))


@contextmanager
def broker(admission=None, limits=LIMITS):
    admission = admission or BrowserNetworkPolicy(HttpFetchBroker(),validate_session=lambda: True)
    obj = BrowserEgressBroker(admission,limits=limits)
    obj.start()
    try:
        yield obj
    finally:
        assert obj.close(timeout_seconds=2).confirmed


def connect(obj):
    config = obj.configuration
    u = urlsplit(config.server)
    return socket.create_connection((u.hostname,u.port),timeout=3)


def auth(obj):
    config = obj.configuration
    return base64.b64encode((config.username+':'+config.password).encode()).decode()


def read_all(client):
    data = bytearray()
    while True:
        try:
            chunk = client.recv(8192)
        except (ConnectionResetError, ConnectionAbortedError):
            break
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data)


def exchange(obj, target, *, method='GET', host=None, headers=(), body=b'', authenticated=True):
    host = host or (target if method=='CONNECT' else urlsplit(target).netloc)
    lines = [method+' '+target+' HTTP/1.1','Host: '+host]
    if authenticated:
        lines.append('Proxy-Authorization: Basic '+auth(obj))
    lines += list(headers)
    with connect(obj) as client:
        client.sendall(('\r\n'.join(lines)+'\r\n\r\n').encode('latin-1')+body)
        return read_all(client)


def header(client):
    data = bytearray()
    while not data.endswith(b'\r\n\r\n'):
        chunk = client.recv(1)
        assert chunk
        data.extend(chunk)
        assert len(data)<8192
    return bytes(data)


def quiesce(obj):
    # Outside request latency; bounded worker join, not retry or new operation.
    with obj._lock:
        workers = tuple(obj._workers)
    for worker in workers:
        worker.join(1)
    assert not obj._workers


@pytest.mark.parametrize('target,method,host', [
    ('http://127.0.0.1/', 'GET', '127.0.0.1'), ('http://10.3.4.5/', 'GET', '10.3.4.5'),
    ('http://169.254.169.254/latest/', 'GET', '169.254.169.254'),
    ('http://[::1]/', 'GET', '[::1]'), ('127.0.0.1:443','CONNECT','127.0.0.1:443'),
    ('[::ffff:127.0.0.1]:443','CONNECT','[::ffff:127.0.0.1]:443'),
])
def test_native_productive_broker_blocks_private_http_connect_ipv6_metadata(target,method,host):
    with broker() as obj:
        reply = exchange(obj,target,method=method,host=host)
        assert b'403 Forbidden' in reply and b'DESTINATION_DENIED' in reply
        quiesce(obj)
        records, dropped = obj.records()
        assert len(records)==1 and not records[0]['upstreamConnected'] and not dropped


def test_native_real_localhost_dns_is_denied_without_private_fixture_hit():
    with upstream() as server:
        p = BrowserNetworkPolicy(HttpFetchBroker(),validate_session=lambda:True,http_ports=(server.server_port,))
        with broker(p) as obj:
            reply = exchange(obj,'http://localhost:'+str(server.server_port)+'/')
            assert b'DESTINATION_DENIED' in reply
            assert not server.hits and server.connections==0


def test_native_mixed_dns_rebinding_new_host_and_invalid_plan_never_connect():
    with upstream() as server:
        resolver = ResolverDouble(('93.184.216.34','127.0.0.1'))
        p = BrowserNetworkPolicy(resolver,validate_session=lambda:True,http_ports=(server.server_port,))
        with broker(p) as obj:
            target='http://mixed.test:'+str(server.server_port)+'/'
            assert b'DESTINATION_DENIED' in exchange(obj,target)
            resolver.addresses=('127.0.0.1',)
            assert b'DESTINATION_DENIED' in exchange(obj,target)
            assert b'DESTINATION_DENIED' in exchange(obj,target.replace('mixed','subresource'))
            assert len(resolver.calls)==3 and server.connections==0
            p.authorize=lambda *_: object()  # Malformed trusted port response.
            assert b'INVALID_PLAN' in exchange(obj,target)
            quiesce(obj)
            assert server.connections==0


def test_proxy_is_not_os_firewall_and_does_not_claim_global_direct_bypass_prevention():
    with upstream() as server:
        p = BrowserNetworkPolicy(HttpFetchBroker(),validate_session=lambda:True,http_ports=(server.server_port,))
        with broker(p) as obj:
            denied = exchange(obj,'http://127.0.0.1:'+str(server.server_port)+'/denied')
            assert b'DESTINATION_DENIED' in denied and server.connections==0
            # Authorized test harness socket bypass is possible in HOST_UNISOLATED.
            # Do not mislabel browser-process confinement as verified by this proxy.
            with socket.create_connection(server.server_address,timeout=2) as client:
                client.sendall(b'GET /harness-direct HTTP/1.0\r\n\r\n')
                assert b'synthetic' in read_all(client)
            assert len(server.hits)==1 and server.hits[0][1]=='/harness-direct'
            snap = probe_browser_broker(obj,timeout_seconds=1)
            assert snap.available.status is CapabilityStatus.UNKNOWN
            assert snap.public_only.status is CapabilityStatus.UNKNOWN


def test_channel_secret_required_before_dns_and_not_in_private_configuration_repr():
    resolver = ResolverDouble()
    p = BrowserNetworkPolicy(resolver,validate_session=lambda:True)
    with broker(p) as obj:
        reply = exchange(obj,'http://public.invalid/',authenticated=False)
        assert b'CHANNEL_DENIED' in reply and not resolver.calls
        config = obj.configuration
        assert config.password not in repr(config) and config.username not in repr(config)
        assert config.server.startswith('http://127.0.0.1:')


def test_native_http_forwarding_preserves_body_cookie_but_never_proxy_secret_or_env(monkeypatch):
    with upstream() as server:
        with broker(FixtureAdmission(server)) as obj:
            # Native socket pinning must not use environment proxies or resolve again.
            for name in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY'):
                monkeypatch.setenv(name,'http://127.0.0.1:1')
            client = connect(obj)
            monkeypatch.setattr(socket,'getaddrinfo',lambda *_a,**_k:pytest.fail('connect performed second DNS'))
            secret = auth(obj)
            target = 'http://server.test:'+str(server.server_port)+'/form?q=synthetic'
            request = ('POST '+target+' HTTP/1.1\r\nHost: server.test:'+str(server.server_port)
                +'\r\nProxy-Authorization: Basic '+secret
                +'\r\nCookie: fixture-site-cookie\r\nContent-Length: 7\r\nConnection: close\r\n\r\n').encode()+b'payload'
            with client:
                client.sendall(request); reply=read_all(client)
            assert b'synthetic' in reply and len(server.hits)==1
            _, path, headers, body = server.hits[0]
            assert path=='/form?q=synthetic' and body==b'payload'
            assert 'Proxy-Authorization' not in headers and 'proxy-authorization' not in headers
            assert headers.get('cookie')=='fixture-site-cookie'
            quiesce(obj)
            assert secret not in repr(obj.records()) and 'q=synthetic' not in repr(obj.records())
            assert 'fixture-site-cookie' not in repr(obj.records())


def test_native_connect_tls_pinned_no_second_dns_hostname_verified_by_client(monkeypatch):
    with upstream(tls=True) as server:
        with broker(FixtureAdmission(server)) as obj:
            client = connect(obj)
            destination='server.test:'+str(server.server_port)
            client.sendall(('CONNECT '+destination+' HTTP/1.1\r\nHost: '+destination
                +'\r\nProxy-Authorization: Basic '+auth(obj)+'\r\n\r\n').encode())
            assert header(client)==b'HTTP/1.1 200 Connection Established\r\n\r\n'
            monkeypatch.setattr(socket,'getaddrinfo',lambda *_a,**_k:pytest.fail('TLS second DNS'))
            context=ssl.create_default_context(cafile=str(TLS/'server_test_cert.pem'))
            with context.wrap_socket(client,server_hostname='server.test') as tls_client:
                tls_client.sendall(b'GET /tls HTTP/1.1\r\nHost: server.test\r\nConnection: close\r\n\r\n')
                assert b'synthetic' in read_all(tls_client)
            assert len(server.hits)==1 and server.hits[0][1]=='/tls'


def test_native_connect_client_rejects_wrong_tls_hostname_no_http_request():
    with upstream(tls=True) as server:
        with broker(FixtureAdmission(server)) as obj:
            with connect(obj) as client:
                destination='server.test:'+str(server.server_port)
                client.sendall(('CONNECT '+destination+' HTTP/1.1\r\nHost: '+destination
                    +'\r\nProxy-Authorization: Basic '+auth(obj)+'\r\n\r\n').encode())
                assert b'200 Connection Established' in header(client)
                context=ssl.create_default_context(cafile=str(TLS/'server_test_cert.pem'))
                with pytest.raises(ssl.SSLCertVerificationError):
                    context.wrap_socket(client,server_hostname='wrong.test')
            quiesce(obj)
            assert not server.hits


def test_no_session_proof_no_listener_and_transport_failure_no_retry(monkeypatch):
    p=BrowserNetworkPolicy(HttpFetchBroker(),validate_session=lambda:False)
    obj=BrowserEgressBroker(p,limits=LIMITS)
    with pytest.raises(BrowserEgressError,match='SESSION_DENIED'):
        obj.start()
    assert obj._listener is None and obj.close(timeout_seconds=1).confirmed
    with upstream() as server:
        fixture=FixtureAdmission(server)
    # Deterministic transport fault. A closed TCP port may time out rather than
    # report immediate refusal on Windows; neither is a successful connection.
    attempts=[]
    def failed(plan,budget,owner):
        attempts.append(plan.endpoint)
        raise OSError('synthetic-private-transport-details')
    with broker(fixture) as obj:
        monkeypatch.setattr(obj,'_connect',failed)
        target='http://server.test:'+str(server.server_port)+'/'
        assert b'TRANSPORT_FAILED' in exchange(obj,target)
        quiesce(obj)
        assert len(fixture.base.resolver.calls)==len(attempts)==1
        assert len(obj.records()[0])==1 and not obj.records()[0][0]['retryAllowed']
        assert 'synthetic-private-transport-details' not in repr(obj.records())


def test_native_redirect_is_returned_not_followed_private_followup_denied():
    with upstream() as forbidden:
        location='http://127.0.0.1:'+str(forbidden.server_port)+'/forbidden'
        def redirect(handler):
            handler.send_response(302); handler.send_header('Location',location); handler.end_headers()
        with upstream(handler=redirect) as source:
            with broker(FixtureAdmission(source)) as obj:
                reply=exchange(obj,'http://server.test:'+str(source.server_port)+'/first')
                assert b'302' in reply and location.encode() in reply
                assert len(source.hits)==1 and not forbidden.hits
                # Fresh client request for another origin must pass productive policy.
                obj.admission.base.http_ports += (forbidden.server_port,)
                denied=exchange(obj,location)
                assert b'DESTINATION_DENIED' in denied and forbidden.connections==0


@pytest.mark.parametrize('headers,body', [
    (('Content-Length: 1','Content-Length: 2'), b'xx'),
    (('Content-Length: 1','Transfer-Encoding: chunked'),b'x'),
    (('Transfer-Encoding: chunked',),b'0\r\n\r\n'),
    (('Upgrade: websocket','Connection: upgrade'),b''),
    (('Expect: 100-continue',),b''), (('Content-Length: +1',),b'x'),
    (('Host: other.invalid',),b''), (('Connection: bad token',),b''),
    (('Content-Length: 0',),b'GET http://other.invalid/ HTTP/1.1\r\n\r\n'),
    ((' X-Folded: value',),b''), (('X-Test: a\nb',),b''),
])
def test_native_smuggling_upgrade_and_ambiguous_framing_denied_before_connect(headers,body):
    with upstream() as server:
        with broker(FixtureAdmission(server)) as obj:
            reply=exchange(obj,'http://server.test:'+str(server.server_port)+'/',headers=headers,body=body)
            assert b'HTTP_FRAMING_DENIED' in reply
            assert server.connections==0 and not server.hits


def test_native_header_request_and_relay_limits_enforced():
    with upstream() as server:
        with broker(FixtureAdmission(server),replace(LIMITS,header_bytes=256,request_bytes=8)) as obj:
            reply=exchange(obj,'http://server.test:'+str(server.server_port)+'/',headers=('X-Filler: '+'x'*300,))
            assert b'HEADER_LIMIT' in reply
            reply=exchange(obj,'http://server.test:'+str(server.server_port)+'/',headers=('Content-Length: 9',),body=b'123456789')
            assert b'REQUEST_LIMIT' in reply and server.connections==0
        with broker(FixtureAdmission(server),replace(LIMITS,relay_bytes=32)) as obj:
            reply=exchange(obj,'http://server.test:'+str(server.server_port)+'/large')
            quiesce(obj)
            assert len(reply)<=32
            assert obj.records()[0][0]['errorCode']=='BROWSER_EGRESS_RELAY_LIMIT'


def test_native_timeout_busy_recovery_no_late_response_or_automatic_retry():
    entered,release=Event(),Event()
    def held(handler):
        if handler.path=='/held':
            entered.set(); assert release.wait(2)
        handler.send_response(200); handler.end_headers(); handler.wfile.write(b'late-synthetic')
    with upstream(handler=held) as server:
        with broker(FixtureAdmission(server),replace(LIMITS,timeout_seconds=.25,max_connections=1)) as obj:
            client=connect(obj)
            target='http://server.test:'+str(server.server_port)+'/held'
            client.sendall(('GET '+target+' HTTP/1.1\r\nHost: server.test:'+str(server.server_port)
                +'\r\nProxy-Authorization: Basic '+auth(obj)+'\r\n\r\n').encode())
            try:
                assert entered.wait(1)
                busy=exchange(obj,target+'/busy')
                assert b'503' in busy
                with client:
                    reply=read_all(client)
                assert b'late-synthetic' not in reply
                quiesce(obj)
                assert obj.records()[0][0]['errorCode']=='NETWORK_TIMEOUT'
                assert len(server.hits)==1
            finally:
                release.set()
            later=exchange(obj,'http://server.test:'+str(server.server_port)+'/later')
            assert b'late-synthetic' in later and len(server.hits)==2
            assert all(not r['retryAllowed'] for r in obj.records()[0])


def test_native_session_revoke_or_broker_close_interrupts_pending_no_success():
    entered,release=Event(),Event(); proof=[True]
    def held(handler):
        entered.set(); assert release.wait(2)
        handler.send_response(200); handler.end_headers(); handler.wfile.write(b'late-synthetic')
    with upstream(handler=held) as server:
        with broker(FixtureAdmission(server,lambda:proof[0])) as obj:
            client=connect(obj)
            target='http://server.test:'+str(server.server_port)+'/'
            client.sendall(('GET '+target+' HTTP/1.1\r\nHost: server.test:'+str(server.server_port)
                +'\r\nProxy-Authorization: Basic '+auth(obj)+'\r\n\r\n').encode())
            try:
                assert entered.wait(1)
                proof[0]=False
                with client:
                    assert b'late-synthetic' not in read_all(client)
                quiesce(obj)
                assert obj.records()[0][0]['errorCode']=='BROWSER_EGRESS_SESSION_DENIED'
                assert obj.close(timeout_seconds=1).confirmed
            finally:
                release.set()


def test_native_probe_component_truthful_unknown_browser_and_closed_failure():
    with broker() as obj:
        snap=probe_browser_broker(obj,timeout_seconds=1)
        assert snap.network_broker.value is True
        assert snap.available.status is CapabilityStatus.UNKNOWN and snap.available.value is None
        assert snap.public_only.status is CapabilityStatus.UNKNOWN
        assert snap.engine.status is CapabilityStatus.UNKNOWN
        assert snap.control_class.value=='HOST_UNISOLATED'
    assert probe_browser_broker(obj,timeout_seconds=1).network_broker.value is False
    with pytest.raises(BrowserEgressError,match='INVALID_STATE'):
        obj.start()


def test_native_no_cross_session_channel_and_no_silent_direct_fallback():
    with broker() as first, broker() as second:
        reply=exchange(second,'http://127.0.0.1/',headers=('Proxy-Authorization: Basic '+auth(first),),authenticated=False)
        assert b'CHANNEL_DENIED' in reply
        assert first.configuration.password!=second.configuration.password
        first.close(timeout_seconds=1)
        assert probe_browser_broker(first,timeout_seconds=1).network_broker.value is False
        assert probe_browser_broker(second,timeout_seconds=1).network_broker.value is True
