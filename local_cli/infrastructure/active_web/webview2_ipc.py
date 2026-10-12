"""Closed v2 offline-lifecycle extension. V1's codec remains pinned to v1.

No URI, script, selector, credentials, authority, or page-to-host messaging.
"""
from enum import Enum
import json
import struct
import time

from . import host_ipc_protocol as v1

FEATURES = ['ping', 'cancel', 'shutdown', 'offline_lifecycle']
COMMANDS = ('session_create', 'page_create', 'page_metadata', 'runtime_metadata',
            'page_close', 'session_close')
PAGE_COMMANDS = ('page_create', 'page_metadata', 'page_close')


class EngineCode(str, Enum):
    RUNTIME_ABSENT = 'RUNTIME_ABSENT'
    RUNTIME_INCOMPATIBLE = 'RUNTIME_INCOMPATIBLE'
    ENVIRONMENT_CREATION_FAILED = 'ENVIRONMENT_CREATION_FAILED'
    CONTROL_CREATION_FAILED = 'CONTROL_CREATION_FAILED'
    WEBVIEW2_PROCESS_FAILED = 'WEBVIEW2_PROCESS_FAILED'
    NOT_SUPPORTED_IN_CURRENT_BLOCK = 'NOT_SUPPORTED_IN_CURRENT_BLOCK'
    OWNERSHIP_MISMATCH = 'OWNERSHIP_MISMATCH'


class EngineIpcError(v1.HostIpcError):
    pass


RUNTIME_KEYS = ('kind', 'engine', 'sdkVersion', 'runtimeVersion', 'architecture',
                'platform', 'hostInstanceRef', 'contextEpoch', 'udfIdentity',
                'processes', 'configuration', 'requiredApiMetadata')
CONFIG_KEYS = ('additionalBrowserArguments', 'exclusiveUserDataFolderAccess',
               'targetCompatibleBrowserVersion', 'initialContent', 'webMessageEnabled',
               'hostObjectsAllowed', 'devToolsEnabled', 'inPrivate')
API_KEYS = ('environment', 'controller', 'processInfos', 'browserProcessExited',
            'launchingExternalUriSchemeSdk', 'externalProtocolGuardCertified')


def result(r):
    v1.require(type(r) is dict)
    kind = r.get('kind')
    if kind == 'handshake':
        v1.require(r.get('ipcVersion') == 2 and r.get('features') == FEATURES)
        v1.validate_result(dict(r, ipcVersion=1, features=['ping', 'cancel', 'shutdown']))
    elif kind in ('ping', 'shutdown', 'cancel'):
        v1.validate_result(r)
    elif kind == 'runtime_metadata':
        v1.closed(r, RUNTIME_KEYS)
        v1.require(r['engine'] == 'WINDOWS_WEBVIEW2' and r['platform'] == 'win32'
                   and r['architecture'] == 'X64' and r['sdkVersion'] == '1.0.4258.31')
        v1.require(isinstance(r['runtimeVersion'], str) and 0 < len(r['runtimeVersion']) < 100)
        v1.ref(r['hostInstanceRef'], 'bhi'); v1.integer(r['contextEpoch'])
        v1.require(isinstance(r['udfIdentity'], str) and len(r['udfIdentity']) == 64)
        v1.closed(r['configuration'], CONFIG_KEYS); v1.closed(r['requiredApiMetadata'], API_KEYS)
        c, a = r['configuration'], r['requiredApiMetadata']
        v1.require(c['initialContent'] == 'about:blank' and c['inPrivate'] is True
                   and c['exclusiveUserDataFolderAccess'] is True
                   and all(c[k] is False for k in ('webMessageEnabled', 'hostObjectsAllowed', 'devToolsEnabled')))
        v1.require(isinstance(c['additionalBrowserArguments'], str) and len(c['additionalBrowserArguments']) < 1024)
        v1.require(isinstance(c['targetCompatibleBrowserVersion'], str))
        v1.require(all(a[k] is True for k in API_KEYS if k != 'externalProtocolGuardCertified')
                   and a['externalProtocolGuardCertified'] is False)
        v1.require(type(r['processes']) is list and 0 < len(r['processes']) <= 128)
        for p in r['processes']:
            v1.closed(p, ('pid', 'kind', 'imageIdentity'))
            v1.integer(p['pid'], maximum=2**32-1)
            v1.require(isinstance(p['kind'], str) and len(p['kind']) < 64)
            v1.require(isinstance(p['imageIdentity'], str) and len(p['imageIdentity']) == 64)
    elif kind in ('session_create', 'page_create', 'page_metadata'):
        v1.closed(r, ('kind', 'hostInstanceRef', 'contextEpoch', 'state'))
        v1.ref(r['hostInstanceRef'], 'bhi'); v1.integer(r['contextEpoch'])
        v1.require(r['state'] == 'READY')
    elif kind in ('page_close', 'session_close'):
        v1.closed(r, ('kind', 'closed', 'cleanupConfirmed'))
        v1.require(r['closed'] is True and type(r['cleanupConfirmed']) is bool)
        if kind == 'session_close': v1.require(r['cleanupConfirmed'] is True)
    else:
        raise v1.HostIpcError(v1.IpcCode.INVALID_MESSAGE)


def validate(m):
    v1.closed(m, v1.KEYS)
    v1.require(type(m['schemaVersion']) is int and m['schemaVersion'] == 2, v1.IpcCode.PROTOCOL_MISMATCH)
    # Reuse v1's strict envelope validation, never its command/authority surface.
    surrogate = dict(m, schemaVersion=1)
    kind = m['messageType']
    if kind == 'request' and m['payload'].get('command') in COMMANDS:
        v1.closed(m['payload'], ('command',))
        v1.require((m['pageRef'] is not None) == (m['payload']['command'] in PAGE_COMMANDS))
        surrogate.update(pageRef='bwp_'+'0'*32, payload={'command':'reserved_browser'})
    elif kind in ('response', 'protocol_error') and m['error'] is not None:
        v1.closed(m['error'], ('code',))
        v1.require(m['error']['code'] in {c.value for c in (*v1.IpcCode, *EngineCode)})
        surrogate['error'] = {'code':'INVALID_STATE'}
    elif kind == 'response' and m['result'] is not None:
        result(m['result'])
        surrogate['result'] = {'kind':'ping', 'state':'READY', 'hostPid':1}
    v1.validate(surrogate)
    v1._depth(m)
    return m


def envelope(session, payload, *, kind='request', page=None, timeout_ms=5000):
    v1.integer(timeout_ms, maximum=v1.MAX_DEADLINE_MS)
    return validate(dict(schemaVersion=2, messageType=kind, requestId=v1.opaque('bhr'),
                         browserSessionRef=session, pageRef=page, operationId=v1.opaque('op'),
                         deadline=int(time.time()*1000)+timeout_ms, payload=payload, result=None, error=None))


def encode(m):
    validate(m)
    body = json.dumps(m, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
    v1.require(0 < len(body) <= v1.MAX_FRAME_BYTES, v1.IpcCode.OVERSIZED_FRAME)
    return struct.pack('<I', len(body)) + body


def decode(body):
    v1.require(0 < len(body) <= v1.MAX_FRAME_BYTES, v1.IpcCode.OVERSIZED_FRAME)
    try:
        return validate(json.loads(body.decode('utf-8'), object_pairs_hook=v1._pairs,
                                  parse_constant=lambda _: (_ for _ in ()).throw(ValueError())))
    except v1.HostIpcError: raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
        raise v1.HostIpcError(v1.IpcCode.MALFORMED_FRAME) from None


def correlate(request, reply, *, event=None):
    validate(reply)
    for k in ('requestId', 'operationId', 'browserSessionRef', 'pageRef', 'deadline'):
        v1.require(request[k] == reply[k], v1.IpcCode.CORRELATION_MISMATCH)
    v1.require(reply['messageType'] == ('event' if event else 'response'), v1.IpcCode.CORRELATION_MISMATCH)
    if event: v1.require(reply['payload']['event'] == event, v1.IpcCode.CORRELATION_MISMATCH)
    elif reply['error']:
        code = reply['error']['code']
        if code in {c.value for c in EngineCode}: raise EngineIpcError(EngineCode(code))
        raise v1.HostIpcError(v1.IpcCode(code))
    return reply['result']
