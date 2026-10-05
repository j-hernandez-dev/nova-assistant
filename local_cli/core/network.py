"""S5 controlled HTTP-fetch contracts, not host socket/firewall contracts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import time
from typing import Callable, Protocol

from local_cli.core.contracts import CancellationToken


class NetworkError(ValueError):
    def __init__(self, code: str, *, dispatched: bool = False):
        self.code, self.dispatched = code, dispatched
        super().__init__(code)


@dataclass(frozen=True)
class FetchLimits:
    timeout_seconds: float
    body_bytes: int
    redirects: int
    published_chars: int

    def __post_init__(self):
        if (type(self.timeout_seconds) not in (float, int)
                or not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0):
            raise ValueError('invalid fetch timeout')
        for name in ('body_bytes', 'redirects', 'published_chars'):
            if type(getattr(self, name)) is not int or getattr(self, name) < (0 if name == 'redirects' else 1):
                raise ValueError('invalid fetch limit: ' + name)


@dataclass(frozen=True)
class NetworkEndpoint:
    address: str
    family: int
    port: int


@dataclass(frozen=True)
class HttpHop:
    status: int
    content_type: str
    location: str | None
    body: bytes
    truncated: bool = False


class FetchBudget:
    """One total deadline for DNS, connect, TLS, headers, body and redirects."""
    def __init__(self, limits: FetchLimits, token: CancellationToken, deadline: datetime | None):
        seconds = limits.timeout_seconds
        if deadline is not None:
            seconds = min(seconds, (deadline - datetime.now(timezone.utc)).total_seconds())
        self.end = time.monotonic() + seconds
        self.token = token

    def check(self):
        if self.token.is_cancel_requested():
            raise NetworkError('NETWORK_CANCELLED')
        if time.monotonic() >= self.end:
            raise NetworkError('NETWORK_TIMEOUT')

    def remaining(self):
        self.check()
        return self.end - time.monotonic()


class HttpFetchPort(Protocol):
    """Resolve without opening HTTP; dispatch GET to exactly the approved IP.

    Implementations must not follow redirects, use ambient proxies/credentials,
    perform a second resolution during connect, or retry a dispatched request.
    TLS must validate the original hostname, even with a pinned IP connection.
    """
    def resolve(self, host: str, port: int, budget: FetchBudget) -> tuple[NetworkEndpoint, ...]: ...

    def get(self, url: str, endpoint: NetworkEndpoint, *, budget: FetchBudget,
            body_bytes: int, validate_dispatch: Callable[[], None]) -> HttpHop: ...
