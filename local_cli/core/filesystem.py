"""S3 mediation ports. No concrete OS calls or process-isolation claims."""
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol, Any, Callable

from local_cli.core.contracts import ToolInvocation, ToolResult


FILESYSTEM_TOOLS = frozenset({'read', 'write', 'edit', 'glob', 'grep'})


class FilesystemError(ValueError):
    """Safe typed error, including an honestly known effect state."""
    def __init__(self, code, *, effect='none'):
        self.code, self.effect = code, effect
        super().__init__(code)


@dataclass(frozen=True)
class FilesystemRoot:
    path: str
    identity: str


class FilesystemPlanPort(Protocol):
    @property
    def binding(self) -> Mapping[str, Any]: ...
    def validate_current(self) -> None: ...
    def execute(self, guard: Callable[[], None]) -> ToolResult: ...
    def close(self) -> None: ...


class FilesystemBrokerPort(Protocol):
    def bind_root(self, path: Path) -> FilesystemRoot: ...
    def prepare(self, root: FilesystemRoot, invocation: ToolInvocation) -> FilesystemPlanPort: ...
    def close(self) -> None: ...
