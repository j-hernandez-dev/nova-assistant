"""Interrupt a single HTTP stream without changing shared provider state."""

from contextlib import contextmanager
import http.client
import socket
from threading import Event, Lock, Thread
import urllib.request


class StreamCancelled(Exception):
    """The owner cancelled this request; it must not be retried."""


@contextmanager
def open_stream(request, timeout, should_stop=None):
    if should_stop is None:
        response = urllib.request.urlopen(request, timeout=timeout)
        try:
            yield response
        finally:
            response.close()
        return
    if should_stop():
        raise StreamCancelled()

    finished, cancelled, lock = Event(), Event(), Lock()
    sockets = []

    def shutdown(connection):
        try:
            connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def register(connection):
        # Connection/TLS setup has a short deadline; generation retains its
        # existing idle deadline and can be interrupted before HTTP headers.
        connection.settimeout(timeout)
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
        response = opener.open(request, timeout=min(timeout, 10))
        if cancelled.is_set():
            raise StreamCancelled()
        yield response
    except (OSError, http.client.HTTPException, ValueError):
        if cancelled.is_set():
            raise StreamCancelled() from None
        raise
    finally:
        finished.set()
        try:
            if response is not None:
                response.close()
        finally:
            watcher.join(timeout=1)
