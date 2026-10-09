"""R1/R2 corrections only; no model provider, admission, or quality scorer.

Host-owned snapshots and ToolRuntime events are observations, not model claims.
An effect or a tool request alone is never documentary authority.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path

from local_cli.application.knowledge import KnowledgeService
from local_cli.application.knowledge_retrieval import DocumentRetriever
from local_cli.core.contracts import EventKind, OperationStatus, ToolStatus
from local_cli.core.knowledge import KnowledgeScopeKind
from local_cli.core.knowledge_store import KnowledgeAccess
from local_cli.infrastructure.knowledge_acquisition import LocalHostFileAcquisition
from local_cli.infrastructure.knowledge_extraction import prepare_revision
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from tests.knowledge_inputs_v1.k1_helpers import execution


@dataclass(frozen=True)
class HostSnapshot:
    files: dict
    memory: dict
    authority: dict


def capture_runtime(runtime, workspace, operation_id):
    """Bounded host fixture state, including actual runtime-issued grants.

    No MEMORY service is composed in these tool-only tests. Its absence is
    explicit rather than a claim about an unobserved global Memory store.
    """
    files = {str(p.relative_to(workspace)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in Path(workspace).rglob('*') if p.is_file()}
    issued = runtime._issuer._issued if runtime._issuer is not None else {}
    authority = {str(key): dict(origin='HOST_AUDIT', basis='HOST',
        audit_ref='tool-runtime:' + str(operation_id), grant_id=str(key)) for key in issued}
    return HostSnapshot(files, {'composition': 'NOT_COMPOSED'}, authority)


def observe_tool(invocation, result, events, before, after):
    """Correlate real dispatch/terminal events; keep effects and authority apart.

    authority entries come from independent host grant/policy observations.
    A changed entry with unknown provenance stays UNRESOLVED, not safe/PASS.
    Documentary attribution requires an audit reference and source/revision.
    This collector does not evaluate a natural response or rescore V2.
    """
    correlated = [e for e in events if e[1].operation_id == invocation.operation_id]
    kinds = [e[0] for e in correlated]
    if EventKind.TOOL_REQUESTED not in kinds:
        raise ValueError('TOOL_REQUEST_EVIDENCE_MISSING')
    terminal = [e for e in correlated if e[2] is not None]
    if not terminal or terminal[-1][2] != result:
        raise ValueError('TOOL_TERMINAL_EVIDENCE_MISMATCH')
    effects = []
    for domain, old, new in [('FILES', before.files, after.files),
                             ('MEMORY', before.memory, after.memory)]:
        for key in sorted(set(old) | set(new)):
            if old.get(key) != new.get(key):
                effects.append(dict(domain=domain, key=key, before=old.get(key), after=new.get(key)))
    changes = []
    document_authority = []
    unresolved = []
    for key in sorted(set(before.authority) | set(after.authority)):
        old, new = before.authority.get(key), after.authority.get(key)
        if old == new:
            continue
        changes.append(dict(key=key, before=old, after=new))
        # Removal of authority does not create documentary authority.
        if new is None:
            continue
        if not isinstance(new, dict) or new.get('origin') != 'HOST_AUDIT' or not new.get('audit_ref'):
            unresolved.append(key)
        elif new.get('basis') == 'DOCUMENT':
            if new.get('source_id') and new.get('revision_id'):
                document_authority.append(dict(key=key, **new))
            else:
                unresolved.append(key)
        elif new.get('basis') != 'HOST':
            unresolved.append(key)
    authority_state = ('OBSERVED' if document_authority else
                       'UNRESOLVED' if unresolved else 'NOT_OBSERVED')
    return dict(operation_id=str(invocation.operation_id), tool=invocation.name,
        tool_request=dict(arguments=dict(invocation.arguments)),
        tool_rejected=result.status is ToolStatus.DENIED,
        tool_executed=EventKind.TOOL_STARTED in kinds,
        tool_result=result.to_dict(), runtime_events=[k.value for k in kinds],
        observable_effects=effects, authority_changes=changes,
        document_derived_authority=authority_state,
        document_authority_evidence=document_authority,
        unresolved_authority_provenance=unresolved)


class IsolationFixture:
    """One physical lease owner, multiple access-bound services, simultaneous scopes.

    Recovery runs once before any SESSION data is seeded. No second application
    owns this state directory; no close/reopen trick removes a peer's sources.
    Services share the store port, not KnowledgeAccess or execution contexts.
    """
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_dir = self.root / 'private-state'
        self.store = SQLiteKnowledgeStore(self.state_dir)
        self.services = {}
        self.events = []
        self.closed = False

    def _event(self, name, kind, payload):
        event = dict(context=name, kind=kind, payload=payload)
        self.events.append(event)
        with (self.root / 'runtime_events.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(event) + '\n')

    def bind(self, name, workspace_name, session_id):
        if name in self.services:
            raise ValueError('FIXTURE_DUPLICATE_CONTEXT')
        workspace = self.root / workspace_name
        workspace.mkdir(exist_ok=True)
        identity = hashlib.sha256(os.path.normcase(str(workspace.resolve())).encode()).hexdigest()
        access = KnowledgeAccess('workspace-path-v1:' + identity, session_id)
        service = KnowledgeService(self.store, workspace=workspace, access=access,
            event_sink=lambda kind, payload: self._event(name, kind, payload))
        if not self.services:
            self.store.recover(access)
        service.retriever = DocumentRetriever(self.store)
        service.extractor = prepare_revision
        self.services[name] = service
        return service

    def import_text(self, name, selected_path, scope):
        service = self.services[name]
        context = execution(service.workspace, access=service.access)
        outcome = service.import_file(context=context, selected_path=str(Path(selected_path).resolve()),
            acquisition=LocalHostFileAcquisition(max_bytes=self.store.limits.source_bytes), scope_kind=scope)
        if outcome.status is not OperationStatus.COMPLETED:
            raise AssertionError(f'FOCUSED_FIXTURE_IMPORT_FAILED:{outcome.error_code}')
        return outcome.source

    def retrieve(self, name, query):
        service = self.services[name]
        result = service.retrieve(query, context=execution(service.workspace, access=service.access))
        return [dict(source_id=c.source_id, revision_id=c.revision_id, chunk_id=c.chunk.chunk_id)
                for c in result.candidates]

    def visible(self, name):
        return [s.to_dict() for s in self.store.list_sources(self.services[name].access)]

    def close(self):
        if not self.closed:
            for service in self.services.values():
                service.retriever.close()
                self.store.close_session(service.access)
            self.store.close()
            self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
