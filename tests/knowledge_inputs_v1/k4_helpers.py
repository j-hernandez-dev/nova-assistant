"""Synthetic K3/K4 producers on a real local SQLite store, not model quality."""
from dataclasses import replace
from uuid import UUID, uuid5
from local_cli.core.knowledge import (KnowledgeScope, KnowledgeScopeKind, SourceKind,
    SourceLifecycle, SourceTrustClass)
from local_cli.core.knowledge_store import KnowledgeAccess
from local_cli.infrastructure.knowledge_extraction import prepare_revision
from tests.knowledge_inputs_v1.k1_helpers import (ACCESS, AT, OTHER_SESSION, OTHER_WORKSPACE,
    source, begin)


def publish_text(store, text, *, src=None, access=ACCESS, filename='synthetic.txt', partial=False):
    data = text.encode('utf-8') if isinstance(text, str) else text
    op = begin(store, src=src, access=access)
    digest, size = store.stage(op.operation_id, access, [data], lambda:False)
    prepared = prepare_revision(op, digest, size, data, filename)
    if partial:
        from local_cli.core.knowledge import ExtractionStatus
        prepared = replace(prepared, document=replace(prepared.document,
            extraction_completeness=ExtractionStatus.PARTIAL, warnings=('synthetic partial',)),
            revision=replace(prepared.revision, extraction_status=ExtractionStatus.PARTIAL))
    return store.publish(op.operation_id, access, prepared, lambda:False), prepared


def load_corpus(store, dataset):
    sources, revisions, prior = {}, {}, {}
    for row in dataset['sources']:
        access = OTHER_WORKSPACE if row['scope']=='FOREIGN_WORKSPACE' else OTHER_SESSION if row['scope']=='OTHER_SESSION' else ACCESS
        scope = KnowledgeScopeKind.SESSION if row['scope'] in ('SESSION','OTHER_SESSION') else KnowledgeScopeKind.WORKSPACE
        src = replace(source(scope, access), source_id=str(uuid5(UUID('0a40d7a9-03f7-4e98-b848-a5f26b0c8f8b'),row['id'])),
            kind=SourceKind(row['kind']))
        sources[row['id']] = src.source_id
        if row.get('priorText'):
            src, previous = publish_text(store, row['priorText'], src=src, access=access, filename=row['filename'])
            prior[row['id']] = previous.revision.revision_id
        if row['state']=='FAILED':
            from local_cli.core.contracts import OperationStatus
            from local_cli.core.knowledge import KnowledgeError
            op = begin(store, src=src, access=access)
            digest,size = store.stage(op.operation_id, access, [row['text'].encode()], lambda:False)
            try: prepare_revision(op,digest,size,row['text'].encode(),row['filename'])
            except KnowledgeError as exc:
                assert exc.code=='CORRUPT_DOCUMENT'
                store.finish(op.operation_id,access,OperationStatus.FAILED,exc.code)
            else: raise AssertionError('Corrupt fixture unexpectedly extracted')
            continue
        src, prepared = publish_text(store,row['text'],src=src,access=access,filename=row['filename'],partial=row['state']=='PARTIAL')
        revisions[row['id']] = prepared.revision.revision_id
        if row['state']=='DELETED': store.delete(src.source_id,access)
    return sources,revisions,prior


def case_filters(case, sources, revisions, prior):
    from local_cli.core.knowledge_retrieval import DocumentRetrievalFilter
    raw = case.get('filters',{})
    return DocumentRetrievalFilter(source_ids=tuple(sources[k] for k in raw.get('sourceKeys',())),
        revision_ids=(prior[raw['previousRevision']],) if raw.get('previousRevision') else (),
        scope=KnowledgeScopeKind(raw['scope']) if 'scope' in raw else None,
        states=tuple(SourceLifecycle(v) for v in raw.get('states',('READY','PARTIAL'))),
        kinds=tuple(SourceKind(v) for v in raw.get('kinds',())), media_types=tuple(raw.get('mediaTypes',())))
