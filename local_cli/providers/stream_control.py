"""Interrupt a single HTTP stream without changing shared provider state."""

from contextlib import contextmanager
import http.client
import socket
import time
from threading import Event, Lock, Thread
import urllib.request


class StreamCancelled(Exception):
    """The owner cancelled this request; it must not be retried."""


class StreamTimedOut(OSError):
    """A connected request stopped making model-response progress."""


class ResponseDeadline:
    def __init__(self, first_response_timeout, idle_timeout):
        self.first_response_timeout, self.idle_timeout = first_response_timeout, idle_timeout
        self.started = None
        self.last_progress = None

    def connected(self):
        if self.started is None:
            self.started = time.monotonic()

    def progress(self):
        self.last_progress = time.monotonic()

    def expired(self):
        if self.started is None:
            return False
        since = self.last_progress if self.last_progress is not None else self.started
        limit = self.idle_timeout if self.last_progress is not None else self.first_response_timeout
        return time.monotonic() - since >= limit


@contextmanager
def open_stream(request, timeout, should_stop=None, *, response_deadline=None, connect_timeout=5):
    if should_stop is None:
        response = urllib.request.urlopen(request, timeout=timeout)
        try:
            yield response
        finally:
            response.close()
        return
    if should_stop():
        raise StreamCancelled()

    finished, cancelled, timed_out, lock = Event(), Event(), Event(), Lock()
    sockets = []

    def shutdown(connection):
        try:
            connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def register(connection):
        # TCP setup is bounded separately. Connected calls can be interrupted
        # during cold-load/prefill, headers or an incomplete streaming line.
        connection.settimeout(timeout)
        if response_deadline is not None:
            response_deadline.connected()
        with lock:
            sockets.append(connection)
            stop = cancelled.is_set()
        if stop:
            shutdown(connection)

    class HTTPConnection(http.client.HTTPConnection):
        def connect(self):
            super().connect()
            register(self.sock)

    class HTTPSConnection(http.client.HTTPSConnection):
        def connect(self):
            super().connect()
            register(self.sock)

    class HTTPHandler(urllib.request.HTTPHandler):
        def http_open(self, req):
            return self.do_open(HTTPConnection, req)

    class HTTPSHandler(urllib.request.HTTPSHandler):
        def https_open(self, req):
            return self.do_open(HTTPSConnection, req, context=self._context)

    def watch():
        while not finished.wait(0.05):
            if should_stop():
                cancelled.set()
            elif response_deadline is not None and response_deadline.expired():
                timed_out.set()
            else:
                continue
            with lock:
                owned = list(sockets)
            for connection in owned:
                shutdown(connection)
            return

    watcher = Thread(target=watch, name="nova-stream-cancel", daemon=True)
    response = None
    watcher.start()
    try:
        opener = urllib.request.build_opener(HTTPHandler(), HTTPSHandler())
        response = opener.open(request, timeout=min(timeout, connect_timeout))
        if cancelled.is_set():
            raise StreamCancelled()
        yield response
        if timed_out.is_set() and not cancelled.is_set():
            raise StreamTimedOut("Model response deadline exceeded")
    except Exception:
        if cancelled.is_set():
            raise StreamCancelled() from None
        if timed_out.is_set():
            raise StreamTimedOut("Model response deadline exceeded") from None
        raise
    finally:
        finished.set()
        try:
            if response is not None:
                response.close()
        finally:
            watcher.join(timeout=1)
