"""Small internal browser lifecycle port; no model tools or policy composition."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class BrowserUnavailable(RuntimeError):
    """An operational browser failure with a stable, bounded public reason."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class BrowserNavigation:
    url: str
    title: str


@dataclass(frozen=True)
class BrowserRead:
    url: str
    title: str
    text: str
    truncated: bool


@dataclass(frozen=True)
class BrowserCloseReceipt:
    host_exited: bool
    job_empty: bool
    profile_removed: bool
    graceful: bool
    forced: bool = False
    errors: tuple[str, ...] = ()


class BrowserSessionPort(Protocol):
    def start(self) -> BrowserSessionPort: ...
    def navigate(self, url: str) -> BrowserNavigation: ...
    def read(self, *, max_chars: int = 16000) -> BrowserRead: ...
    def close(self) -> BrowserCloseReceipt: ...


class BrowserService:
    """Trusted application entry point for a supplied browser session adapter."""

    def __init__(self, session: BrowserSessionPort):
        self._session = session

    def start(self) -> BrowserService:
        self._session.start()
        return self

    def navigate(self, url: str) -> BrowserNavigation:
        return self._session.navigate(url)

    def read(self, *, max_chars: int = 16000) -> BrowserRead:
        return self._session.read(max_chars=max_chars)

    def close(self) -> BrowserCloseReceipt:
        return self._session.close()

    def __enter__(self) -> BrowserService:
        return self.start()

    def __exit__(self, *_exc) -> None:
        self.close()
