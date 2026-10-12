"""AW4 bounded authenticated loopback forward proxy / HTTPS CONNECT broker.

Every upstream socket is authorized with fresh DNS, then pinned to the admitted
numeric endpoint. No ambient proxy, retry, redirect, DNS at connect or private
network fallback. CONNECT is an opaque TCP tunnel to that ONE endpoint: it does
not inspect TLS/site credentials or certify remote HTTP/application semantics.

This is NOT a firewall or a browser engine. A future engine must independently
prove exclusive mediation (proxy bypass/SW/WebRTC/QUIC) before availability.
"""
import base64
from dataclasses import dataclass
import hmac
import ipaddress
import re
import secrets
import select
import socket
from threading import BoundedSemaphore, Event, Lock, Thread
import time
from urllib.parse import urlsplit

from local_cli.core.active_web_network import (
    BrowserBrokerCleanup, BrowserBrokerLimits, BrowserConnectionPlan, BrowserEgressError,
    BrowserProxyConfiguration,
)
from local_cli.core.network import FetchBudget, FetchLimits, NetworkError
from local_cli.infrastructure.http_fetch import _PinnedConnection, _SocketOwner, _BudgetSocket

_TOKEN = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_HOP_HEADERS = frozenset(('connection', 'proxy-connection', 'proxy-authorization',
    'proxy-authenticate', 'keep-alive', 'te', 'trailer', 'transfer-encoding', 'upgrade'))


@dataclass(frozen=True)
class _Request:
    method: str
    target: str
    headers: tuple
    content_length: int
    buffered: bytes


class _BrokerToken:
    def __init__(self, broker):
        self.broker = broker

    def is_cancel_requested(self):
        if self.broker._stop.is_set():
            return True
        self.broker.admission.validate_current()
        return False


class BrowserEgressBroker:
    def __init__(self, admission, *, limits: BrowserBrokerLimits):
        if (not isinstance(limits, BrowserBrokerLimits)
                or not callable(getattr(admission, 'authorize', None))
                or not callable(getattr(admission, 'validate_current', None))):
            raise BrowserEgressError('BROWSER_EGRESS_INVALID_CONFIGURATION')
        self.admission, self.limits = admission, limits
        self._lock, self._stop = Lock(), Event()
        self._slots = BoundedSemaphore(limits.max_connections)
        self._listener, self._accept_thread = None, None
        self._workers, self._clients, self._owners = set(), set(), set()
        self._started, self._retired = False, False
        self._configuration = None
        self._auth = 'Basic ' + base64.b64encode(
            ('nova-' + secrets.token_hex(16) + ':' + secrets.token_urlsafe(32)).encode()).decode()
        self._records, self._records_dropped = [], 0

    def start(self):
        # Host-internal only. No model tool, config mutation or auto bootstrap.
        self.admission.validate_current()
        with self._lock:
            if self._started or self._retired:
                raise BrowserEgressError('BROWSER_EGRESS_INVALID_STATE')
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                # Fresh port, no reuse; never bind all interfaces/public address.
                listener.bind(('127.0.0.1', 0))
                listener.listen(self.limits.max_connections)
                listener.settimeout(.05)
                self._listener = listener
                user, password = base64.b64decode(self._auth[6:]).decode().split(':', 1)
                self._configuration = BrowserProxyConfiguration(
                    'http://127.0.0.1:' + str(listener.getsockname()[1]), user, password)
                self._started = True
                self._accept_thread = Thread(target=self._accept, name='nova-browser-proxy', daemon=True)
                self._accept_thread.start()
            except Exception:
                listener.close(); self._listener = None; self._retired = True
                raise BrowserEgressError('BROWSER_EGRESS_START_FAILED') from None
        return self._configuration

    @property
    def configuration(self):
        with self._lock:
            if not self._started or self._stop.is_set():
                raise BrowserEgressError('BROWSER_EGRESS_UNAVAILABLE')
            return self._configuration

    def records(self):
        # Bounded, sanitized transport diagnostics, NOT SecurityAudit or receipts
        # about remote mutations. No bodies, path/query, credentials or headers.
        with self._lock:
            return tuple(dict(r) for r in self._records), self._records_dropped

    def _record(self, plan, *, connected, code):
        row = dict(origin=plan.origin if plan else None,
                   method=plan.method if plan else None,
                   upstreamConnected=connected, errorCode=code, retryAllowed=False)
        with self._lock:
            if len(self._records) < 1024:
                self._records.append(row)
            else:
                self._records_dropped += 1

    def _accept(self):
        while not self._stop.is_set():
            try:
                client, address = self._listener.accept()
            except socket.timeout:
                continue
            except (OSError, AttributeError):
                return
            if address[0] != '127.0.0.1' or not self._slots.acquire(blocking=False):
                self._deny(client, b'HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\nContent-Length: 0\r\n\r\n')
                client.close()
                continue
            worker = Thread(target=self._serve, args=(client,), name='nova-browser-egress', daemon=True)
            with self._lock:
                if self._stop.is_set():
                    client.close(); self._slots.release(); return
                self._clients.add(client); self._workers.add(worker)
                try:
                    worker.start()
                except Exception:
                    self._clients.discard(client); self._workers.discard(worker)
                    client.close(); self._slots.release()

    @staticmethod
    def _deny(client, response):
        # A close with unread input can reset TCP and discard DENY/BUSY on
        # Windows. Half-close + bounded discard avoids that; not a retry or an
        # upstream request. Never retain discarded attacker bytes.
        end, remaining = time.monotonic() + .05, 65536
        try:
            client.settimeout(.05)
            client.sendall(response)
            client.shutdown(socket.SHUT_WR)
            while remaining > 0:
                left = end-time.monotonic()
                if left <= 0:
                    break
                client.settimeout(left)
                data = client.recv(min(8192, remaining))
                if not data:
                    break
                remaining -= len(data)
        except OSError:
            pass  # Hostile/aborted clients cannot force unbounded cleanup.

    def _check(self, budget):
        if self._stop.is_set():
            raise BrowserEgressError('BROWSER_EGRESS_CLOSED')
        budget.check()
        self.admission.validate_current()

    def _recv(self, client, budget, size):
        while True:
            self._check(budget)
            ready, _, _ = select.select([client], [], [], min(.02, budget.remaining()))
            if ready:
                data = client.recv(size)
                if not data:
                    raise BrowserEgressError('BROWSER_EGRESS_INCOMPLETE_REQUEST')
                return data

    def _request(self, client, budget):
        data = bytearray()
        while b'\r\n\r\n' not in data:
            room = self.limits.header_bytes - len(data)
            if room <= 0:
                raise BrowserEgressError('BROWSER_EGRESS_HEADER_LIMIT')
            data.extend(self._recv(client, budget, min(8192, room)))
        head, extra = bytes(data).split(b'\r\n\r\n', 1)
        try:
            lines = head.decode('latin-1').split('\r\n')
            method, target, version = lines.pop(0).split(' ')
            if version != 'HTTP/1.1' or not _TOKEN.fullmatch(method):
                raise ValueError()
            headers = {}
            for line in lines:
                name, value = line.split(':', 1)
                if not _TOKEN.fullmatch(name) or name.lower() in headers:
                    raise ValueError()
                value = value.strip(' \t')
                if any(ord(c) < 32 or ord(c) == 127 for c in value):
                    raise ValueError()
                headers[name.lower()] = value
            if not hmac.compare_digest(headers.get('proxy-authorization', ''), self._auth):
                raise BrowserEgressError('BROWSER_EGRESS_CHANNEL_DENIED')
            if not headers.get('host'):
                raise ValueError()
            # No chunked/body ambiguity, upgrades or implicit continue/retry.
            if any(h in headers for h in ('transfer-encoding', 'upgrade', 'expect')):
                raise BrowserEgressError('BROWSER_EGRESS_HTTP_FRAMING_DENIED')
            if any(n.strip() and not _TOKEN.fullmatch(n.strip())
                   for n in headers.get('connection', '').split(',')):
                raise BrowserEgressError('BROWSER_EGRESS_HTTP_FRAMING_DENIED')
            length = headers.get('content-length', '0')
            if re.fullmatch(r'[0-9]{1,12}', length) is None:
                raise ValueError()
            length = int(length)
            if length > self.limits.request_bytes:
                raise BrowserEgressError('BROWSER_EGRESS_REQUEST_LIMIT')
            if method == 'CONNECT' and length:
                raise BrowserEgressError('BROWSER_EGRESS_HTTP_FRAMING_DENIED')
            if method != 'CONNECT' and len(extra) > length:
                raise BrowserEgressError('BROWSER_EGRESS_HTTP_FRAMING_DENIED')
            return _Request(method, target, tuple(headers.items()), length, extra)
        except BrowserEgressError:
            raise
        except (ValueError, UnicodeError, TypeError):
            raise BrowserEgressError('BROWSER_EGRESS_HTTP_FRAMING_DENIED') from None

    def _connect(self, plan, budget, owner):
        # Defense against a malformed host adapter plan, not a second policy.
        try:
            endpoint = plan.endpoint
            ip = ipaddress.ip_address(endpoint.address)
            if (endpoint.port != plan.port or '%' in endpoint.address
                    or endpoint.family != (socket.AF_INET6 if ip.version == 6 else socket.AF_INET)):
                raise ValueError()
        except (ValueError, AttributeError):
            raise BrowserEgressError('BROWSER_EGRESS_INVALID_ENDPOINT') from None
        self._check(budget)
        conn = _PinnedConnection(plan.host, plan.port, endpoint, budget, owner)
        # Reuses S5 numeric-IP connect_ex (no DNS/ambient proxy/HTTP retry).
        conn.connect()
        return conn.sock.sock

    def _forward_http(self, client, upstream, request, plan, budget):
        headers = dict(request.headers)
        connection_tokens = {n.strip().lower() for n in headers.get('connection', '').split(',')}
        if any(n and not _TOKEN.fullmatch(n) for n in connection_tokens):
            raise BrowserEgressError('BROWSER_EGRESS_HTTP_FRAMING_DENIED')
        u = urlsplit(plan.url)
        path = u.path or '/'
        if u.query:
            path += '?' + u.query
        # Host/content length are generated, never copied from ambiguous input.
        lines = [request.method + ' ' + path + ' HTTP/1.1', 'Host: ' + u.netloc,
                 'Connection: close', 'Content-Length: ' + str(request.content_length)]
        for name, value in request.headers:
            if name not in _HOP_HEADERS | connection_tokens | {'host', 'content-length'}:
                lines.append(name + ': ' + value)
        body = bytearray(request.buffered)
        while len(body) < request.content_length:
            body.extend(self._recv(client, budget, min(8192, request.content_length-len(body))))
        self._check(budget)
        _BudgetSocket(upstream, budget).sendall(('\r\n'.join(lines)+'\r\n\r\n').encode('latin-1'))
        _BudgetSocket(upstream, budget).sendall(body)
        # Never accept a second/pipelined browser request on this socket.
        self._relay(client, upstream, budget, duplex=False)

    def _relay(self, client, upstream, budget, *, duplex, initial_bytes=0):
        total = initial_bytes
        sources = [upstream, client] if duplex else [upstream]
        while sources:
            self._check(budget)
            ready, _, _ = select.select(sources, [], [], min(.02, budget.remaining()))
            for source in ready:
                self._check(budget)
                try:
                    data = source.recv(min(8192, self.limits.relay_bytes-total+1))
                except BlockingIOError:
                    continue
                if not data:
                    return
                total += len(data)
                if total > self.limits.relay_bytes:
                    raise BrowserEgressError('BROWSER_EGRESS_RELAY_LIMIT')
                target = upstream if source is client else client
                self._check(budget)
                _BudgetSocket(target, budget).sendall(data)

    def _serve(self, client):
        owner, plan, connected, code = _SocketOwner(), None, False, None
        token = _BrokerToken(self)
        budget = FetchBudget(FetchLimits(self.limits.timeout_seconds, self.limits.request_bytes, 0, 1), token, None)
        with self._lock:
            self._owners.add(owner)
        try:
            client.setblocking(False)
            request = self._request(client, budget)
            candidate = self.admission.authorize(request.method, request.target, dict(request.headers)['host'], budget)
            if not isinstance(candidate, BrowserConnectionPlan):
                raise BrowserEgressError('BROWSER_EGRESS_INVALID_PLAN')
            plan = candidate
            upstream = self._connect(plan, budget, owner)
            connected = True
            self._check(budget)
            if request.method == 'CONNECT':
                # Acknowledges the tunnel, NEVER remote action success.
                _BudgetSocket(client, budget).sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
                if request.buffered:
                    if len(request.buffered) > self.limits.relay_bytes:
                        raise BrowserEgressError('BROWSER_EGRESS_RELAY_LIMIT')
                    self._check(budget)
                    _BudgetSocket(upstream, budget).sendall(request.buffered)
                self._relay(client, upstream, budget, duplex=True, initial_bytes=len(request.buffered))
            else:
                self._forward_http(client, upstream, request, plan, budget)
        except NetworkError as exc:
            code = exc.code
        except Exception:
            code = 'BROWSER_EGRESS_TRANSPORT_FAILED'
        finally:
            if code and not connected:
                # Never reflect a URL, header, body or upstream error to client.
                data = code.encode('ascii')
                # AW5 interoperability: Chromium sends proxy credentials in
                # response to the HTTP challenge, not a 403 origin denial.
                # Authentication still precedes DNS/connect. Repeating this
                # pre-effect handshake is NOT retrying a started web action.
                status = (b'HTTP/1.1 407 Proxy Authentication Required\r\nProxy-Authenticate: Basic realm="Nova Active Web"\r\n'
                          if code == 'BROWSER_EGRESS_CHANNEL_DENIED' else b'HTTP/1.1 403 Forbidden\r\n')
                self._deny(client, status+b'Connection: close\r\nContent-Type: text/plain\r\nContent-Length: '
                           +str(len(data)).encode()+b'\r\n\r\n'+data)
            owner.abort()
            client.close()
            self._record(plan, connected=connected, code=code)
            from threading import current_thread
            with self._lock:
                self._clients.discard(client); self._owners.discard(owner)
                self._workers.discard(current_thread())
            self._slots.release()

    def close(self, *, timeout_seconds):
        if type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds < float('inf'):
            raise BrowserEgressError('BROWSER_EGRESS_INVALID_LIMIT')
        end = time.monotonic() + timeout_seconds
        self._stop.set()
        with self._lock:
            self._retired = True
            listener, self._listener = self._listener, None
            clients, owners = tuple(self._clients), tuple(self._owners)
            workers = tuple(self._workers)
            accept = self._accept_thread
        if listener is not None:
            listener.close()
        for owner in owners:
            owner.abort()
        for client in clients:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            client.close()
        for worker in ((accept,) if accept else ()) + workers:
            worker.join(max(0, end-time.monotonic()))
        with self._lock:
            return BrowserBrokerCleanup(True, not self._clients and not self._owners,
                sum(w.is_alive() for w in self._workers) + int(bool(accept and accept.is_alive())))
