"""Closed opt-in HTTP/1.1 GET/HEAD transport. Import never connects/enables tools.

Reuses S5 pinned connection/owner/readiness; no automatic HTTPConnection.request,
proxy, ambient auth, pooling, redirect or retry. Application is the sole policy.
"""
import hashlib
import ipaddress
from pathlib import Path
import re
import socket
import ssl
from threading import RLock
from urllib.parse import quote, urlsplit

from local_cli.core.controlled_fetch import (
    AdmittedControlledFetchRequest, CONTROLLED_FETCH_CAPABILITY_ID,
    ControlledFetchError, ControlledFetchErrorCode as Error, ControlledFetchHop,
    ControlledFetchMethod, ControlledFetchTransportEvidence, ControlledFetchTransportFailure, require,
)
from local_cli.core.network import NetworkError
from local_cli.infrastructure.http_fetch import _PinnedConnection, _SocketOwner, _ready


class UnconfiguredControlledFetchTransport:
    def validate(self, admitted: AdmittedControlledFetchRequest) -> None:
        raise ControlledFetchError(Error.UNCONFIGURED)

    def dispatch(self, admitted, budget):
        # Defense even if a caller bypassed validate(); no fallback to S5 GET.
        raise ControlledFetchError(Error.UNCONFIGURED)


class _CurrentBudget:
    def __init__(self, budget, guard, plan):self.base,self.guard,self.plan=budget,guard,plan
    def check(self):self.base.check();self.guard(self.plan,'current')
    def remaining(self):self.check();return self.base.remaining()


class RealControlledFetchTransport:
    """Only validate/dispatch are effects port APIs. guard/observer are private host wiring.

    A real socket is opened only after Application confirms a live registered
    plan and claims its one-use dispatch lease. There is no accepted wire IP.
    """
    MAX_STATUS_BYTES=2048
    MAX_HEADER_COUNT=100

    def __init__(self, *, validate_plan, tls_context=None, observe=None):
        require(callable(validate_plan))
        require(observe is None or callable(observe))
        if tls_context is None:
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.load_default_certs()
        else:context=tls_context
        require(type(context) is ssl.SSLContext and context.check_hostname and context.verify_mode==ssl.CERT_REQUIRED,Error.TLS)
        context.set_alpn_protocols(['http/1.1'])
        context.keylog_filename=None
        self._guard,self._tls,self._observe=validate_plan,context,observe
        self._lock,self._active,self._retired=RLock(),set(),{}
        self._identity=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

    def validate(self, admitted):
        require(type(admitted) is AdmittedControlledFetchRequest,Error.ADMISSION)
        self._guard(admitted,'validate')
        require(admitted.request.capability_id==CONTROLLED_FETCH_CAPABILITY_ID,Error.CAPABILITY)
        require(type(admitted.request.method) is ControlledFetchMethod,Error.METHOD)
        u=urlsplit(admitted.canonical_target);e=admitted.endpoint
        try:ip=ipaddress.ip_address(e.address)
        except ValueError:raise ControlledFetchError(Error.ADMISSION) from None
        require('%' not in e.address and e.family==(socket.AF_INET6 if ip.version==6 else socket.AF_INET) and
                e.port==(u.port or (443 if u.scheme=='https' else 80)) and bool(admitted.dns_answers) and
                e in admitted.dns_answers,Error.ADMISSION)
        with self._lock:require(id(admitted) not in self._retired,Error.REPLAY)

    def dispatch(self, admitted, budget):
        # Claim first, even a structurally correct clone cannot reach a socket.
        require(type(admitted) is AdmittedControlledFetchRequest,Error.ADMISSION)
        self._guard(admitted,'claim')
        with self._lock:
            require(id(admitted) not in self._active and id(admitted) not in self._retired,Error.REPLAY)
            require(len(self._active)<2 and len(self._retired)<64,Error.BUSY)
            self._active.add(id(admitted));self._retired[id(admitted)]=admitted
        current=_CurrentBudget(budget,self._guard,admitted)
        owner=_SocketOwner();conn=None;sock=None
        sent=received_headers=received_body=0;connected=False;peer=None;error=None;status=None;complete=False
        tls_verify_code=None
        stage='BEFORE_CONNECT';u=urlsplit(admitted.canonical_target)
        request_limit=admitted.request.limits.max_header_bytes
        response_limit=admitted.request.limits.max_response_bytes
        allowance=admitted.transfer_byte_allowance
        def remaining():return allowance-sent-received_headers-received_body
        def read(size, *, header=False):
            nonlocal received_headers,received_body
            require(remaining()>0,Error.LIMIT)
            size=min(size,remaining())
            # Header reads are single-byte (never prefetch a HEAD/body). Full
            # authority is checked per line; cancellation/deadline on EVERY IO.
            io_budget=budget if header else current
            while True:
                io_budget.check()
                if not isinstance(sock,ssl.SSLSocket) or not sock.pending():_ready(sock,io_budget)
                try:data=sock.recv(size)
                except (BlockingIOError,ssl.SSLWantReadError):continue
                except ssl.SSLWantWriteError:_ready(sock,io_budget,write=True);continue
                if header:received_headers+=len(data)
                else:received_body+=len(data)
                io_budget.check();return data
        def line(maximum):
            current.check()
            buffer=bytearray()
            while True:
                require(len(buffer)<maximum and received_headers<request_limit,Error.LIMIT)
                data=read(1,header=True)
                require(bool(data),Error.FRAMING)
                buffer.extend(data)
                if buffer.endswith(b'\r\n'):
                    current.check();return bytes(buffer[:-2])
                require(not (buffer.endswith(b'\n') and not buffer.endswith(b'\r\n')),Error.FRAMING)
        try:
            current.check()
            host=u.netloc
            path=quote(u.path or '/',safe="/%:@!$&'()*+,;=-._~")
            if u.query:path+='?'+quote(u.query,safe="/%:@!$&'()*+,;=?-._~")
            request=(admitted.request.method.value+' '+path+' HTTP/1.1\r\nHost: '+host+
                '\r\nUser-Agent: Nova-ControlledFetch/1.2\r\nAccept: text/plain, text/html, application/json\r\n'+
                'Accept-Encoding: identity\r\nConnection: close\r\n\r\n').encode('ascii')
            require(len(request)<=request_limit and len(request)<allowance,Error.LIMIT)
            stage='CONNECT_TLS'
            conn=_PinnedConnection(u.hostname,admitted.endpoint.port,admitted.endpoint,current,owner,
                                   self._tls if u.scheme=='https' else None)
            conn.connect();sock=conn.sock.sock
            physical=sock.getpeername();peer=(str(ipaddress.ip_address(physical[0])),physical[1])
            connected=True
            require(peer==(str(ipaddress.ip_address(admitted.endpoint.address)),admitted.endpoint.port),Error.ADMISSION)
            if isinstance(sock,ssl.SSLSocket):require(sock.selected_alpn_protocol() in (None,'http/1.1'),Error.TLS)
            current.check();stage='REQUEST'
            view=memoryview(request)
            while sent<len(view):
                current.check();_ready(sock,current,write=True)
                try:count=sock.send(view[sent:])
                except (BlockingIOError,ssl.SSLWantWriteError):continue
                except ssl.SSLWantReadError:_ready(sock,current);continue
                require(count>0,Error.TRANSPORT);sent+=count
            current.check();stage='HEADERS'
            first=line(self.MAX_STATUS_BYTES)
            require(re.fullmatch(rb'HTTP/1\.1 [1-5][0-9]{2} [\x20-\x7e]*',first) is not None,Error.FRAMING)
            status=int(first[9:12]);require(status>=200 and status!=101,Error.FRAMING)
            headers={};seen=set();count=0
            wanted={'content-length','content-type','transfer-encoding','content-encoding','location','connection'}
            while True:
                raw=line(request_limit)
                if not raw:break
                count+=1;require(count<=self.MAX_HEADER_COUNT,Error.LIMIT)
                require(b':' in raw and raw[:1] not in (b' ',b'\t'),Error.FRAMING)
                name,value=raw.split(b':',1)
                require(re.fullmatch(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+",name) is not None,Error.FRAMING)
                name=name.decode('ascii').lower();value=value.strip(b' \t')
                require(all(c>=32 and c!=127 for c in value),Error.FRAMING)
                if name in wanted:
                    require(name not in seen,Error.FRAMING);seen.add(name)
                    headers[name]=value.decode('latin-1')
            # Conservative declared profile: ANY TE (including chunked) is unsupported.
            require('transfer-encoding' not in headers,Error.FRAMING)
            require(headers.get('content-encoding','identity').lower()=='identity',Error.FRAMING)
            length=None
            if 'content-length' in headers:
                require(re.fullmatch('[0-9]{1,12}',headers['content-length']) is not None,Error.FRAMING)
                length=int(headers['content-length'])
            require(status!=204 or length in (None,0),Error.FRAMING)
            ctype=headers.get('content-type','');location=headers.get('location')
            require(len(ctype)<=256 and (location is None or 0<len(location)<=512),Error.FRAMING)
            stage='BODY';body=bytearray()
            no_body=admitted.request.method is ControlledFetchMethod.HEAD or status in (204,304)
            # Redirect/error bodies are never retained/read: Application decides the next hop.
            if no_body or status in (301,302,303,307,308) or not 200<=status<300:
                complete=True
            else:
                capacity=min(response_limit,remaining())
                require(capacity>0 or length==0,Error.LIMIT)
                wanted_bytes=min(length,capacity) if length is not None else capacity
                while len(body)<wanted_bytes:
                    data=read(min(8192,wanted_bytes-len(body)))
                    if not data:
                        require(length is None or len(body)==length,Error.FRAMING)
                        complete=True;break
                    body.extend(data)
                else:
                    # No one-byte overread. At an EOF-body ceiling completeness is unknown.
                    complete=length is not None and len(body)==length
                if length is not None and length>capacity:complete=False
            current.check()
            return ControlledFetchHop(status,ctype,bytes(body),received_headers,location,complete,sent)
        except Exception as exc:
            if isinstance(exc,ssl.SSLCertVerificationError):tls_verify_code=exc.verify_code
            if peer is None and owner.sock is not None:
                try:
                    physical=owner.sock.getpeername()
                    peer=(str(ipaddress.ip_address(physical[0])),physical[1]);connected=True
                except OSError:pass
            error=exc.code if isinstance(exc,ControlledFetchError) else (
                Error.TLS if isinstance(exc,ssl.SSLError) else Error.TIMEOUT if isinstance(exc,TimeoutError) else
                Error.TIMEOUT if isinstance(exc,NetworkError) and exc.code=='NETWORK_TIMEOUT' else
                Error.CANCELLED if isinstance(exc,NetworkError) and exc.code=='NETWORK_CANCELLED' else
                Error.CONNECT if stage=='CONNECT_TLS' else Error.TRANSPORT)
            evidence=ControlledFetchTransportEvidence(admitted,self,sent,received_headers,received_body,connected,peer,error)
            raise ControlledFetchTransportFailure(evidence) from None
        finally:
            owner.abort()
            if conn is not None:conn.close()
            with self._lock:self._active.discard(id(admitted))
            if self._observe is not None:
                # Bounded fixed telemetry, NO query/path, headers/body/credentials or authority.
                row=dict(capabilityId=CONTROLLED_FETCH_CAPABILITY_ID,operationId=admitted.request.operation_id,
                    transportSha256=self._identity,method=admitted.request.method.value,hop=admitted.hop,
                    origin=u.scheme+'://'+u.netloc,admittedEndpoint=[admitted.endpoint.address,admitted.endpoint.port],
                    dnsAnswers=[[e.address,e.port] for e in admitted.dns_answers],connectedEndpoint=list(peer) if peer else None,
                    connected=connected,httpRequestBytesSent=sent,httpHeaderBytesReceived=received_headers,
                    httpBodyBytesReceived=received_body,tlsMode='STANDARD_HOSTNAME_VERIFICATION' if u.scheme=='https' else 'NONE',
                    tlsHostname=u.hostname if u.scheme=='https' else None,status=status,complete=complete,
                    tlsVerifyCode=tls_verify_code,
                    errorCode=error.value if error else None,stage=stage,retryAllowed=False)
                try:self._observe(row)
                except Exception:pass  # Observation cannot alter dispatch or create retry authority.
