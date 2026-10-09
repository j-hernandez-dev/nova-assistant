"""S5 stdlib HTTP broker: pinned sockets, verified TLS, no proxy or redirect handler."""
from __future__ import annotations

import http.client
import errno
import io
import ipaddress
import select
import socket
import ssl
from threading import BoundedSemaphore, Event, Lock, Thread
from urllib.parse import urlsplit

from local_cli.core.network import HttpHop, NetworkEndpoint, NetworkError


class _SocketOwner:
    """Own only this fetch's socket; HTTPConnection cannot release it prematurely."""
    def __init__(self):
        self.lock, self.sock, self.closed = Lock(), None, False

    def attach(self, sock):
        with self.lock:
            if self.closed:
                sock.close()
                raise NetworkError('NETWORK_TIMEOUT')
            self.sock = sock

    def abort(self):
        with self.lock:
            self.closed = True
            sock, self.sock = self.sock, None
            if sock is not None:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                sock.close()


def _ready(sock, budget, *, write=False):
    while True:
        budget.check()
        readable, writable, exceptional = select.select([] if write else [sock], [sock] if write else [], [sock],
                                                       min(.02, budget.remaining()))
        if exceptional:
            code = sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            raise OSError(code or errno.ECONNABORTED, 'socket failed')
        if readable or writable:
            budget.check()
            return


class _BudgetReader(io.RawIOBase):
    """Nonblocking reads keep one absolute deadline even for trickle headers/TLS."""
    def __init__(self, sock, budget):
        super().__init__()
        self.sock, self.budget = sock, budget

    def readable(self):
        return True

    def readinto(self, buffer):
        while True:
            self.budget.check()
            if not isinstance(self.sock, ssl.SSLSocket) or not self.sock.pending():
                _ready(self.sock, self.budget)
            try:
                count = self.sock.recv_into(buffer)
                self.budget.check()
                return count
            except (BlockingIOError, ssl.SSLWantReadError):
                continue
            except ssl.SSLWantWriteError:
                _ready(self.sock, self.budget, write=True)


class _BudgetSocket:
    def __init__(self, sock, budget):
        self.sock, self.budget = sock, budget

    def makefile(self, mode):
        if mode != 'rb':
            raise ValueError('read-only HTTP response stream')
        return io.BufferedReader(_BudgetReader(self.sock, self.budget))

    def sendall(self, data):
        view, sent = memoryview(data), 0
        while sent < len(view):
            _ready(self.sock, self.budget, write=True)
            try:
                count = self.sock.send(view[sent:])
                if not count:
                    raise NetworkError('NETWORK_REQUEST_FAILED')
                sent += count
            except (BlockingIOError, ssl.SSLWantWriteError):
                continue
            except ssl.SSLWantReadError:
                _ready(self.sock, self.budget)
        self.budget.check()

    def close(self):
        # HTTPConnection closes after HTTP/1.0 headers. The operation's owner,
        # not that implicit close, releases the response socket in finally.
        pass


class _PinnedConnection(http.client.HTTPConnection):
    def __init__(self, host, port, endpoint, budget, owner, tls_context=None):
        super().__init__(host, port, timeout=budget.remaining())
        self.endpoint, self.budget, self.owner, self.tls_context = endpoint, budget, owner, tls_context

    def connect(self):
        self.budget.check()
        sock = socket.socket(self.endpoint.family, socket.SOCK_STREAM)
        self.owner.attach(sock)
        sock.setblocking(False)
        # address is already a validated numeric literal. No getaddrinfo here.
        code = sock.connect_ex((self.endpoint.address, self.endpoint.port))
        if code not in (0, errno.EINPROGRESS, errno.EWOULDBLOCK, errno.EALREADY, 10035):
            raise OSError(code, 'connect failed')
        if code:
            _ready(sock, self.budget, write=True)
            code = sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if code:
                raise OSError(code, 'connect failed')
        if self.tls_context is not None:
            sock = self.tls_context.wrap_socket(sock, server_hostname=self.host, do_handshake_on_connect=False)
            self.owner.attach(sock)
            while True:
                self.budget.check()
                try:
                    sock.do_handshake()
                    break
                except ssl.SSLWantReadError:
                    _ready(sock, self.budget)
                except ssl.SSLWantWriteError:
                    _ready(sock, self.budget, write=True)
        self.sock = _BudgetSocket(sock, self.budget)


class HttpFetchBroker:
    def __init__(self, *, tls_context=None):
        self._tls_context = tls_context or ssl.create_default_context()
        if (not self._tls_context.check_hostname
                or self._tls_context.verify_mode != ssl.CERT_REQUIRED):
            raise ValueError('verified TLS required')
        # stdlib getaddrinfo is not interruptible. A single daemon resolver per
        # shared broker bounds lingering OS lookups after the caller's deadline;
        # subsequent calls fail fast while it remains busy, never grow a queue.
        self._resolver_slot = BoundedSemaphore(1)

    def resolve(self, host, port, budget):
        budget.check()
        try:
            ip = ipaddress.ip_address(host)
            return (NetworkEndpoint(str(ip), socket.AF_INET6 if ip.version == 6 else socket.AF_INET, port),)
        except ValueError:
            pass
        if not self._resolver_slot.acquire(blocking=False):
            raise NetworkError('NETWORK_DNS_BUSY')
        done, answer = Event(), []
        def resolve():
            try:
                rows = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
                # DNS records and published audit stay finite; excessive answer
                # sets fail closed instead of choosing an unchecked subset.
                if not rows or len(rows) > 64:
                    raise NetworkError('NETWORK_DNS_FAILED')
                endpoints = []
                for family, _, _, _, address in rows:
                    if family not in (socket.AF_INET, socket.AF_INET6):
                        continue
                    e = NetworkEndpoint(str(ipaddress.ip_address(address[0])), family, port)
                    if e not in endpoints:
                        endpoints.append(e)
                answer.append(tuple(endpoints))
            except Exception:
                answer.append(None)
            finally:
                self._resolver_slot.release()
                done.set()
        try:
            Thread(target=resolve, name='nova-http-dns', daemon=True).start()
        except Exception:
            self._resolver_slot.release()
            raise NetworkError('NETWORK_DNS_FAILED') from None
        while not done.wait(min(.02, budget.remaining())):
            budget.check()
        budget.check()
        if not answer or not answer[0]:
            raise NetworkError('NETWORK_DNS_FAILED')
        return answer[0]

    def get(self, url, endpoint, *, budget, body_bytes, validate_dispatch):
        p = urlsplit(url)
        if (p.scheme not in ('http', 'https') or p.hostname is None or p.username is not None
                or p.password is not None or p.fragment or '\\' in url
                or any(c.isspace() or ord(c) < 32 for c in url)):
            raise NetworkError('NETWORK_URL_DENIED')
        port = p.port or (443 if p.scheme == 'https' else 80)
        try:
            ip = ipaddress.ip_address(endpoint.address)
        except ValueError:
            raise NetworkError('NETWORK_ENDPOINT_INVALID') from None
        if (endpoint.port != port or endpoint.family != (socket.AF_INET6 if ip.version == 6 else socket.AF_INET)
                or '%' in endpoint.address or type(body_bytes) is not int or body_bytes < 1):
            raise NetworkError('NETWORK_ENDPOINT_INVALID')
        budget.check()
        owner = _SocketOwner()
        conn = _PinnedConnection(p.hostname, port, endpoint, budget, owner,
                                 self._tls_context if p.scheme == 'https' else None)
        dispatched, response = False, None
        try:
            validate_dispatch()  # before TCP/TLS as well as before the HTTP write
            budget.check()
            conn.connect()
            budget.check()
            validate_dispatch()
            budget.check()
            path = p.path or '/'
            if p.query:
                path += '?' + p.query
            # Only fixed Nova headers; no auth, cookies, .netrc or environment.
            # Set before writing because a partial send cannot safely be retried.
            dispatched = True
            conn.request('GET', path, headers={'User-Agent': 'local-cli/1.0',
                         'Accept-Encoding': 'identity', 'Connection': 'close'})
            response = conn.getresponse()
            budget.check()
            locations = response.headers.get_all('Location', [])
            if len(locations) > 1:
                raise NetworkError('NETWORK_REDIRECT_INVALID')
            location = locations[0] if locations else None
            content_type = response.getheader('Content-Type', '')
            if response.status in (301, 302, 303, 307, 308) or not 200 <= response.status < 300:
                # Do not retain redirect/error bodies or follow at the transport layer.
                return HttpHop(response.status, content_type, location, b'')
            mime = content_type.split(';', 1)[0].strip().lower()
            if mime and not (mime.startswith('text/') or mime in ('application/json', 'application/xml')):
                raise NetworkError('NETWORK_CONTENT_TYPE_DENIED')
            if response.getheader('Content-Encoding', 'identity').lower() not in ('', 'identity'):
                raise NetworkError('NETWORK_CONTENT_ENCODING_DENIED')
            body = bytearray()
            expected = response.length
            while len(body) < body_bytes:
                budget.check()
                chunk = response.read1(min(8192, body_bytes-len(body)))
                if not chunk:
                    if expected is not None and len(body) < min(expected, body_bytes):
                        raise NetworkError('NETWORK_RESPONSE_INCOMPLETE')
                    break
                body.extend(chunk)
            truncated = False
            if len(body) == body_bytes:
                budget.check()
                # One-byte probe is not retained in the result body.
                truncated = bool(response.read1(1))
            budget.check()
            safe_headers = tuple((name, value[:256]) for name in ('ETag', 'Last-Modified')
                if (value := response.getheader(name)) is not None
                and not any(ord(c) < 32 or ord(c) == 127 for c in value))
            return HttpHop(response.status, content_type, location, bytes(body), truncated, safe_headers)
        except NetworkError as exc:
            raise NetworkError(exc.code, dispatched=dispatched or exc.dispatched) from None
        except Exception as error:
            try:
                budget.check()
            except NetworkError as exc:
                code = exc.code
            else:
                code = ('NETWORK_TLS_FAILED' if isinstance(error, ssl.SSLError)
                        else 'NETWORK_TIMEOUT' if isinstance(error, TimeoutError)
                        else 'NETWORK_REQUEST_FAILED')
            raise NetworkError(code, dispatched=dispatched) from None
        finally:
            owner.abort()
            if response is not None:
                response.close()
            conn.close()
