"""Real owned DNS/HTTP/TLS fixtures. No patched admission/resolver/socket returns.

Synthetic DNS names resolve by actual UDP to an already assigned GLOBAL IPv6.
No private-IP exception, map-to-loopback, hosts/DNS/CA/firewall mutation. Only
test TLSContext trusts the generated exact fixture cert, CERT_REQUIRED remains.
"""
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import socket
import ssl
import struct
import subprocess
import tempfile
from threading import Event,Thread,RLock
import time
from uuid import uuid4

from local_cli.application.cancellation import CancellationController
from local_cli.application.controlled_fetch import ControlledFetchContext,ControlledFetchService,ControlledFetchTurnBudget
from local_cli.application.grants import GrantIssuer
from local_cli.application.network import public_address
from local_cli.application.policy import PolicyEngineV2
from local_cli.core.controlled_fetch import CONTROLLED_FETCH_CAPABILITY_ID as CF,ControlledFetchLimits,ControlledFetchOwner,ControlledFetchError
from local_cli.core.network import NetworkEndpoint
from local_cli.core.security import AuthorityCeiling,Capability,ControlClass,Permission,ResourceScope,ScopeKind
from local_cli.infrastructure.controlled_fetch_dns import ProcessScopedDNSResolver
from local_cli.infrastructure.controlled_fetch_transport import RealControlledFetchTransport
from local_cli.infrastructure.http_fetch import HttpFetchBroker


class DNSFixture:
    def __init__(self,address):
        self.address=address;self.events=[];self.behavior={};self.admissions={};self.stop=Event()
        self.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);self.sock.bind(('127.0.0.1',0));self.sock.settimeout(.05)
        self.port=self.sock.getsockname()[1];self.thread=Thread(target=self.run,daemon=True);self.thread.start()

    def run(self):
        while not self.stop.is_set():
            try:data,peer=self.sock.recvfrom(4096)
            except socket.timeout:continue
            except OSError:return
            try:
                host,offset=ProcessScopedDNSResolver._name(data,12);qtype,qcls=struct.unpack('!HH',data[offset:offset+4])
                behavior=self.behavior.get(host,'public')
                if qtype==1:self.admissions[host]=self.admissions.get(host,0)+1
                step=self.admissions.get(host,1)
                self.events.append(dict(host=host,qtype=qtype,behavior=behavior,step=step))
                if behavior=='timeout':continue
                records=[]
                if behavior=='public':addresses=[] if qtype==1 else [self.address]
                elif behavior=='private':addresses=['127.0.0.1'] if qtype==1 else ['::1']
                elif behavior=='mixed':addresses=['1.1.1.1','127.0.0.1'] if qtype==1 else []
                elif behavior=='excessive':addresses=['1.1.1.1']*65 if qtype==1 else []
                elif behavior=='rebind':addresses=([] if qtype==1 else [self.address]) if step==1 else (['127.0.0.1'] if qtype==1 else ['::1'])
                elif behavior=='rebind-mixed':addresses=([] if qtype==1 else [self.address]) if step==1 else (['1.1.1.1','127.0.0.1'] if qtype==1 else [])
                else:addresses=[]
                for a in addresses:
                    packed=ipaddress.ip_address(a).packed
                    records.append(b'\xc0\x0c'+struct.pack('!HHIH',qtype,1,1,len(packed))+packed)
                identity=struct.unpack('!H',data[:2])[0]
                if behavior=='ambiguous':identity^=1
                reply=struct.pack('!6H',identity,0x8180,1,len(records),0,0)+data[12:offset+4]+b''.join(records)
                self.sock.sendto(reply,peer)
            except (OSError,ValueError,IndexError,struct.error):continue

    def close(self):self.stop.set();self.sock.close();self.thread.join(2)


class HTTPFixture:
    def __init__(self,address,port,tls=None):
        self.address,self.port,self.tls=address,port,tls;self.events=[];self.snis=[];self.routes={};self.stop=Event();self.connections=[]
        family=socket.AF_INET6 if ':' in address else socket.AF_INET
        self.sock=socket.socket(family,socket.SOCK_STREAM)
        if family==socket.AF_INET6:self.sock.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_V6ONLY,1)
        self.sock.bind((address,port));self.sock.listen(8);self.sock.settimeout(.05)
        if tls:tls.set_servername_callback(lambda conn,name,context:self.snis.append(name))
        self.thread=Thread(target=self.run,daemon=True);self.thread.start()

    def run(self):
        while not self.stop.is_set():
            try:connection,peer=self.sock.accept()
            except socket.timeout:continue
            except OSError:return
            self.connections.append(peer)
            Thread(target=self.handle,args=(connection,peer),daemon=True).start()

    def handle(self,connection,peer):
        try:
            connection.settimeout(3)
            if getattr(self,'reset_before_request',False):
                connection.setsockopt(socket.SOL_SOCKET,socket.SO_LINGER,struct.pack('hh' if os.name=='nt' else 'ii',1,0))
                connection.close();self.reset_done.set();return
            if self.tls:connection=self.tls.wrap_socket(connection,server_side=True)
            data=bytearray()
            while b'\r\n\r\n' not in data and len(data)<32768:
                chunk=connection.recv(1024)
                if not chunk:return
                data.extend(chunk)
            first=bytes(data).split(b'\r\n')[0].decode('ascii');method,target,version=first.split(' ')
            path=target.split('?',1)[0]
            headers={n.decode('ascii').lower():v.strip().decode('latin-1') for n,v in
                (line.split(b':',1) for line in bytes(data).split(b'\r\n')[1:] if b':' in line)}
            self.events.append(dict(method=method,path=path,version=version,host=headers.get('host'),
                acceptEncoding=headers.get('accept-encoding'),connection=headers.get('connection'),
                forbiddenHeadersPresent=any(n in headers for n in ('cookie','authorization','proxy-authorization','x-forwarded-for')),
                localEndpoint=list(connection.getsockname()[:2]),peer=list(peer[:2]),requestBytes=len(data)))
            route=self.routes.get(path)
            if callable(route):route(connection,method)
            elif isinstance(route,bytes):connection.sendall(route)
            else:
                body=b'controlled fixture content'
                connection.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: '+str(len(body)).encode()+b'\r\nConnection: close\r\nSet-Cookie: synthetic=ignored\r\n\r\n'+(body if method=='GET' else b''))
        except (OSError,ValueError,ssl.SSLError):pass
        finally:
            try:connection.close()
            except OSError:pass

    def close(self):self.stop.set();self.sock.close();self.thread.join(2)


class Environment:
    def __init__(self,address,openssl):
        if not public_address(address) or ipaddress.ip_address(address).version!=6:raise ValueError('Real assigned global IPv6 required')
        self.address,self.openssl=address,openssl;self.rows=[];self.temp=tempfile.TemporaryDirectory(prefix='nova-cf-b2-')
        self.work=Path(self.temp.name);self.cert=self.work/'fixture-cert.pem';self.key=self.work/'fixture-key.pem'
        flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
        subprocess.run([openssl,'req','-x509','-newkey','rsa:2048','-nodes','-sha256','-days','2',
            '-subj','/CN=cf-public.test','-addext','subjectAltName=DNS:cf-public.test,DNS:cf-rebind.test,DNS:cf-mixed.test',
            '-addext','basicConstraints=critical,CA:TRUE','-addext','keyUsage=critical,keyCertSign,cRLSign,digitalSignature,keyEncipherment',
            '-keyout',str(self.key),'-out',str(self.cert)],check=True,capture_output=True,timeout=20,creationflags=flags)
        self.cert_sha256=hashlib.sha256(self.cert.read_bytes()).hexdigest()
        server_tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);server_tls.load_cert_chain(self.cert,self.key)
        self.http=HTTPFixture(address,80);self.https=HTTPFixture(address,443,server_tls)
        self.private=HTTPFixture('127.0.0.1',80)
        self.dns=DNSFixture(address)
        self.socket_attempts=[];self.live_client_sockets=[];self._socket_original=socket.socket
        original=self._socket_original;attempts=self.socket_attempts;live=self.live_client_sockets
        class ObservedRealSocket(original):
            def connect_ex(self,target):
                if self.type==socket.SOCK_STREAM:
                    attempts.append(dict(family=self.family,target=list(target[:2]),native=True));live.append(self)
                return super().connect_ex(target)
        socket.socket=ObservedRealSocket

    def case(self,name,*,method='GET',tls=False,host='cf-public.test',path='/ok',limits=None,trusted=True,
             resolver_mode='process_dns',policy_mutator=None,dns_port=None,reset_sync=False,capture_service=None,validate_hook=None):
        now=datetime.now(timezone.utc);limits=limits or ControlledFetchLimits(timeout_seconds=3)
        owner=ControlledFetchOwner('ses_'+uuid4().hex,str(self.work),'task_'+uuid4().hex)
        token=CancellationController();context=ControlledFetchContext(owner,'turn_'+uuid4().hex,'op_'+uuid4().hex,1,now+timedelta(seconds=limits.timeout_seconds),token)
        scheme='https' if tls else 'http';origin=scheme+'://'+host
        scope=ResourceScope(ScopeKind.ORIGIN,origin)
        cap=Capability(Permission('network.fetch'),scope,ControlClass.APPLICATION_ENFORCED,{'capabilityId':CF,'profile':'GET_HEAD_CONTRACT_ONLY'})
        issuer=GrantIssuer(AuthorityCeiling('ceiling_b2',1,(cap,)),policy_revision=1);policy=PolicyEngineV2()
        dns_events=[];transport_events=[];receipts=[]
        resolver=ProcessScopedDNSResolver(NetworkEndpoint('127.0.0.1',socket.AF_INET,dns_port or self.dns.port),observe=dns_events.append) if resolver_mode=='process_dns' else HttpFetchBroker()
        def record(receipt):
            # Real fsync sink, private fixture filename; public data is only closed receipt.
            with (self.work/'receipts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(receipt.to_dict())+'\n');f.flush();__import__('os').fsync(f.fileno())
            receipts.append(receipt.to_dict())
            if policy_mutator and receipt.outcome.value=='STARTED':policy_mutator(policy,token)
        service=ControlledFetchService(issuer=issuer,policy=policy,approved_scope=scope,
            turn_budget=ControlledFetchTurnBudget(owner,context.turn_id,limits),record=record,resolver=resolver)
        client_tls=ssl.create_default_context(cafile=str(self.cert)) if trusted else ssl.create_default_context()
        def guard(plan,phase):
            service.transport_guard(plan,phase)
            if phase=='validate' and validate_hook:validate_hook(plan,service)
            if reset_sync and phase=='current':
                # Wait only once a native client socket is actually connected;
                # does not substitute a socket result or transport operation.
                for s in self.live_client_sockets:
                    try:s.getpeername()
                    except OSError:continue
                    if not self.http.reset_done.wait(.5):raise RuntimeError('reset fixture not synchronized')
        service.transport=RealControlledFetchTransport(validate_plan=guard,tls_context=client_tls,observe=transport_events.append)
        target=origin+path
        request=service.request_from_candidate(dict(capabilityId=CF,url=target,method=method,resultMode='TEXT'),context)
        grant=issuer.issue(service.grant_request(request,context),token)
        if capture_service:capture_service(service,request,context,grant)
        h=self.https if tls else self.http
        before=len(h.events);before_connects=len(h.connections);private_before=len(self.private.connections)
        before_socket=len(self.socket_attempts);before_dns=len(self.dns.events);before_sni=len(self.https.snis)
        started=time.monotonic()
        result=service.execute(request,context,grant)
        time.sleep(.02)
        row=dict(case=name,method=method,scheme=scheme,outcome=result.outcome.value,error=result.error.value if result.error else None,
            countedBytes=result.counted_bytes,complete=result.completeness.value,truncated=result.truncated,
            durationSeconds=round(time.monotonic()-started,4),dns=dns_events,transport=transport_events,
            httpCanaryHits=len(h.events)-before,httpCanaryConnections=len(h.connections)-before_connects,
            forbiddenCanaryConnections=len(self.private.connections)-private_before,serverEvents=h.events[before:],
            nativeTCPConnectAttempts=self.socket_attempts[before_socket:],dnsServerPackets=self.dns.events[before_dns:],tlsServerSNI=self.https.snis[before_sni:],
            receipts=[dict(outcome=r['outcome'],consumed=r['consumed']) for r in receipts],
            actualPayloadSha256=hashlib.sha256((result.payload or '').encode()).hexdigest(),
            testTLSExactFixtureTrust=trusted and tls,fixtureCertSha256=self.cert_sha256 if tls else None,
            resolverMode=resolver_mode,retryAllowed=result.to_dict()['retryAllowed'])
        self.rows.append(row)
        return row

    def close(self):
        socket.socket=self._socket_original
        for resource in (self.http,self.https,self.private,self.dns):resource.close()
        self.temp.cleanup()

    def dated_leaf(self,name,start,end):
        csr=self.work/(name+'.csr');leaf=self.work/(name+'.pem')
        index=self.work/(name+'.index');serial=self.work/(name+'.serial');config=self.work/(name+'.cnf')
        index.write_text('');serial.write_text('1000\n')
        config.write_text('[ca]\ndefault_ca=x\n[x]\ndatabase='+index.as_posix()+'\nserial='+serial.as_posix()+
            '\nnew_certs_dir='+self.work.as_posix()+'\ncertificate='+self.cert.as_posix()+'\nprivate_key='+self.key.as_posix()+
            '\ndefault_md=sha256\npolicy=p\nx509_extensions=ext\n[p]\ncommonName=supplied\n[ext]\n'+
            'basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\n'+
            'subjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid\nsubjectAltName=DNS:cf-public.test\n')
        flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
        subprocess.run([self.openssl,'req','-new','-key',str(self.key),'-subj','/CN=leaf-cf-public.test','-out',str(csr)],check=True,capture_output=True,timeout=10,creationflags=flags)
        subprocess.run([self.openssl,'ca','-config',str(config),'-batch','-notext','-startdate',start,'-enddate',end,'-in',str(csr),'-out',str(leaf)],check=True,capture_output=True,timeout=10,creationflags=flags)
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(leaf,self.key)
        context.set_servername_callback(lambda conn,name,ctx:self.https.snis.append(name))
        return context,hashlib.sha256(leaf.read_bytes()).hexdigest()


def run_smoke(address,openssl,output):
    env=Environment(address,openssl)
    try:
        for tls in (False,True):
            for method in ('GET','HEAD'):
                row=env.case(f'positive_{tls}_{method}',tls=tls,method=method)
                assert row['outcome']=='SUCCEEDED_OBSERVED',row
        Path(output).write_text(json.dumps(env.rows,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'realPositiveCases':4,'outcomes':[r['outcome'] for r in env.rows],'physicalIPv6':address}))
    finally:env.close()


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--public-ipv6',required=True);p.add_argument('--openssl',required=True);p.add_argument('--output',required=True)
    args=p.parse_args();run_smoke(args.public_ipv6,args.openssl,args.output)
