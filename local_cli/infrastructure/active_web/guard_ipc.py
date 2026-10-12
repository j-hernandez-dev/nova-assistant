"""Closed v3 read-only guard metadata; no web content or authority in requests."""
import json
import struct
import time
from enum import Enum
from . import webview2_ipc as v2
from . import host_ipc_protocol as v1

class GuardCode(str, Enum):
    UNAVAILABLE = 'GUARD_UNAVAILABLE'
    AUDIT_FAILED = 'GUARD_AUDIT_FAILED'

FEATURES = v2.FEATURES

def validate(m):
    v1.closed(m, v1.KEYS)
    v1.require(type(m['schemaVersion']) is int and m['schemaVersion'] == 3, v1.IpcCode.PROTOCOL_MISMATCH)
    copy = dict(m, schemaVersion=2)
    if m['messageType'] == 'request' and m['payload'].get('command') == 'guard_metadata':
        v1.closed(m['payload'], ('command',)); v1.require(m['pageRef'] is None)
        copy['payload'] = {'command':'runtime_metadata'}
    if m['messageType'] in ('response','protocol_error') and m['error'] and m['error']['code'] in {c.value for c in GuardCode}:
        v1.closed(m['error'], ('code',)); copy['error'] = {'code':'INVALID_STATE'}
    if m['messageType'] == 'response' and m['result']:
        r = m['result']
        if r.get('kind') == 'handshake':
            v1.require(r['ipcVersion'] == 3); copy['result'] = dict(r, ipcVersion=2)
        elif r.get('kind') == 'guard_metadata':
            v1.closed(r, ('kind','browserSessionRef','hostInstanceRef','contextEpoch','externalProtocolGuard','auditGap','policy','popupPolicy','installations','receipts'))
            v1.ref(r['browserSessionRef'],'bws'); v1.ref(r['hostInstanceRef'],'bhi'); v1.integer(r['contextEpoch'])
            v1.require(r['policy'] == r['popupPolicy'] == 'DENY_ALL' and type(r['auditGap']) is bool)
            v1.require(r['externalProtocolGuard'] in ('HOST_PRE_EFFECT_DENY','UNKNOWN'))
            v1.require(type(r['installations']) is list and len(r['installations']) <= 3)
            for i in r['installations']:
                v1.closed(i, ('pageRef','sequence')); v1.ref(i['pageRef'],'bwp'); v1.integer(i['sequence'])
            v1.require(type(r['receipts']) is list and len(r['receipts']) <= 1024)
            for i in r['receipts']:
                v1.closed(i, ('sequence','recordId','pageRef','cancel','outcome','reason','durable'))
                v1.ref(i['pageRef'],'bwp'); v1.integer(i['sequence'])
                v1.require(i['cancel'] is True and i['outcome'] == 'DENIED_PRE_EFFECT' and type(i['durable']) is bool)
                v1.require(i['reason'] in ('EXTERNAL_PROTOCOL_GUARD_DENIAL','POPUP_DENIED_PRE_EFFECT','GUARD_AUDIT_DELIVERY_FAILED'))
                v1.require((i['recordId'] is not None) == i['durable'])
            copy['result'] = {'kind':'ping','state':'READY','hostPid':1}
    v2.validate(copy); v1._depth(m)
    return m

def envelope(session, payload, *, kind='request', page=None, timeout_ms=5000):
    v1.integer(timeout_ms, maximum=v1.MAX_DEADLINE_MS)
    return validate(dict(schemaVersion=3, messageType=kind, requestId=v1.opaque('bhr'),browserSessionRef=session,
        pageRef=page,operationId=v1.opaque('op'),deadline=int(time.time()*1000)+timeout_ms,payload=payload,result=None,error=None))

def encode(m):
    validate(m); body=json.dumps(m,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')
    v1.require(0<len(body)<=v1.MAX_FRAME_BYTES,v1.IpcCode.OVERSIZED_FRAME)
    return struct.pack('<I',len(body))+body

def decode(body):
    v1.require(0<len(body)<=v1.MAX_FRAME_BYTES,v1.IpcCode.OVERSIZED_FRAME)
    try: return validate(json.loads(body.decode('utf-8'),object_pairs_hook=v1._pairs,parse_constant=lambda _: (_ for _ in ()).throw(ValueError())))
    except v1.HostIpcError: raise
    except (ValueError,TypeError,KeyError,AttributeError,RecursionError): raise v1.HostIpcError(v1.IpcCode.MALFORMED_FRAME) from None

def correlate(request,reply,*,event=None):
    validate(reply)
    for k in ('requestId','operationId','browserSessionRef','pageRef','deadline'): v1.require(reply[k]==request[k],v1.IpcCode.CORRELATION_MISMATCH)
    v1.require(reply['messageType']==('event' if event else 'response'),v1.IpcCode.CORRELATION_MISMATCH)
    if event: v1.require(reply['payload']['event']==event,v1.IpcCode.CORRELATION_MISMATCH)
    elif reply['error']:
        code=reply['error']['code']
        if code in {c.value for c in GuardCode}: raise v1.HostIpcError(GuardCode(code))
        if code in {c.value for c in v2.EngineCode}: raise v2.EngineIpcError(v2.EngineCode(code))
        raise v1.HostIpcError(v1.IpcCode(code))
    return reply['result']
