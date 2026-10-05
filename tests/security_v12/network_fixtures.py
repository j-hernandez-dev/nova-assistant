"""Explicit mocked network ports; these never establish a socket connection."""
import socket

from local_cli.core.network import HttpHop, NetworkEndpoint


class ScriptedHTTPPort:
    def __init__(self, hops=(), *, addresses=None, before_get=None):
        self.hops = list(hops) or [HttpHop(200, 'text/plain', None, b'fixture')]
        self.addresses = addresses or {}
        self.before_get = before_get
        self.resolutions, self.gets = [], []

    def resolve(self, host, port, budget):
        budget.check()
        self.resolutions.append((host, port))
        ips = self.addresses.get(host, ('8.8.8.8',))
        return tuple(NetworkEndpoint(ip, socket.AF_INET6 if ':' in ip else socket.AF_INET, port) for ip in ips)

    def get(self, url, endpoint, *, budget, body_bytes, validate_dispatch):
        if self.before_get:
            self.before_get()
        budget.check()
        validate_dispatch()
        self.gets.append((url, endpoint))
        value = self.hops.pop(0)
        if isinstance(value, Exception):
            raise value
        return value
