"""Closed v4 typed observation/action IPC; no CDP/eval/selector in requests."""
import json
import struct
import time
from . import guard_ipc as v3
from . import host_ipc_protocol as v1

FEATURES=v3.FEATURES
ACTIONS=('CLICK','INPUT_TEXT','SELECT_OPTION','PRESS_KEY','SCROLL','BACK','FORWARD','WAIT','NAVIGATE','FORM_SUBMIT')
ERRORS=('STALE_TARGET','INVALID_ACTION','OBSERVATION_LIMIT','BUSY','LOCAL_NAVIGATION_FAILED')

def validate(m):
    v1.closed(m,v1.KEYS);v1.require(type(m['schemaVersion']) is int and m['schemaVersion']==4,v1.IpcCode.PROTOCOL_MISMATCH)
    copy=dict(m,schemaVersion=3);p=m['payload'];kind=m['messageType']
    if kind=='request' and p.get('command') in ('capture','resolve','act','navigate_local'):
        v1.require(len(json.dumps(p,ensure_ascii=False,separators=(',',':')).encode('utf-8'))<=v1.MAX_PAYLOAD_BYTES,v1.IpcCode.OVERSIZED_FRAME)
        v1.ref(m['pageRef'],'bwp');cmd=p['command']
        if cmd=='capture':
            v1.closed(p,('command','maxElements','maxText','maxField'))
            for k,cap in (('maxElements',32),('maxText',8192),('maxField',512)):v1.integer(p[k],maximum=cap)
        elif cmd=='resolve':v1.closed(p,('command','binding'));v1.ref(p['binding'],'wvb')
        elif cmd=='navigate_local':v1.closed(p,('command','path'));v1.require(p['path'] in ('index.html','other.html','frame.html'))
        else:
            v1.closed(p,('command','action','binding','text','fields'));v1.require(p['action'] in ACTIONS)
            if p['binding'] is not None:v1.ref(p['binding'],'wvb')
            v1.require(type(p['text']) is str and len(p['text'])<=2048 and type(p['fields']) is list and len(p['fields'])<=32)
            for f in p['fields']:v1.closed(f,('binding','value'));v1.ref(f['binding'],'wvb');v1.require(type(f['value']) is str and len(f['value'])<=1024)
        copy['payload']={'command':'page_metadata'}
    if kind=='event' and p.get('event')=='ACTION_STARTED':
        v1.closed(p,('event',));v1.ref(m['pageRef'],'bwp');copy.update(pageRef=None,payload={'event':'HOST_READY'})
    if kind in ('response','protocol_error') and m['error'] and m['error']['code'] in ERRORS:
        v1.closed(m['error'],('code',));copy['error']={'code':'INVALID_STATE'}
    if kind=='response' and m['result']:
        r=m['result'];k=r.get('kind')
        if k=='handshake':v1.require(r['ipcVersion']==4);copy['result']=dict(r,ipcVersion=3)
        elif k in ('capture','resolve','act','navigate_local'):
            if k=='capture':
                v1.closed(r,('kind','engineEpoch','engineVersion','url','title','text','elements','dialogs'))
                v1.require(type(r['elements']) is list and len(r['elements'])<=33)
                for el in r['elements']:
                    v1.closed(el,('binding','fingerprint','role','name','kind','capabilities','state','href','isForm'));v1.ref(el['binding'],'wvb')
                    v1.require(type(el['fingerprint']) is str and len(el['fingerprint'])==64 and type(el['isForm']) is bool and type(el['capabilities']) is list and all(c in ACTIONS for c in el['capabilities']))
                v1.require(all(type(r[x]) is str for x in ('url','title','text')))
            elif k=='resolve':v1.closed(r,('kind','found','fingerprint','origin','capabilities','engineEpoch','engineVersion'));v1.require(type(r['found']) is bool)
            elif k=='navigate_local':v1.closed(r,('kind','localOnly'));v1.require(r['localOnly'] is True)
            else:
                v1.closed(r,('kind','started','outcome','error','engineEpoch','engineVersion'))
                v1.require(type(r['started']) is bool and r['outcome'] in ('FAILED_NO_EFFECT_CONFIRMED','SUCCEEDED_OBSERVED','PARTIAL','UNKNOWN'))
                v1.require(r['started'] or r['outcome']=='FAILED_NO_EFFECT_CONFIRMED')
            copy['result']={'kind':'ping','state':'READY','hostPid':1}
    v3.validate(copy);v1._depth(m);return m

def envelope(session,payload,*,kind='request',page=None,timeout_ms=5000):
    v1.integer(timeout_ms,maximum=v1.MAX_DEADLINE_MS)
    return validate(dict(schemaVersion=4,messageType=kind,requestId=v1.opaque('bhr'),browserSessionRef=session,pageRef=page,operationId=v1.opaque('op'),deadline=int(time.time()*1000)+timeout_ms,payload=payload,result=None,error=None))
def encode(m):
    validate(m);body=json.dumps(m,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8');v1.require(0<len(body)<=v1.MAX_FRAME_BYTES,v1.IpcCode.OVERSIZED_FRAME)
    return struct.pack('<I',len(body))+body
def decode(body):
    v1.require(0<len(body)<=v1.MAX_FRAME_BYTES,v1.IpcCode.OVERSIZED_FRAME)
    try:return validate(json.loads(body.decode('utf-8'),object_pairs_hook=v1._pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError())))
    except v1.HostIpcError:raise
    except (ValueError,TypeError,KeyError,AttributeError,RecursionError):raise v1.HostIpcError(v1.IpcCode.MALFORMED_FRAME) from None
def correlate(request,reply,*,event=None):
    validate(reply)
    for k in ('requestId','operationId','browserSessionRef','pageRef','deadline'):v1.require(reply[k]==request[k],v1.IpcCode.CORRELATION_MISMATCH)
    v1.require(reply['messageType']==('event' if event else 'response'),v1.IpcCode.CORRELATION_MISMATCH)
    if event:v1.require(reply['payload']['event']==event,v1.IpcCode.CORRELATION_MISMATCH)
    elif reply['error']:
        code=reply['error']['code']
        if code in ERRORS:raise HostIpcError(code)
        surrogate=dict(reply,schemaVersion=3);surrogateRequest=dict(request,schemaVersion=3)
        return v3.correlate(surrogateRequest,surrogate)
    return reply['result']

class HostIpcError(v1.HostIpcError):
    # Opaque typed local error, no backend/payload strings.
    def __init__(self,code):
        self.code=code
        RuntimeError.__init__(self,code)
