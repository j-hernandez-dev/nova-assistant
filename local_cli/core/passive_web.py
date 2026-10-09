"""K6 passive-search data/port contracts. No browser, sockets or credentials."""
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol
from datetime import datetime

from local_cli.core.knowledge import (_DTO, _require, _text, _digest, _time, _version,
    SourceLocator, LocatorKind)
from local_cli.core.contracts import CancellationToken
from local_cli.core.network import FetchedSnapshot


class WebSearchState(str, Enum):
    DISABLED = 'DISABLED'
    UNAVAILABLE = 'UNAVAILABLE'
    AVAILABLE = 'AVAILABLE'
    DEGRADED = 'DEGRADED'


class WebSearchError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__('Passive search unavailable.')


@dataclass(frozen=True)
class SearchOptions(_DTO):
    max_results: int = 5
    schema_version: int = 1

    def __post_init__(self):
        _version(self.schema_version)
        _require(type(self.max_results) is int and 1 <= self.max_results <= 10)


@dataclass(frozen=True)
class SearchResult(_DTO):
    title: str
    url: str
    snippet: str
    rank: int
    provenance: str = 'SEARCH_PROVIDER_SNIPPET'
    schema_version: int = 1

    def __post_init__(self):
        _version(self.schema_version)
        _text(self.title)
        _require(len(self.title) <= 512 and isinstance(self.snippet, str)
            and len(self.snippet) <= 4000 and '\x00' not in self.snippet)
        _require(type(self.rank) is int and 1 <= self.rank <= 10
            and self.provenance == 'SEARCH_PROVIDER_SNIPPET')
        self.locator  # Syntax only: a result URL is not authority to fetch it.

    @property
    def locator(self):
        return SourceLocator(LocatorKind.SEARCH_RESULT, {'url': self.url, 'rank': self.rank})


@dataclass(frozen=True)
class SearchResponse(_DTO):
    provider_id: str
    query_fingerprint: str
    acquired_at: datetime
    results: tuple[SearchResult, ...]
    truncated: bool = False
    schema_version: int = 1

    def __post_init__(self):
        _version(self.schema_version)
        _text(self.provider_id)
        _digest(self.query_fingerprint)
        _time(self.acquired_at)
        _require(isinstance(self.results, tuple) and len(self.results) <= 10
            and all(isinstance(r, SearchResult) for r in self.results)
            and [r.rank for r in self.results] == list(range(1, len(self.results)+1))
            and type(self.truncated) is bool)


class WebSearchPort(Protocol):
    """Host-configured passive provider; acquire is a one-operation S5 callback.

    The provider does not own network authority. Application binds its URL into
    the exact grant and refuses any callback URL different from that binding.
    No browser session, automatic page fetch or corpus/Memory write.
    """
    provider_id: str
    state: WebSearchState
    def request_url(self, query: str, options: SearchOptions) -> str: ...
    def search(self, query: str, options: SearchOptions, cancellation: CancellationToken,
               acquire: Callable[[str], FetchedSnapshot]) -> SearchResponse: ...
