"""Explicit host selection for legacy source rebuild, never vector migration.

The opaque legacy key identifies an entry for idempotency/tombstones. Its
metadata/path is not an acquisition authority; original bytes must be selected
again by the host through the existing K2 acquisition port.
"""
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from local_cli.core.knowledge import KnowledgeScope, Source, _text
from local_cli.core.knowledge_store import KnowledgeAccess


@dataclass(frozen=True)
class LegacySourceSelection:
    legacy_key: str
    selected_path: str

    def __post_init__(self):
        _text(self.legacy_key); _text(self.selected_path)


@runtime_checkable
class LegacyRebuildPort(Protocol):
    def reserve_legacy_source(self, legacy_key: str, scope: KnowledgeScope,
                              access: KnowledgeAccess) -> Source: ...
