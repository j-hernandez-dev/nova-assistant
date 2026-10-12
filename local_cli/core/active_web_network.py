"""AW4 engine-agnostic, private broker contracts. No browser/grant authority.

PUBLIC_ONLY enforcement of broker sockets is not proof that a future engine
uses them exclusively. DNS, HTTP parsing and sockets remain outside Core.
"""
from dataclasses import dataclass, field
import math
from typing import Protocol

from local_cli.core.network import FetchBudget, NetworkEndpoint, NetworkError


class BrowserEgressError(NetworkError):
    """Typed failure with a fixed, body/URL/credential-free error code."""


@dataclass(frozen=True)
class BrowserBrokerLimits:
    # Required host-supplied operational bounds, not global/OS quotas.
    timeout_seconds: float
    header_bytes: int
    request_bytes: int
    relay_bytes: int
    max_connections: int

    def __post_init__(self):
        if (type(self.timeout_seconds) not in (int, float)
                or not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0):
            raise BrowserEgressError('BROWSER_EGRESS_INVALID_LIMIT')
        for name in ('header_bytes', 'request_bytes', 'relay_bytes', 'max_connections'):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise BrowserEgressError('BROWSER_EGRESS_INVALID_LIMIT')


@dataclass(frozen=True)
class BrowserConnectionPlan:
    method: str
    url: str = field(repr=False)  # Private path/query, never audit/model DTO.
    origin: str
    host: str
    port: int
    endpoint: NetworkEndpoint

    def __post_init__(self):
        if (self.method not in ('GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'CONNECT')
                or any(not isinstance(v, str) or not v for v in (self.url, self.origin, self.host))
                or type(self.port) is not int or not 1 <= self.port <= 65535
                or not isinstance(self.endpoint, NetworkEndpoint)):
            raise BrowserEgressError('BROWSER_EGRESS_INVALID_PLAN')


class BrowserNetworkAdmissionPort(Protocol):
    """Host policy revalidated for EVERY connection, including subresources.

    No plan can authorize browser actions or transfer effects. authorize()
    performs fresh DNS and returns a numeric, admitted, pinned endpoint.
    """
    def authorize(self, method: str, target: str, host_header: str,
                  budget: FetchBudget) -> BrowserConnectionPlan: ...
    def validate_current(self) -> None: ...


@dataclass(frozen=True)
class BrowserProxyConfiguration:
    """Private adapter-only channel; NEVER expose to a page/model/transcript."""
    server: str
    username: str = field(repr=False)
    password: str = field(repr=False)


@dataclass(frozen=True)
class BrowserBrokerCleanup:
    listener_closed: bool
    connections_closed: bool
    workers_remaining: int

    @property
    def confirmed(self):
        # Socket/worker cleanup only, not browser process or OS DNS isolation.
        return self.listener_closed and self.connections_closed and self.workers_remaining == 0
