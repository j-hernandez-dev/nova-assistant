"""Opt-in real HTTP/TLS/IPv4/IPv6 sockets on PRIVATE fixtures, never external Internet.

Test-only resolver/admission substitutions are explicitly recorded. Productive
PUBLIC_ONLY is separately proved to deny the very same local fixtures.
"""
from contextlib import contextmanager
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import ssl
from threading import Event, Thread
import time

import pytest

from local_cli.application.cancellation import CancellationController
from local_cli.application.network import NetworkFetchService
from local_cli.application.tool_runtime import ToolRegistry, ToolRuntime
from local_cli.core.contracts import EffectState, ToolStatus
from local_cli.core.network import FetchBudget, FetchLimits, HttpHop, NetworkEndpoint, NetworkError
from local_cli.infrastructure.http_fetch import HttpFetchBroker
from local_cli.network_config import DEFAULT_FETCH_LIMITS
from local_cli.tools.web_fetch_tool import WebFetchTool
from tests.security_v12.test_s2_policy import invocation

pytestmark = pytest.mark.skipif(os.environ.get('NOVA_S5_HOST_REAL') != '1', reason='S5 native private fixtures opt-in')
TLS = Path(__file__).with_name('network_tls_fixture')


def evidence(case, server=None, **fields):
    out = Path(os.environ['NOVA_S5_EVIDENCE_DIR'])/'network_observations.json'
    records = json.loads(out.read_text()) if out.exists() else []
    records.append({'case':case, 'broker':'local_cli.infrastructure.http_fetch.HttpFetchBroker',
        'externalInternet':False, 'realSocket':server is not None,
        'fixtureAddress':list(server.server_address) if server else None,
        'httpHits':list(server.hits) if server else [],
        'tcpConnections':server.connections if server else None, **fields})
    out.write_text(json.dumps(records, indent=2), encoding='utf-8')


@contextmanager
def server(handler=None, *, ipv6=False, tls=False):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.server.hits.append({'path':self.path, 'host':self.headers['Host'],
                'clientAddress':self.client_address[0], 'headers':dict(self.headers.items())})
            try:
                if handler:
                    handler(self)
                else:
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/plain; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(b'fixture')
            except (OSError, ssl.SSLError):
                pass  # client closing its bounded response is expected

    class Server(ThreadingHTTPServer):
        address_family = socket.AF_INET6 if ipv6 else socket.AF_INET
        daemon_threads = True
        def get_request(self):
            sock, address = super().get_request()
            self.connections += 1
            return sock, address
    http = Server(('::1' if ipv6 else '127.0.0.1', 0), Handler)
    http.hits = []
    http.connections = 0
    if tls:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(TLS/'server_test_cert.pem', TLS/'server_test_key.pem')
        http.socket = ctx.wrap_socket(http.socket, server_side=True)
    thread = Thread(target=http.serve_forever, kwargs={'poll_interval':.02}, daemon=True)
    thread.start()
    try:
        yield http
    finally:
        http.shutdown()
        http.server_close()
        thread.join(1)


def budget(timeout=2, token=None):
    return FetchBudget(FetchLimits(timeout, 2097152, 5, 50000), token or CancellationController(), None)


def get(broker, http, path='/', *, hostname='server.test', tls=False, body_bytes=2097152,
        operation_budget=None, guard=lambda: None):
    url = ('https' if tls else 'http') + '://' + hostname + ':' + str(http.server_port) + path
    endpoint = NetworkEndpoint(http.server_address[0], http.address_family, http.server_port)
    return broker.get(url, endpoint, budget=operation_budget or budget(), body_bytes=body_bytes,
                      validate_dispatch=guard)


def test_native_ipv4_pinning_no_second_dns_no_ambient_proxy_credentials(tmp_path, monkeypatch):
    for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY'):
        monkeypatch.setenv(key, 'http://127.0.0.1:1')
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *_a, **_k: pytest.fail('second DNS lookup'))
    with server() as http:
        report = get(HttpFetchBroker(), http)
        assert report.status == 200 and report.body == b'fixture'
        assert len(http.hits) == 1 and http.hits[0]['host'] == 'server.test:'+str(http.server_port)
        assert not any(k.lower() in ('authorization', 'cookie', 'proxy-authorization') for k in http.hits[0]['headers'])
        evidence('ipv4_pinned_get', http, passed=True, noSecondDNS=True, noProxy=True)


def test_native_ipv6_pinned_connection():
    with server(ipv6=True) as http:
        report = get(HttpFetchBroker(), http)
        assert report.status == 200 and report.body == b'fixture'
        assert len(http.hits) == 1 and http.hits[0]['clientAddress'] == '::1'
        evidence('ipv6_pinned_get', http, passed=True)


def test_native_https_original_hostname_verified_on_pinned_ip():
    trusted = ssl.create_default_context(cafile=str(TLS/'server_test_cert.pem'))
    with server(tls=True) as http:
        report = get(HttpFetchBroker(tls_context=trusted), http, tls=True)
        assert report.status == 200 and report.body == b'fixture'
        for broker, hostname in ((HttpFetchBroker(), 'server.test'),
                                 (HttpFetchBroker(tls_context=trusted), 'wrong.test')):
            with pytest.raises(NetworkError, match='NETWORK_TLS_FAILED') as error:
                get(broker, http, tls=True, hostname=hostname)
            assert not error.value.dispatched
        assert len(http.hits) == 1
        evidence('https_verified_hostname', http, passed=True, TLSVerificationDisabled=False,
                 fixtureCA=True, untrustedRejected=True, wrongHostnameRejected=True)


def test_native_transport_does_not_follow_redirect():
    def redirect(h):
        h.send_response(302); h.send_header('Location', '/forbidden'); h.end_headers()
    with server(redirect) as http:
        hop = get(HttpFetchBroker(), http, '/start')
        assert hop.status == 302 and hop.location == '/forbidden' and not hop.body
        assert [h['path'] for h in http.hits] == ['/start']
        evidence('transport_no_auto_redirect', http, passed=True)


class FixtureResolverBroker(HttpFetchBroker):
    """Test-only DNS substitution, actual production get() and real sockets."""
    def __init__(self, http):
        super().__init__()
        self.http = http

    def resolve(self, host, port, budget):
        budget.check()
        return (NetworkEndpoint(self.http.server_address[0], self.http.address_family, port),)


class FixtureAdmissionService(NetworkFetchService):
    """Permit only the explicitly selected private fixture; never product default."""
    def _admit(self, endpoints):
        if not endpoints or any(e.address != self.broker.http.server_address[0] for e in endpoints):
            raise NetworkError('NETWORK_DESTINATION_DENIED')


def test_native_application_redirect_then_blocked_target_no_connection(tmp_path):
    with server() as forbidden:
        def handler(h):
            if h.path == '/start':
                h.send_response(302); h.send_header('Location', '/second'); h.end_headers()
            else:
                h.send_response(302)
                h.send_header('Location', 'http://127.0.0.1:'+str(forbidden.server_port)+'/forbidden')
                h.end_headers()
        with server(handler) as http:
            service = FixtureAdmissionService(FixtureResolverBroker(http), DEFAULT_FETCH_LIMITS)
            rt = ToolRuntime(ToolRegistry([WebFetchTool()]), network_service=service)
            url = 'http://server.test:'+str(http.server_port)+'/start'
            inv = invocation(tmp_path, 'web_fetch', {'url':url})
            result = rt.execute(inv)
            assert result.status is ToolStatus.OUTCOME_UNKNOWN
            assert result.metadata['securityErrorCode'] == 'NETWORK_DESTINATION_DENIED'
            assert [h['path'] for h in http.hits] == ['/start', '/second'] and not forbidden.hits
            assert rt.execute(inv) is result and len(http.hits) == 2
            evidence('application_blocked_redirect', http, passed=True, forbiddenHits=len(forbidden.hits),
                     fixtureDNS=True, fixtureAdmission=True, resultMetadata=dict(result.metadata))


def test_native_productive_policy_denies_same_loopback_and_private_dns(tmp_path):
    with server() as http:
        for port, url in ((HttpFetchBroker(), 'http://127.0.0.1:'+str(http.server_port)+'/'),
                          (FixtureResolverBroker(http), 'http://server.test:'+str(http.server_port)+'/')):
            service = NetworkFetchService(port, DEFAULT_FETCH_LIMITS)
            rt = ToolRuntime(ToolRegistry([WebFetchTool()]), network_service=service)
            result = rt.execute(invocation(tmp_path, 'web_fetch', {'url':url}))
            assert result.status is ToolStatus.DENIED
            assert result.metadata['securityErrorCode'] == 'NETWORK_DESTINATION_DENIED'
        assert not http.hits
        evidence('productive_policy_denies_private', http, passed=True, productiveAdmission=True, fixtureDNS=True)


def test_native_productive_ipv6_policy_denies_real_loopback_fixture(tmp_path):
    with server(ipv6=True) as http:
        url = 'http://[::1]:'+str(http.server_port)+'/'
        tool = WebFetchTool()
        assert tool.execute(url=url).startswith('Error:')
        assert not http.hits and http.connections == 0
        evidence('productive_ipv6_denied', http, passed=True, productiveAdmission=True)


def test_native_productive_policy_checks_real_localhost_resolution(tmp_path):
    broker = HttpFetchBroker()
    endpoints = broker.resolve('localhost', 80, budget())
    assert endpoints and all(e.address in ('127.0.0.1', '::1') for e in endpoints)
    with server() as http:
        rt = ToolRuntime(ToolRegistry([WebFetchTool(http_broker=broker)]))
        result = rt.execute(invocation(tmp_path, 'web_fetch', {'url':'http://localhost:'+str(http.server_port)+'/'}))
        assert result.status is ToolStatus.DENIED and result.metadata['securityErrorCode'] == 'NETWORK_DESTINATION_DENIED'
        assert not http.hits and http.connections == 0
        evidence('real_dns_localhost_denied', http, passed=True, realOSResolver=True,
                 resolvedAddresses=[e.address for e in endpoints], productiveAdmission=True)


def test_native_last_guard_rejects_before_tcp_connect():
    def deny():
        raise NetworkError('GRANT_REVOKED')
    with server() as http:
        with pytest.raises(NetworkError, match='GRANT_REVOKED') as error:
            get(HttpFetchBroker(), http, guard=deny)
        assert not error.value.dispatched and not http.hits and http.connections == 0
        evidence('last_guard_before_tcp', http, passed=True)


def test_native_connection_refused_is_typed_without_http_dispatch():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
    listener.close()
    broker = HttpFetchBroker()
    start = time.monotonic()
    with pytest.raises(NetworkError, match='NETWORK_REQUEST_FAILED') as error:
        broker.get('http://server.test:'+str(port)+'/', NetworkEndpoint('127.0.0.1', socket.AF_INET, port),
                   budget=budget(3), body_bytes=100, validate_dispatch=lambda: None)
    elapsed = time.monotonic()-start
    # Native Windows probe reports refusal after ~2 seconds. A .5s budget
    # correctly times out before that event, so it cannot test error mapping.
    assert not error.value.dispatched and elapsed < 3
    evidence('connection_refused', passed=True, realSocket=True, fixtureAddress=['127.0.0.1', port],
             httpDispatched=False, errorCode=error.value.code, configuredSeconds=3, elapsedSeconds=elapsed)


def test_native_application_total_budget_across_redirects(tmp_path):
    def redirect(h):
        time.sleep(.06)
        h.send_response(302); h.send_header('Location', '/next'); h.end_headers()
    with server(redirect) as http:
        limits = replace(DEFAULT_FETCH_LIMITS, timeout_seconds=.14)
        service = FixtureAdmissionService(FixtureResolverBroker(http), limits)
        events = []
        rt = ToolRuntime(ToolRegistry([WebFetchTool()]), network_service=service, publish=events.append)
        inv = invocation(tmp_path, 'web_fetch', {'url':'http://server.test:'+str(http.server_port)+'/start'})
        start = time.monotonic()
        result = rt.execute(inv)
        elapsed = time.monotonic()-start
        assert result.status is ToolStatus.OUTCOME_UNKNOWN
        assert result.metadata['securityErrorCode'] == 'NETWORK_TIMEOUT'
        assert elapsed < .7 and 2 <= len(http.hits) <= 3
        assert rt.execute(inv) is result
        from local_cli.core.contracts import EventKind
        assert sum(e[0] is EventKind.TOOL_FAILED for e in events) == 1
        evidence('total_budget_includes_redirects', http, passed=True, configuredSeconds=.14,
                 elapsedSeconds=elapsed, fixtureDNS=True, fixtureAdmission=True)


def test_native_application_successful_relative_redirect(tmp_path):
    def handler(h):
        if h.path == '/start':
            h.send_response(302); h.send_header('Location', '/final'); h.end_headers()
        else:
            h.send_response(200); h.send_header('Content-Type', 'text/html'); h.end_headers()
            h.wfile.write(b'<p>done</p>')
    with server(handler) as http:
        service = FixtureAdmissionService(FixtureResolverBroker(http), DEFAULT_FETCH_LIMITS)
        rt = ToolRuntime(ToolRegistry([WebFetchTool()]), network_service=service)
        result = rt.execute(invocation(tmp_path, 'web_fetch', {'url':'http://server.test:'+str(http.server_port)+'/start'}))
        assert result.status is ToolStatus.COMPLETED and result.legacy_text == 'done'
        assert [h['path'] for h in http.hits] == ['/start', '/final']
        evidence('application_successful_redirect', http, passed=True, fixtureDNS=True, fixtureAdmission=True,
                 resultMetadata=dict(result.metadata))


def test_native_payload_retained_2mib_and_published_limit(tmp_path):
    def large(h):
        h.send_response(200); h.send_header('Content-Type', 'text/plain'); h.end_headers()
        for _ in range(400):
            h.wfile.write(b'x'*8192)
    with server(large) as http:
        hop = get(HttpFetchBroker(), http)
        assert hop.truncated and len(hop.body) == DEFAULT_FETCH_LIMITS.body_bytes
        service = FixtureAdmissionService(FixtureResolverBroker(http), DEFAULT_FETCH_LIMITS)
        rt = ToolRuntime(ToolRegistry([WebFetchTool()]), network_service=service)
        result = rt.execute(invocation(tmp_path, 'web_fetch', {
            'url':'http://server.test:'+str(http.server_port)+'/', 'max_length':50}))
        assert result.status is ToolStatus.COMPLETED and result.metadata['truncated']
        assert len(result.legacy_text) == 50 and result.legacy_text.endswith('[content truncated]')
        evidence('payload_bounds', http, passed=True, retainedBytes=len(hop.body), publishedCharacters=len(result.legacy_text),
                 fixtureDNS=True, fixtureAdmission=True)


@pytest.mark.parametrize('stage', ['headers', 'body'])
def test_native_total_timeout_interrupts_continuous_trickle(stage):
    def trickle(h):
        if stage == 'headers':
            for char in b'HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\n\r\n':
                h.connection.send(bytes([char])); time.sleep(.025)
        else:
            h.send_response(200); h.send_header('Content-Type', 'text/plain'); h.end_headers()
            for _ in range(50):
                h.wfile.write(b'x'); h.wfile.flush(); time.sleep(.025)
    with server(trickle) as http:
        start = time.monotonic()
        with pytest.raises(NetworkError, match='NETWORK_TIMEOUT') as error:
            get(HttpFetchBroker(), http, operation_budget=budget(.12))
        elapsed = time.monotonic()-start
        assert error.value.dispatched and elapsed < .7 and len(http.hits) == 1
        evidence('total_timeout_'+stage, http, passed=True, configuredSeconds=.12, elapsedSeconds=elapsed)


@pytest.mark.parametrize('repeat', range(5))
def test_native_cancel_interrupts_body_and_closes_socket(repeat):
    ready, peer_closed, peer_states, token = Event(), Event(), [], CancellationController()
    def slow(h):
        h.send_response(200); h.send_header('Content-Type', 'text/plain'); h.end_headers()
        ready.set()
        h.connection.settimeout(1)
        try:
            if h.connection.recv(1) == b'':
                peer_states.append('EOF')
                peer_closed.set()
        except ConnectionResetError:
            # Abort with unread response bytes may use RST instead of FIN.
            # Both prove closure; timeout or a still-open peer does not pass.
            peer_states.append('CONNECTION_RESET')
            peer_closed.set()
    with server(slow) as http:
        creation_start = time.monotonic()
        broker = HttpFetchBroker()
        creation_seconds = time.monotonic()-creation_start
        canceller = Thread(target=lambda: (ready.wait(1), token.request()), daemon=True)
        canceller.start()
        start = time.monotonic()
        with pytest.raises(NetworkError, match='NETWORK_CANCELLED') as error:
            get(broker, http, operation_budget=budget(2, token))
        elapsed = time.monotonic()-start
        evidence('cancel_closes_socket_'+str(repeat), http, clientCreationSeconds=creation_seconds,
                 getElapsedSeconds=elapsed, dispatched=error.value.dispatched, errorCode=error.value.code)
        assert error.value.dispatched and elapsed < .7
        canceller.join(1)
        closed = peer_closed.wait(.5)
        evidence('cancel_peer_closure_'+str(repeat), http, peerClosed=closed, peerStates=peer_states)
        assert closed and peer_states[0] in ('EOF', 'CONNECTION_RESET')


@pytest.mark.parametrize('mode', ['timeout', 'cancel'])
def test_native_tls_handshake_has_total_budget_and_cancellation(mode):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(('127.0.0.1', 0)); listener.listen(1)
    accepted, peer_eof, token = Event(), Event(), CancellationController()
    def stalled_tls_peer():
        conn, _ = listener.accept()
        try:
            accepted.set()
            conn.settimeout(1)
            while conn.recv(4096):
                pass  # consume ClientHello but never respond with ServerHello
            peer_eof.set()
        except OSError:
            pass
        finally:
            conn.close()
    peer = Thread(target=stalled_tls_peer, daemon=True); peer.start()
    broker = HttpFetchBroker()
    endpoint = NetworkEndpoint('127.0.0.1', socket.AF_INET, listener.getsockname()[1])
    canceller = Thread(target=lambda: (accepted.wait(1), token.request()), daemon=True) if mode == 'cancel' else None
    if canceller:
        canceller.start()
    try:
        start = time.monotonic()
        code = 'NETWORK_CANCELLED' if mode == 'cancel' else 'NETWORK_TIMEOUT'
        with pytest.raises(NetworkError, match=code) as error:
            broker.get('https://server.test:'+str(endpoint.port)+'/', endpoint, budget=budget(.12, token),
                       body_bytes=100, validate_dispatch=lambda: None)
        elapsed = time.monotonic()-start
        assert not error.value.dispatched and elapsed < .7 and peer_eof.wait(.5)
        evidence('tls_handshake_'+mode, passed=True, realSocket=True, elapsedSeconds=elapsed,
                 fixtureAddress=['127.0.0.1', endpoint.port], TLSVerificationDisabled=False, peerEOF=True)
    finally:
        listener.close()
        peer.join(1)
        if canceller:
            canceller.join(1)


def test_native_dns_total_budget_and_bounded_lingering_worker(monkeypatch):
    release, entered = Event(), Event()
    def blocked(*_args, **_kwargs):
        entered.set(); release.wait(2)
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', ('8.8.8.8', 80))]
    monkeypatch.setattr(socket, 'getaddrinfo', blocked)
    broker = HttpFetchBroker()
    try:
        start = time.monotonic()
        with pytest.raises(NetworkError, match='NETWORK_TIMEOUT'):
            broker.resolve('fixture.test', 80, budget(.1))
        assert entered.is_set() and time.monotonic()-start < .6
        with pytest.raises(NetworkError, match='NETWORK_DNS_BUSY'):
            broker.resolve('fixture.test', 80, budget())
        evidence('dns_deadline_bounded_worker', passed=True, DNSMock=True, lingeringWorkerLimit=1)
    finally:
        release.set()


@pytest.mark.parametrize('kind', ['binary', 'compressed', 'incomplete', 'duplicate_location'])
def test_native_typed_transport_errors_and_no_retry(kind):
    def invalid(h):
        h.send_response(302 if kind == 'duplicate_location' else 200)
        h.send_header('Content-Type', 'application/octet-stream' if kind == 'binary' else 'text/plain')
        if kind == 'compressed':
            h.send_header('Content-Encoding', 'gzip')
        if kind == 'incomplete':
            h.send_header('Content-Length', '100')
        if kind == 'duplicate_location':
            h.send_header('Location', '/a'); h.send_header('Location', '/b')
        h.end_headers(); h.wfile.write(b'fixture')
    codes = {'binary':'NETWORK_CONTENT_TYPE_DENIED', 'compressed':'NETWORK_CONTENT_ENCODING_DENIED',
             'incomplete':'NETWORK_RESPONSE_INCOMPLETE', 'duplicate_location':'NETWORK_REDIRECT_INVALID'}
    with server(invalid) as http:
        with pytest.raises(NetworkError, match=codes[kind]) as error:
            get(HttpFetchBroker(), http)
        assert error.value.dispatched and len(http.hits) == 1
        evidence('typed_error_'+kind, http, passed=True, errorCode=error.value.code)


def test_native_ollama_provider_host_route_remains_separate(tmp_path, monkeypatch):
    from local_cli.ollama_client import OllamaClient
    for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
        monkeypatch.delenv(key, raising=False)
    def ollama(h):
        h.send_response(200); h.send_header('Content-Type', 'application/json'); h.end_headers()
        h.wfile.write(b'{"models":[{"name":"fixture-only"}]}')
    with server(ollama) as http:
        url = 'http://127.0.0.1:'+str(http.server_port)
        tool = WebFetchTool()
        assert tool.execute(url=url+'/api/tags').startswith('Error:') and not http.hits
        models = OllamaClient(url).list_models()
        assert models == [{'name':'fixture-only'}]
        assert [h['path'] for h in http.hits] == ['/api/tags']
        evidence('provider_host_route', http, passed=True, realOllamaDaemon=False, providerServerFixture=True,
                 productiveWebFetchDenied=True, broker=None, client='local_cli.ollama_client.OllamaClient')
