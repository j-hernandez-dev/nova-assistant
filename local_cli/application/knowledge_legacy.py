"""Explicit legacy source rebuild: K2 acquisition -> K3 -> K4 -> atomic FTS.

Never opens a legacy index, its paths or its vectors. The caller supplies host
selected originals, not model/legacy-row authority. Legacy bytes are untouched
on success, failure or interruption. Supplied selections are not auto-scanned.
"""
from dataclasses import dataclass
from pathlib import Path

from local_cli.core.contracts import OperationStatus, new_operation_id
from local_cli.core.knowledge import (KnowledgeError, KnowledgeErrorCode,
    KnowledgeScope, KnowledgeScopeKind)
from local_cli.core.knowledge_legacy import LegacyRebuildPort, LegacySourceSelection


@dataclass(frozen=True)
class LegacyRebuildResult:
    completed: tuple[str, ...]
    failed: tuple[tuple[str, str], ...]

    @property
    def status(self): return 'READY' if self.completed and not self.failed else 'LEGACY_REBUILD_REQUIRED'


def rebuild_legacy_sources(service, selections, *, context, acquisition):
    from dataclasses import replace
    service._check(context)
    if not isinstance(service.store, LegacyRebuildPort): raise KnowledgeError(KnowledgeErrorCode.LEGACY_REBUILD_REQUIRED)
    if not isinstance(selections, tuple) or not all(isinstance(s, LegacySourceSelection) for s in selections):
        raise KnowledgeError(KnowledgeErrorCode.INVALID_CONTRACT)
    if len({s.legacy_key for s in selections}) != len(selections):
        raise KnowledgeError(KnowledgeErrorCode.INVALID_CONTRACT)
    scope = KnowledgeScope(KnowledgeScopeKind.WORKSPACE, service.access.workspace_id)
    completed, failed = [], []
    for selected in selections:
        if context.cancellation_token.is_cancel_requested():
            failed.append((selected.legacy_key, KnowledgeErrorCode.IMPORT_CANCELLED.value)); break
        try:
            source = service.store.reserve_legacy_source(selected.legacy_key, scope, service.access)
            acquired = []
            def payload():
                for block in acquisition.read(selected.selected_path, cancelled=context.cancellation_token.is_cancel_requested,
                                              progress=lambda size: None):
                    acquired.append(block); yield block
            def prepare(op, digest, size):
                return service.extractor(op, digest, size, b''.join(acquired), Path(selected.selected_path).name)
            outcome = service.import_prepared(context=replace(context, operation_id=new_operation_id()),
                scope_kind=scope.kind, kind=source.kind, origin=source.origin,
                display_name=source.display_name, trust_class=source.trust_class,
                payload=payload(), prepare=prepare, source_id=source.source_id)
            if outcome.status is OperationStatus.COMPLETED: completed.append(source.source_id)
            else: failed.append((selected.legacy_key, outcome.error_code))
        except KnowledgeError as exc:
            failed.append((selected.legacy_key, exc.code))
    return LegacyRebuildResult(tuple(completed), tuple(failed))
