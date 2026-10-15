"""K2 attachment references are descriptive data, never file authority."""
from dataclasses import dataclass
from typing import Callable, Iterable, Protocol
from local_cli.core.knowledge import (SourceLifecycle, KnowledgeError, KnowledgeErrorCode,
                                     _uuid, _text, _version, _require)


@dataclass(frozen=True)
class AttachmentRef:
    attachment_id: str
    source_id: str
    revision_id: str | None
    display_name: str
    state: SourceLifecycle
    schema_version: int = 1

    def __post_init__(self):
        _version(self.schema_version)
        _uuid(self.attachment_id); _uuid(self.source_id)
        if self.revision_id is not None: _uuid(self.revision_id)
        _text(self.display_name)
        _require(isinstance(self.state, SourceLifecycle))
        if self.state in (SourceLifecycle.READY, SourceLifecycle.PARTIAL):
            _require(self.revision_id is not None)

    def to_dict(self):
        return dict(schemaVersion=1, attachmentId=self.attachment_id, sourceId=self.source_id,
                    revisionId=self.revision_id, displayName=self.display_name, state=self.state.value)

    @classmethod
    def from_dict(cls, data):
        try:
            _require(isinstance(data, dict) and set(data) == {
                'schemaVersion','attachmentId','sourceId','revisionId','displayName','state'})
            return cls(data['attachmentId'],data['sourceId'],data['revisionId'],
                       data['displayName'],SourceLifecycle(data['state']),data['schemaVersion'])
        except (TypeError, KeyError, ValueError):
            raise KnowledgeError(KnowledgeErrorCode.INVALID_CONTRACT) from None


def attachment_refs(data):
    _require(isinstance(data, (list, tuple)))
    refs = tuple(AttachmentRef.from_dict(value) for value in data)
    _require(len({r.attachment_id for r in refs}) == len(refs))
    return refs


class HostFileAcquisitionPort(Protocol):
    """Only Application calls this after an authenticated, explicit host import.

    Selected paths are not obtained from Source.origin, a model or a renderer.
    Infrastructure owns handles and bounded reads; Core owns no host paths.
    """
    def read(self, selected_path: str, *, cancelled: Callable[[], bool],
             progress: Callable[[int], None]) -> Iterable[bytes]: ...
