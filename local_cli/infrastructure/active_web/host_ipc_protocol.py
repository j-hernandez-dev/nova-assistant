"""Closed Infrastructure-only wire protocol. No BrowserPort/authority changes."""
from __future__ import annotations

from enum import Enum
import json
import re
import struct
import time
from uuid import uuid4

SCHEMA_VERSION = 1
PROTOCOL = "nova-browser-host-ipc"
HOST_IDENTITY = "nova-browser-host"
MAX_FRAME_BYTES = 16384
MAX_PAYLOAD_BYTES = 4096
MAX_DEPTH = 8
MAX_REQUESTS = 4096
MAX_DEADLINE_MS = 30000
KEYS = frozenset(("schemaVersion", "messageType", "requestId", "browserSessionRef",
                  "pageRef", "operationId", "deadline", "payload", "result", "error"))


class IpcCode(str, Enum):
    MALFORMED_FRAME = "MALFORMED_FRAME"
    OVERSIZED_FRAME = "OVERSIZED_FRAME"
    INVALID_MESSAGE = "INVALID_MESSAGE"
    UNKNOWN_MESSAGE = "UNKNOWN_MESSAGE"
    PROTOCOL_MISMATCH = "PROTOCOL_MISMATCH"
    CORRELATION_MISMATCH = "CORRELATION_MISMATCH"
    DUPLICATE_REQUEST = "DUPLICATE_REQUEST"
    UNSUPPORTED_COMMAND = "UNSUPPORTED_COMMAND"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    DISCONNECTED = "DISCONNECTED"
    PROCESS_START_FAILED = "PROCESS_START_FAILED"
    HANDSHAKE_FAILED = "HANDSHAKE_FAILED"
    PROCESS_EXIT_UNEXPECTED = "PROCESS_EXIT_UNEXPECTED"
    UNAUTHORIZED_CLIENT = "UNAUTHORIZED_CLIENT"
    HOST_NOT_STARTED = "HOST_NOT_STARTED"
    INVALID_STATE = "INVALID_STATE"
    CLEANUP_UNCONFIRMED = "CLEANUP_UNCONFIRMED"
    REQUEST_LIMIT = "REQUEST_LIMIT"


class HostIpcError(RuntimeError):
    def __init__(self, code: IpcCode):
        self.code = code
        super().__init__(code.value)  # Never echo frames, args, paths or secrets.


def require(value, code=IpcCode.INVALID_MESSAGE):
    if not value:
        raise HostIpcError(code)


def opaque(prefix):
    return prefix + "_" + uuid4().hex


def ref(value, prefix):
    require(isinstance(value, str) and re.fullmatch(prefix + "_[0-9a-f]{32}", value))


def integer(value, minimum=1, maximum=2**53-1):
    require(type(value) is int and minimum <= value <= maximum)


def closed(value, keys):
    require(type(value) is dict and set(value) == set(keys))


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def _depth(value, level=0):
    require(level <= MAX_DEPTH)
    if isinstance(value, dict):
        for child in value.values():
            _depth(child, level + 1)
    elif isinstance(value, list):
        for child in value:
            _depth(child, level + 1)


def validate(message):
    closed(message, KEYS)
    require(type(message['schemaVersion']) is int and message['schemaVersion'] == SCHEMA_VERSION,
            IpcCode.PROTOCOL_MISMATCH)
    kind = message['messageType']
    require(kind in ('request', 'response', 'event', 'cancel', 'protocol_error'), IpcCode.UNKNOWN_MESSAGE)
    ref(message['browserSessionRef'], 'bws')
    if message['pageRef'] is not None:
        ref(message['pageRef'], 'bwp')
    if kind == 'protocol_error':
        require(message['requestId'] is None and message['operationId'] is None and message['pageRef'] is None)
    else:
        ref(message['requestId'], 'bhr'); ref(message['operationId'], 'op')
    integer(message['deadline'])
    require(type(message['payload']) is dict)
    _depth(message)
    require(len(json.dumps(message['payload'], ensure_ascii=False).encode('utf-8')) <= MAX_PAYLOAD_BYTES)
    result, error, payload = message['result'], message['error'], message['payload']
    if kind in ('response', 'protocol_error'):
        closed(payload, ())
        require((result is None) != (error is None))
        if error is not None:
            closed(error, ('code',))
            require(error['code'] in {v.value for v in IpcCode})
        else:
            require(kind == 'response')
            validate_result(result)
    else:
        require(result is None and error is None)
        if kind == 'request':
            command = payload.get('command')
            require(command in ('handshake', 'ping', 'shutdown', 'reserved_browser'), IpcCode.UNSUPPORTED_COMMAND)
            if command == 'handshake':
                closed(payload, ('command', 'clientPid', 'expectedHostPid', 'hostInstanceRef', 'protocol'))
                integer(payload['clientPid'], maximum=2**32-1)
                integer(payload['expectedHostPid'], maximum=2**32-1)
                ref(payload['hostInstanceRef'], 'bhi')
                require(payload['protocol'] == PROTOCOL, IpcCode.PROTOCOL_MISMATCH)
            else:
                closed(payload, ('command',))
            require((message['pageRef'] is not None) == (command == 'reserved_browser'))
        elif kind == 'cancel':
            closed(payload, ('targetRequestId', 'targetOperationId'))
            ref(payload['targetRequestId'], 'bhr'); ref(payload['targetOperationId'], 'op')
            require(message['pageRef'] is None)
        else:
            closed(payload, ('event',))
            require(payload['event'] in ('HOST_READY', 'HOST_STOPPED') and message['pageRef'] is None)
    return message


def validate_result(result):
    require(type(result) is dict)
    kind = result.get('kind')
    if kind == 'handshake':
        closed(result, ('kind', 'hostIdentity', 'hostInstanceRef', 'hostPid', 'ownerPid',
                        'ipcProtocol', 'ipcVersion', 'features', 'activeWebAvailable'))
        require(result['hostIdentity'] == HOST_IDENTITY and result['ipcProtocol'] == PROTOCOL)
        require(type(result['ipcVersion']) is int and result['ipcVersion'] == 1)
        require(result['activeWebAvailable'] is False)
        ref(result['hostInstanceRef'], 'bhi')
        integer(result['hostPid'], maximum=2**32-1); integer(result['ownerPid'], maximum=2**32-1)
        require(result['features'] == ['ping', 'cancel', 'shutdown'])
    elif kind == 'ping':
        closed(result, ('kind', 'state', 'hostPid'))
        require(result['state'] == 'READY'); integer(result['hostPid'], maximum=2**32-1)
    elif kind == 'shutdown':
        closed(result, ('kind', 'state')); require(result['state'] == 'STOPPING')
    elif kind == 'cancel':
        closed(result, ('kind', 'disposition')); require(result['disposition'] == 'ALREADY_COMPLETED')
    else:
        raise HostIpcError(IpcCode.INVALID_MESSAGE)


def envelope(session, payload, *, kind='request', page=None, timeout_ms=5000):
    integer(timeout_ms, maximum=MAX_DEADLINE_MS)
    return validate(dict(schemaVersion=1, messageType=kind, requestId=opaque('bhr'),
                         browserSessionRef=session, pageRef=page, operationId=opaque('op'),
                         deadline=int(time.time()*1000)+timeout_ms, payload=payload, result=None, error=None))


def encode(message):
    validate(message)
    body = json.dumps(message, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
    require(0 < len(body) <= MAX_FRAME_BYTES, IpcCode.OVERSIZED_FRAME)
    return struct.pack('<I', len(body)) + body


def decode(body):
    require(0 < len(body) <= MAX_FRAME_BYTES, IpcCode.OVERSIZED_FRAME)
    try:
        message = json.loads(body.decode('utf-8', errors='strict'), object_pairs_hook=_pairs,
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        return validate(message)
    except HostIpcError:
        raise
    except (ValueError, TypeError, RecursionError):
        raise HostIpcError(IpcCode.MALFORMED_FRAME) from None


def correlate(request, reply, *, event=None):
    validate(reply)
    for key in ('requestId', 'operationId', 'browserSessionRef', 'pageRef', 'deadline'):
        require(request[key] == reply[key], IpcCode.CORRELATION_MISMATCH)
    require(reply['messageType'] == ('event' if event else 'response'), IpcCode.CORRELATION_MISMATCH)
    if event:
        require(reply['payload']['event'] == event, IpcCode.CORRELATION_MISMATCH)
    elif reply['error']:
        raise HostIpcError(IpcCode(reply['error']['code']))
    return reply['result']
