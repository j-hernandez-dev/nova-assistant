"""Closed private IPC v6; exact host-admitted navigation, never a model API."""
import json
import struct
import time
from local_cli.application.network import canonical_url
from . import transfer_ipc as v5
from . import host_ipc_protocol as v1

FEATURES=v5.FEATURES
ERRORS=v5.ERRORS
HostIpcError=v5.HostIpcError
PRODUCT_ACTIONS=('CLICK','INPUT_TEXT','SELECT_OPTION','PRESS_KEY','NAVIGATE')

def validate(m):
    v1.closed(m,v1.KEYS)
    v1.require(type(m['schemaVersion']) is int and m['schemaVersion']==6,v1.IpcCode.PROTOCOL_MISMATCH)
    copy=dict(m,schemaVersion=5);p=m['payload'];kind=m['messageType']
    if kind=='request':
        command=p.get('command')
        if command=='navigate_admitted':
            v1.require(len(json.dumps(p,ensure_ascii=False,separators=(',',':')).encode())<=v1.MAX_PAYLOAD_BYTES,v1.IpcCode.OVERSIZED_FRAME)
            v1.closed(p,('command','capabilityId','canonicalTarget','ownerSessionId','workspaceDigest','policyRevision','authorityDigest','browserContextEpoch'))
            v1.ref(m['pageRef'],'bwp');v1.ref(p['ownerSessionId'],'ses')
            v1.require(p['capabilityId']=='INTERACTIVE_BROWSER_V1_2')
            try:v1.require(canonical_url(p['canonicalTarget'])==p['canonicalTarget'] and len(p['canonicalTarget'])<=8192)
            except (ValueError,TypeError):raise HostIpcError(v1.IpcCode.INVALID_MESSAGE)from None
            v5.digest(p['workspaceDigest']);v5.digest(p['authorityDigest'])
            v1.integer(p['policyRevision']);v1.integer(p['browserContextEpoch'],minimum=0)
            copy['payload']={'command':'page_metadata'}
        elif command=='act':v1.require(p.get('action')in PRODUCT_ACTIONS)
        else:v1.require(command!='navigate_local')
    if kind=='response' and m['result']:
        r=m['result'];k=r.get('kind')
        if k=='handshake':v1.require(r['ipcVersion']==6);copy['result']=dict(r,ipcVersion=5)
        elif k=='navigate_admitted':
            v1.closed(r,('kind','started','outcome','error','engineEpoch','engineVersion'))
            v1.require(type(r['started'])is bool and r['outcome']in('FAILED_NO_EFFECT_CONFIRMED','SUCCEEDED_OBSERVED','UNKNOWN'))
            v1.require(r['started']or r['outcome']=='FAILED_NO_EFFECT_CONFIRMED')
            v1.integer(r['engineEpoch'],minimum=0);v1.integer(r['engineVersion'],minimum=0)
            v1.require(r['error']is None or r['error']in('OWNERSHIP_MISMATCH','INVALID_ACTION'))
            copy['result']={'kind':'ping','state':'READY','hostPid':1}
    v5.validate(copy);v1._depth(m);return m

def envelope(session,payload,*,kind='request',page=None,timeout_ms=5000):
    v1.integer(timeout_ms,maximum=v1.MAX_DEADLINE_MS)
    return validate(dict(schemaVersion=6,messageType=kind,requestId=v1.opaque('bhr'),browserSessionRef=session,pageRef=page,
        operationId=v1.opaque('op'),deadline=int(time.time()*1000)+timeout_ms,payload=payload,result=None,error=None))
def encode(m):
    validate(m);body=json.dumps(m,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    v1.require(0<len(body)<=v1.MAX_FRAME_BYTES,v1.IpcCode.OVERSIZED_FRAME);return struct.pack('<I',len(body))+body
def decode(body):
    v1.require(0<len(body)<=v1.MAX_FRAME_BYTES,v1.IpcCode.OVERSIZED_FRAME)
    try:return validate(json.loads(body.decode(),object_pairs_hook=v1._pairs,parse_constant=lambda _:(_ for _ in()).throw(ValueError())))
    except HostIpcError:raise
    except(ValueError,TypeError,KeyError,AttributeError,RecursionError):raise HostIpcError(v1.IpcCode.MALFORMED_FRAME)from None
def correlate(request,reply,*,event=None):
    validate(reply)
    for k in('requestId','operationId','browserSessionRef','pageRef','deadline'):
        v1.require(request[k]==reply[k],v1.IpcCode.CORRELATION_MISMATCH)
    v1.require(reply['messageType']==('event'if event else'response'),v1.IpcCode.CORRELATION_MISMATCH)
    if event:v1.require(reply['payload']['event']==event,v1.IpcCode.CORRELATION_MISMATCH)
    elif reply['error']:
        code=reply['error']['code']
        if code in ERRORS:raise HostIpcError(code)
        return v5.correlate(dict(request,schemaVersion=5),dict(reply,schemaVersion=5))
    return reply['result']
