"""Explicit process-scoped DNS endpoint for controlled native fixtures/host wiring.

No address classification: BrowserNetworkPolicy/S5 remains the sole admission.
Queries A and AAAA once, validates the entire finite answer set. No OS resolver
config/hosts file mutation, cache, CNAME chasing or hidden fallback/retry.
Default production composition may keep S5 HttpFetchBroker.resolve unchanged.
"""
import ipaddress
import secrets
import select
import socket
import struct

from local_cli.core.network import NetworkEndpoint, NetworkError


class ProcessScopedDNSResolver:
    def __init__(self, server: NetworkEndpoint, *, observe=None):
        if type(server) is not NetworkEndpoint or server.family not in (socket.AF_INET,socket.AF_INET6):
            raise NetworkError('NETWORK_DNS_FAILED')
        ipaddress.ip_address(server.address)
        self._server,self._observe=server,observe

    @staticmethod
    def _name(data,offset):
        labels=[];seen=set();next_offset=None
        for _ in range(128):
            if offset>=len(data) or offset in seen:raise NetworkError('NETWORK_DNS_FAILED')
            seen.add(offset);size=data[offset];offset+=1
            if size&0xc0==0xc0:
                if offset>=len(data):raise NetworkError('NETWORK_DNS_FAILED')
                pointer=((size&0x3f)<<8)|data[offset]
                if next_offset is None:next_offset=offset+1
                offset=pointer;continue
            if size&0xc0 or size>63:raise NetworkError('NETWORK_DNS_FAILED')
            if size==0:return '.'.join(labels).lower(), next_offset if next_offset is not None else offset
            if offset+size>len(data):raise NetworkError('NETWORK_DNS_FAILED')
            try:labels.append(data[offset:offset+size].decode('ascii'))
            except UnicodeError:raise NetworkError('NETWORK_DNS_FAILED') from None
            offset+=size
        raise NetworkError('NETWORK_DNS_FAILED')

    def resolve(self,host,port,budget):
        try:
            literal=ipaddress.ip_address(host)
            return (NetworkEndpoint(str(literal),socket.AF_INET6 if literal.version==6 else socket.AF_INET,port),)
        except ValueError:pass
        answers=[]
        for qtype in (1,28):
            budget.check();tx=secrets.randbelow(65536)
            try:qname=b''.join(bytes([len(p)])+p.encode('ascii') for p in host.split('.'))+b'\x00'
            except (UnicodeError,ValueError):raise NetworkError('NETWORK_DNS_FAILED') from None
            query=struct.pack('!6H',tx,0x0100,1,0,0,0)+qname+struct.pack('!HH',qtype,1)
            with socket.socket(self._server.family,socket.SOCK_DGRAM) as sock:
                sock.setblocking(False)
                sock.sendto(query,(self._server.address,self._server.port))
                while True:
                    budget.check();ready,_,_=select.select([sock],[],[],min(.02,budget.remaining()))
                    if not ready:continue
                    try:data,sender=sock.recvfrom(8193)
                    except OSError:raise NetworkError('NETWORK_DNS_FAILED') from None
                    if sender[0]!=self._server.address or sender[1]!=self._server.port:
                        raise NetworkError('NETWORK_DNS_FAILED')
                    break
            if len(data)<12 or len(data)>8192:raise NetworkError('NETWORK_DNS_FAILED')
            identity,flags,qd,an,ns,ar=struct.unpack('!6H',data[:12])
            if identity!=tx or not flags&0x8000 or flags&0x7800 or flags&0x0200 or flags&15 or qd!=1 or an>64 or ns or ar:
                raise NetworkError('NETWORK_DNS_FAILED')
            question,offset=self._name(data,12)
            if offset+4>len(data) or question!=host.lower() or struct.unpack('!HH',data[offset:offset+4])!=(qtype,1):
                raise NetworkError('NETWORK_DNS_FAILED')
            offset+=4
            for _ in range(an):
                name,offset=self._name(data,offset)
                if offset+10>len(data):raise NetworkError('NETWORK_DNS_FAILED')
                kind,cls,ttl,size=struct.unpack('!HHIH',data[offset:offset+10]);offset+=10
                if name!=host.lower() or cls!=1 or kind!=qtype or size!=(4 if kind==1 else 16) or offset+size>len(data):
                    raise NetworkError('NETWORK_DNS_FAILED')
                address=str(ipaddress.ip_address(data[offset:offset+size]));offset+=size
                answers.append(NetworkEndpoint(address,socket.AF_INET if kind==1 else socket.AF_INET6,port))
                if len(answers)>64:raise NetworkError('NETWORK_DNS_FAILED')
            if offset!=len(data):raise NetworkError('NETWORK_DNS_FAILED')
            budget.check()
            if self._observe is not None:self._observe(dict(host=host,queryType=qtype,answerCount=an,addresses=[e.address for e in answers],transport='REAL_UDP_PROCESS_SCOPED_DNS'))
        if not answers:raise NetworkError('NETWORK_DNS_FAILED')
        return tuple(answers)
