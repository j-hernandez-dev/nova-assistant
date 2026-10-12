"""AW4 explicit broker probe, NOT a browser/proxy-bypass certification.

Only the broker's own loopback listener is contacted. No public site, engine
load/install, user config, credentials dump or network best-effort fallback.
"""
import base64
import socket
import math
import time
from urllib.parse import urlsplit

from local_cli.core.contracts import BrowserCapabilitySnapshot, Observation


def probe_browser_broker(broker, *, timeout_seconds):
    network = Observation.known(False)
    try:
        if (type(timeout_seconds) not in (int, float)
                or not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
            raise ValueError('finite probe deadline required')
        end = time.monotonic() + timeout_seconds
        config = broker.configuration
        endpoint = urlsplit(config.server)
        auth = base64.b64encode((config.username + ':' + config.password).encode())
        # Destination loopback is denied by productive admission, not permitted
        # merely because the proxy listener itself is local.
        port = broker.admission.http_ports[0]
        target = ('127.0.0.1:'+str(port)).encode('ascii')
        with socket.create_connection((endpoint.hostname, endpoint.port), timeout=timeout_seconds) as client:
            client.sendall(b'GET http://'+target+b'/ HTTP/1.1\r\nHost: '+target+b'\r\nProxy-Authorization: Basic '
                           +auth+b'\r\n\r\n')
            data = bytearray()
            while len(data) < 4096:
                remaining = end-time.monotonic()
                if remaining <= 0:
                    raise TimeoutError()
                client.settimeout(remaining)
                chunk = client.recv(4096-len(data))
                if not chunk:
                    break
                data.extend(chunk)
        if (bytes(data).startswith(b'HTTP/1.1 403 Forbidden\r\n')
                and bytes(data).endswith(b'BROWSER_EGRESS_DESTINATION_DENIED')):
            network = Observation.known(True)
    except Exception:
        pass  # An explicit false component result; never availability true.
    return BrowserCapabilitySnapshot(
        network_broker=network,
        public_only=Observation.unknown('engine exclusive mediation not probed'),
        available=Observation.unknown('engine/proxy bypass not probed'),
        control_class=Observation.known('HOST_UNISOLATED'))
