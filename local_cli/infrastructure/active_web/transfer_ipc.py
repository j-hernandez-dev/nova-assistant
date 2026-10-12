"""Closed v5 host UI/transfer extension, no original filesystem paths/secrets."""
import json
import struct
import time
from . import action_ipc as v4
from . import host_ipc_protocol as v1
FEATURES=v4.FEATURES
ERRORS=(*v4.ERRORS,'TAKEOVER_ACTIVE','HUMAN_CONTROL_INCOMPLETE','SECRET_BOUNDARY_UNCONFIRMED','TRANSFER_STALE','TRANSFER_INTERRUPTED')
HostIpcError=v4.HostIpcError
def filename(value):
    v1.require(type(value)is str and 0<len(value)<=255 and value not in('.','..')and not any(ord(c)<32 or c in('/','\\',':')for c in value))
def digest(value):v1.require(type(value)is str and len(value)==64 and all(c in '0123456789abcdef'for c in value))
def boolean(value):v1.require(type(value)is bool)
def events(records):
    v1.require(type(records)is list and len(records)<=32)
    fields={'UPLOAD_ASSIGNED':('size','sha256','mime'),'DOWNLOAD_DENIED':('outcome',),'DOWNLOAD_AUTHORIZED':('token','total'),
        'FILE_SECURITY_CHECK':('extension','defaultPolicy','cancelled'),'DOWNLOAD_COMPLETED':('state','size','sha256'),
        'DOWNLOAD_UNCONFIRMED':('errorType','state','bytes','total','reason')}
    for r in records:
        v1.require(type(r)is dict and r.get('kind')in fields);v1.closed(r,('kind',*fields[r['kind']]))
        for key in('size','bytes','total'):
            if key in r and r[key]is not None:v1.integer(r[key],minimum=0)
        if'sha256'in r:digest(r['sha256'])
        if'token'in r:v1.ref(r['token'],'wvd')
        for key in('defaultPolicy','cancelled'):
            if key in r:boolean(r[key])
        if'outcome'in r:v1.require(r['outcome']=='DENIED_PRE_EFFECT')
        if'state'in r:v1.require(r['state']in(None,'InProgress','Interrupted','Completed'))
        for key in('extension','errorType','reason','mime'):
            if key in r and r[key]is not None:v1.require(type(r[key])is str and len(r[key])<=128 and not any(ord(c)<32 or c in('/','\\',':')for c in r[key])if key!='mime'else type(r[key])is str and 0<len(r[key])<=128)

def validate(m):
    v1.closed(m,v1.KEYS);v1.require(type(m['schemaVersion'])is int and m['schemaVersion']==5,v1.IpcCode.PROTOCOL_MISMATCH)
    c=dict(m,schemaVersion=4);p=m['payload'];kind=m['messageType']
    if kind=='request'and p.get('command')in('takeover_begin','transfer_metadata','upload','download','takeover_state','takeover_end'):
        cmd=p['command'];v1.require(len(json.dumps(p,separators=(',',':')).encode())<=v1.MAX_PAYLOAD_BYTES,v1.IpcCode.OVERSIZED_FRAME)
        if cmd in('takeover_state','takeover_end'):
            v1.closed(p,('command',));v1.require(m['pageRef']is None);c['payload']={'command':'guard_metadata'}
        else:
            v1.ref(m['pageRef'],'bwp')
            if cmd=='upload':
                v1.closed(p,('command','binding','source','filename','size','mime','sha256'));v1.ref(p['binding'],'wvb');v1.ref(p['source'],'wvu')
                v1.integer(p['size'],minimum=0);filename(p['filename']);digest(p['sha256'])
                v1.require(type(p['mime'])is str and 0<len(p['mime'])<=128 and not any(ord(c)<32 for c in p['mime']))
            elif cmd=='download':v1.closed(p,('command','binding','maxBytes'));v1.ref(p['binding'],'wvb');v1.integer(p['maxBytes'])
            else:v1.closed(p,('command',))
            c['payload']={'command':'page_metadata'}
    if kind in('response','protocol_error')and m['error']and m['error']['code']in ERRORS:
        v1.closed(m['error'],('code',));c['error']={'code':'INVALID_STATE'}
    if kind=='response'and m['result']:
        r=m['result'];k=r.get('kind')
        if k=='handshake':v1.require(r['ipcVersion']==5);c['result']=dict(r,ipcVersion=4)
        elif k=='guard_metadata':
            v1.integer(r['contextEpoch'],minimum=0);c['result']=dict(r,contextEpoch=1)
        elif k in('session_create','page_create','page_metadata','runtime_metadata'):
            v1.integer(r['contextEpoch'],minimum=0);c['result']=dict(r,contextEpoch=1)
        elif k=='capture':
            c['result']=dict(r,elements=[dict(e,capabilities=[a for a in e['capabilities']if a not in('UPLOAD_FILE','DOWNLOAD')])for e in r['elements']])
            for e in r['elements']:v1.require(all(a in(*v4.ACTIONS,'UPLOAD_FILE','DOWNLOAD')for a in e['capabilities']))
        elif k in('takeover_begin','takeover_end','takeover_state','transfer_metadata','download'):
            if k in('takeover_begin','takeover_end'):v1.closed(r,('kind','humanActive','contextEpoch'));v1.integer(r['contextEpoch'],minimum=0)
            elif k=='takeover_state':v1.closed(r,('kind','humanActive','humanCompleted','humanAborted','contextEpoch'));v1.integer(r['contextEpoch'],minimum=0)
            elif k=='transfer_metadata':v1.closed(r,('kind','humanPaused','events'));boolean(r['humanPaused']);events(r['events'])
            else:
                v1.closed(r,('kind','started','outcome','fileToken','size','mime','sha256','suggestedName','origin'))
                v1.require(type(r['started'])is bool and r['outcome']in('FAILED_NO_EFFECT_CONFIRMED','SUCCEEDED_OBSERVED','UNKNOWN'))
                if r['outcome']=='SUCCEEDED_OBSERVED':
                    v1.require(r['started']is True);v1.ref(r['fileToken'],'wvd');v1.integer(r['size'],minimum=0);digest(r['sha256']);filename(r['suggestedName'])
                    v1.require(type(r['mime'])is str and 0<len(r['mime'])<=128 and type(r['origin'])is str and r['origin'].startswith(('http://','https://')))
                else:v1.require(r['fileToken']is None and r['size']==0 and all(r[n]is None for n in('mime','sha256','suggestedName','origin')))
            if k.startswith('takeover_'):
                for key in('humanActive','humanCompleted','humanAborted'):
                    if key in r:boolean(r[key])
            c['result']={'kind':'ping','state':'READY','hostPid':1}
    v4.validate(c);v1._depth(m);return m
def envelope(session,payload,*,kind='request',page=None,timeout_ms=5000):
    v1.integer(timeout_ms,maximum=v1.MAX_DEADLINE_MS)
    return validate(dict(schemaVersion=5,messageType=kind,requestId=v1.opaque('bhr'),browserSessionRef=session,pageRef=page,operationId=v1.opaque('op'),deadline=int(time.time()*1000)+timeout_ms,payload=payload,result=None,error=None))
def encode(m):
    validate(m);body=json.dumps(m,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode();v1.require(0<len(body)<=v1.MAX_FRAME_BYTES,v1.IpcCode.OVERSIZED_FRAME);return struct.pack('<I',len(body))+body
def decode(body):
    v1.require(0<len(body)<=v1.MAX_FRAME_BYTES,v1.IpcCode.OVERSIZED_FRAME)
    try:return validate(json.loads(body.decode(),object_pairs_hook=v1._pairs,parse_constant=lambda _:(_ for _ in()).throw(ValueError())))
    except v1.HostIpcError:raise
    except(ValueError,TypeError,KeyError,AttributeError,RecursionError):raise v1.HostIpcError(v1.IpcCode.MALFORMED_FRAME)from None
def correlate(request,reply,*,event=None):
    validate(reply)
    for k in('requestId','operationId','browserSessionRef','pageRef','deadline'):v1.require(request[k]==reply[k],v1.IpcCode.CORRELATION_MISMATCH)
    v1.require(reply['messageType']==('event'if event else'response'),v1.IpcCode.CORRELATION_MISMATCH)
    if event:v1.require(reply['payload']['event']==event,v1.IpcCode.CORRELATION_MISMATCH)
    elif reply['error']:
        code=reply['error']['code']
        if code in ERRORS:raise HostIpcError(code)
        return v4.correlate(dict(request,schemaVersion=4),dict(reply,schemaVersion=4))
    return reply['result']
