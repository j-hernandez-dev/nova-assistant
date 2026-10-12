"""Productive Infrastructure skeleton for a future BrowserPort adapter.

Never registered as a tool/BrowserPort, never returns Active Web capability.
Process/pipe paths are host composition only; no shell or arbitrary commands.
"""
from __future__ import annotations

from enum import Enum
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
from threading import RLock
import time

from .host_ipc_protocol import (HostIpcError, IpcCode, PROTOCOL, MAX_DEADLINE_MS,
                                correlate, encode, envelope, opaque, ref, require)
from .host_named_pipe import NamedPipeTransport
from . import host_ipc_protocol


class HostState(str, Enum):
    NOT_STARTED = 'NOT_STARTED'
    STARTING = 'STARTING'
    READY = 'READY'
    STOPPING = 'STOPPING'
    STOPPED = 'STOPPED'
    FAILED = 'FAILED'
    CLEANUP_UNCONFIRMED = 'CLEANUP_UNCONFIRMED'


class BrowserHostClient:
    wire = host_ipc_protocol

    def _bootstrap_arguments(self):
        return []

    def _receive(self, **kwargs):
        if self.wire is host_ipc_protocol:
            return self.transport.receive(**kwargs)
        return self.transport.receive(**kwargs, decoder=self.wire.decode)

    def __init__(self, dotnet_executable, host_assembly, session):
        ref(session, 'bws')
        self._dotnet, self._assembly = Path(dotnet_executable), Path(host_assembly)
        self.session = session
        self.instance = opaque('bhi')
        self._pipe_name = opaque('nova_browser_host')
        self.process = None
        self.transport = None
        self.state = HostState.NOT_STARTED
        self.history = [self.state.value]
        self.failure = None
        self._lock = RLock()
        self._last = None

    def _state(self, state):
        self.state = state
        self.history.append(state.value)

    @staticmethod
    def _budget(timeout_ms):
        require(type(timeout_ms) is int and 0 <= timeout_ms <= MAX_DEADLINE_MS)
        return time.monotonic() + timeout_ms/1000

    @contextmanager
    def _exclusive(self, timeout_ms, cancel=None):
        end = self._budget(timeout_ms)
        # Waiting for the single IPC owner also consumes this call's budget.
        while not self._lock.acquire(blocking=False):
            NamedPipeTransport.check(end, cancel=cancel)
            time.sleep(min(.005, max(0, end-time.monotonic())))
        try:
            yield end
        finally:
            self._lock.release()

    def _cleanup(self):
        if self.transport is not None:
            self.transport.close()
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._state(HostState.CLEANUP_UNCONFIRMED)

    def _fail(self, error):
        self.failure = error.code
        self._state(HostState.FAILED)
        self._cleanup()

    def start(self, *, timeout_ms=5000, cancel=None):
        with self._exclusive(timeout_ms, cancel) as end:
            require(self.state is HostState.NOT_STARTED, IpcCode.INVALID_STATE)
            self._state(HostState.STARTING)
            try:
                NamedPipeTransport.check(end, cancel=cancel)
                require(os.name == 'nt' and self._dotnet.is_absolute() and self._dotnet.is_file()
                        and self._assembly.is_absolute() and self._assembly.is_file()
                        and self._assembly.name == 'nova-browser-host.dll', IpcCode.PROCESS_START_FAILED)
                env = {k:v for k,v in os.environ.items() if k.upper() in
                       ('SYSTEMROOT', 'WINDIR', 'PROGRAMFILES', 'PROGRAMFILES(X86)', 'PROGRAMDATA')}
                env.update(DOTNET_CLI_TELEMETRY_OPTOUT='1', DOTNET_NOLOGO='1', DOTNET_EnableDiagnostics='0')
                try:
                    self.process = subprocess.Popen([str(self._dotnet), str(self._assembly),
                        '--pipe', self._pipe_name, '--owner-pid', str(os.getpid()),
                        '--session', self.session, '--instance', self.instance, *self._bootstrap_arguments()], shell=False,
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        close_fds=True, env=env, creationflags=subprocess.CREATE_NO_WINDOW)
                except OSError:
                    raise HostIpcError(IpcCode.PROCESS_START_FAILED) from None
                self.transport = NamedPipeTransport.connect(self._pipe_name, self.process.pid,
                    end=end, process=self.process, cancel=cancel)
                request = self.wire.envelope(self.session, dict(command='handshake', clientPid=os.getpid(),
                    expectedHostPid=self.process.pid, hostInstanceRef=self.instance, protocol=PROTOCOL),
                    timeout_ms=max(1, int((end-time.monotonic())*1000)))
                result = self._exchange(request, end, cancel)
                require(result['kind'] == 'handshake' and result['hostPid'] == self.process.pid
                        and result['ownerPid'] == os.getpid() and result['hostInstanceRef'] == self.instance,
                        IpcCode.HANDSHAKE_FAILED)
                self.wire.correlate(request, self._receive(end=end, process=self.process, cancel=cancel), event='HOST_READY')
                self._state(HostState.READY)
                return result
            except HostIpcError as error:
                self._fail(error)
                raise

    def _exchange(self, request, end, cancel=None):
        NamedPipeTransport.check(end, self.process, cancel)
        self.transport.write(self.wire.encode(request), end=end, process=self.process, cancel=cancel)
        reply = self._receive(end=end, process=self.process, cancel=cancel)
        if reply['messageType'] == 'protocol_error':
            require(reply['browserSessionRef'] == self.session, IpcCode.CORRELATION_MISMATCH)
            raise HostIpcError(IpcCode(reply['error']['code']))
        result = self.wire.correlate(request, reply)
        NamedPipeTransport.check(end, self.process, cancel)
        self._last = request
        return result

    def _ready(self):
        require(self.state is not HostState.NOT_STARTED, IpcCode.HOST_NOT_STARTED)
        require(self.state is HostState.READY, IpcCode.INVALID_STATE)

    def ping(self, *, timeout_ms=5000, cancel=None):
        with self._exclusive(timeout_ms, cancel) as end:
            self._ready()
            request = self.wire.envelope(self.session, {'command':'ping'}, timeout_ms=max(1, timeout_ms))
            try:
                result = self._exchange(request, end, cancel)
                require(result['kind'] == 'ping' and result['hostPid'] == self.process.pid, IpcCode.CORRELATION_MISMATCH)
                return result
            except HostIpcError as error:
                self._fail(error)
                raise

    def cancel_last(self, *, timeout_ms=5000):
        with self._exclusive(timeout_ms) as end:
            self._ready(); require(self._last is not None, IpcCode.INVALID_STATE)
            request = self.wire.envelope(self.session, {'targetRequestId':self._last['requestId'],
                'targetOperationId':self._last['operationId']}, kind='cancel', timeout_ms=timeout_ms)
            try:
                return self._exchange(request, end)
            except HostIpcError as error:
                self._fail(error); raise

    def shutdown(self, *, timeout_ms=5000):
        with self._exclusive(timeout_ms) as end:
            if self.state is HostState.NOT_STARTED:
                self._state(HostState.STOPPED); return
            if self.state is HostState.STOPPED:
                return
            if self.state is not HostState.READY:
                self._cleanup(); return  # Does not turn a failure into successful shutdown.
            self._state(HostState.STOPPING)
            try:
                request = self.wire.envelope(self.session, {'command':'shutdown'}, timeout_ms=max(1, timeout_ms))
                # The host may exit immediately after buffering the shutdown receipt.
                self.transport.write(self.wire.encode(request), end=end, process=self.process)
                result = self.wire.correlate(request, self._receive(end=end))
                require(result['kind'] == 'shutdown', IpcCode.CORRELATION_MISMATCH)
                self.wire.correlate(request, self._receive(end=end), event='HOST_STOPPED')
                remaining = max(0, end-time.monotonic())
                try:
                    exit_code = self.process.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    raise HostIpcError(IpcCode.TIMEOUT) from None
                require(exit_code == 0, IpcCode.PROCESS_EXIT_UNEXPECTED)
                self.transport.close()
                self._state(HostState.STOPPED)
            except HostIpcError as error:
                self._fail(error); raise
