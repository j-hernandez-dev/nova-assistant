"""K1 unit/contract/native SQLite integration; synthetic projections only."""
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from local_cli.core.contracts import OperationStatus, new_operation_id
from local_cli.core.knowledge import (ExtractionStatus, KnowledgeError, KnowledgeScopeKind,
    SourceLifecycle, new_revision_id)
from local_cli.core.knowledge_store import (DocumentBlock, DocumentChunk, ExtractedDocument,
    KnowledgeAccess, KnowledgeLimits, KnowledgeStorePort, PreparedKnowledgeRevision)
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from tests.knowledge_inputs_v1.k1_helpers import (ACCESS, OTHER_SESSION, OTHER_WORKSPACE, PAYLOAD, TEXT,
    begin, source, staged, published, projection)


@pytest.fixture
def store(tmp_path):
    with SQLiteKnowledgeStore(tmp_path / 'private-state') as value:
        yield value


def test_versioned_store_native_schema_and_ports(store):
    assert isinstance(store, KnowledgeStorePort)
    assert store.path.parent.name == 'v1' and store.path.parent.parent.name == 'knowledge'
    c = store._connection
    assert c.execute('PRAGMA user_version').fetchone()[0] == 1
    assert c.execute('PRAGMA foreign_keys').fetchone()[0] == 1
    assert c.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
    assert c.execute('PRAGMA synchronous').fetchone()[0] == 2
    assert c.execute('PRAGMA foreign_key_check').fetchone() is None
    assert all((store.path.parent / p).is_dir() for p in ('blobs', 'staging', 'cache'))
    assert not list(store.path.parent.rglob('*memory*'))


@pytest.mark.parametrize('cls', [DocumentBlock, DocumentChunk, ExtractedDocument])
def test_storage_projection_roundtrip_frozen(cls, store):
    op, p = staged(store)
    value = p.document if cls is ExtractedDocument else p.document.blocks[0] if cls is DocumentBlock else p.chunks[0]
    assert cls.from_dict(value.to_dict()) == value
    with pytest.raises(FrozenInstanceError):
        value.schema_version = 99
    with pytest.raises(KnowledgeError):
        cls.from_dict(dict(value.to_dict(), artifactPath='../outside'))


def test_block_metadata_deeply_frozen_descriptive_only(store):
    op,p=staged(store)
    incoming={'description':'synthetic metadata'}
    block=replace(p.document.blocks[0],metadata=incoming)
    incoming['description']='changed'
    assert block.metadata['description']=='synthetic metadata'
    with pytest.raises(TypeError):block.metadata['path']='../outside'
    with pytest.raises(KnowledgeError):replace(block,metadata={'action':lambda:None})


@pytest.mark.parametrize('partial,text', [(False,TEXT),(True,TEXT),(False,'')])
def test_publish_only_after_real_mandatory_projections_commit(store, partial, text):
    operation = begin(store)
    before = store.get_source(operation.source_id, ACCESS)
    assert before.lifecycle_state is SourceLifecycle.IMPORTING and before.current_revision_id is None
    digest, size = store.stage(operation.operation_id, ACCESS, [text.encode()], lambda: False)
    p = projection(operation, digest, size, text, partial=partial)
    result = store.publish(operation.operation_id, ACCESS, p, lambda: False)
    assert result.lifecycle_state is (SourceLifecycle.PARTIAL if partial else SourceLifecycle.READY)
    assert result.current_revision_id == p.revision.revision_id
    assert store.read_blob(p.revision.revision_id, ACCESS) == text.encode()
    assert store.get_revision(p.revision.revision_id, ACCESS) == p.revision
    assert store.operation(operation.operation_id, ACCESS).status is OperationStatus.COMPLETED
    assert store._connection.execute('SELECT count(*) FROM chunk_fts').fetchone()[0] == len(p.chunks)
    assert store.recover(ACCESS).published == (p.revision.revision_id,)


@pytest.mark.parametrize('field', ['chunks','digest','revision','document_revision','status','ordinals','partial_warnings'])
def test_missing_or_incompatible_prepared_projections_never_ready(store, field):
    op, p = staged(store)
    with pytest.raises(KnowledgeError):
        if field == 'chunks':
            replace(p, chunks=())
        elif field == 'digest':
            replace(p, revision=replace(p.revision, extracted_digest='0'*64))
        elif field == 'revision':
            q = replace(p, revision=replace(p.revision, source_id=new_revision_id()))
            store.publish(op.operation_id, ACCESS, q, lambda: False)
        elif field == 'document_revision':
            replace(p, document=replace(p.document, revision_id=new_revision_id()))
        elif field == 'status':
            replace(p, revision=replace(p.revision, extraction_status=ExtractionStatus.CORRUPT))
        elif field == 'ordinals':
            replace(p, chunks=(replace(p.chunks[0], ordinal=1),))
        else:
            replace(p.document, extraction_completeness=ExtractionStatus.PARTIAL)
    assert store.get_source(op.source_id, ACCESS).current_revision_id is None
    assert store._connection.execute('SELECT count(*) FROM source_revisions').fetchone()[0] == 0


def test_refresh_new_revision_immutable_lineage_only_superseded_after_commit(store):
    old, p1, first = published(store)
    op, p2 = staged(store, old, payload=b'Synthetic amber replacement NOVA-K1-046.')
    assert store.get_source(old.source_id, ACCESS) == old
    assert store._connection.execute('SELECT state FROM revision_publication WHERE revision_id=?',
                                    (p1.revision.revision_id,)).fetchone()[0] == 'READY'
    current = store.publish(op.operation_id, ACCESS, p2, lambda: False)
    assert current.source_id == old.source_id and current.current_revision_id != old.current_revision_id
    assert p2.revision.previous_revision_id == p1.revision.revision_id
    assert store.get_revision(p1.revision.revision_id, ACCESS) == p1.revision
    assert store._connection.execute('SELECT state FROM revision_publication WHERE revision_id=?',
                                    (p1.revision.revision_id,)).fetchone()[0] == 'SUPERSEDED'
    with pytest.raises(sqlite3.IntegrityError):
        store._connection.execute("UPDATE source_revisions SET revision_json='{}'")
    with pytest.raises(KnowledgeError):
        store.begin(old, ACCESS, str(new_operation_id()), new_revision_id())


@pytest.mark.parametrize('scope', [KnowledgeScopeKind.SESSION, KnowledgeScopeKind.WORKSPACE])
@pytest.mark.parametrize('access', [OTHER_WORKSPACE, OTHER_SESSION])
@pytest.mark.parametrize('method', ['source','revision','blob','delete','refresh','operation','list'])
def test_scope_all_store_surfaces(store, scope, access, method):
    src, p, op = published(store, source(scope))
    allowed = scope is KnowledgeScopeKind.WORKSPACE and access.workspace_id == ACCESS.workspace_id
    call = {'source': lambda: store.get_source(src.source_id, access),
        'revision': lambda: store.get_revision(p.revision.revision_id, access),
        'blob': lambda: store.read_blob(p.revision.revision_id, access),
        'delete': lambda: store.delete(src.source_id, access),
        'refresh': lambda: begin(store, src, access),
        'operation': lambda: store.operation(op.operation_id, access),
        'list': lambda: store.list_sources(access)}[method]
    if method == 'operation':
        # Core correlation belongs to the initiating session even for WORKSPACE sources.
        allowed = False
    if method == 'list':
        assert len(call()) == int(allowed)
    elif allowed:
        call()
    else:
        with pytest.raises(KnowledgeError) as exc:
            call()
        assert exc.value.code == 'SOURCE_NOT_AUTHORIZED'


def test_two_sources_same_digest_distinct_identity_provenance_and_delete_independent(store):
    a, pa, _ = published(store)
    b, pb, _ = published(store)
    assert a.source_id != b.source_id and pa.revision.content_digest == pb.revision.content_digest
    store.delete(a.source_id, ACCESS)
    assert store.read_blob(pb.revision.revision_id, ACCESS) == PAYLOAD


def test_parallel_single_store_writes_serialized_no_mixed_revision(store):
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = tuple(executor.map(lambda n: published(store, payload=f'Synthetic {n}'.encode())[0], range(12)))
    assert len({s.source_id for s in results}) == 12
    assert len(store.list_sources(ACCESS)) == 12


@pytest.mark.parametrize('limit', ['source_bytes','session_bytes','workspace_bytes','workspace_sources',
                                 'workspace_chunks','source_chunks','extracted_characters'])
def test_operational_bounds_typed_no_purge_delete_still_available(tmp_path, limit):
    limits = replace(KnowledgeLimits(), **{limit: 1})
    with SQLiteKnowledgeStore(tmp_path / 'private', limits=limits) as store:
        scope = KnowledgeScopeKind.SESSION if limit == 'session_bytes' else KnowledgeScopeKind.WORKSPACE
        op = begin(store, source(scope))
        if limit in ('source_bytes','session_bytes','workspace_bytes'):
            with pytest.raises(KnowledgeError) as error:
                store.stage(op.operation_id, ACCESS, [PAYLOAD], lambda: False)
            assert error.value.code in ('SOURCE_TOO_LARGE','SOURCE_CAPACITY_EXCEEDED')
        else:
            digest, size = store.stage(op.operation_id, ACCESS, [b'a'], lambda: False)
            p = projection(op, digest, size, 'aa' if limit=='extracted_characters' else 'a')
            if limit in ('source_chunks','workspace_chunks'):
                p = replace(p, chunks=(p.chunks[0], replace(p.chunks[0], ordinal=1, chunk_id=new_revision_id())))
            if limit == 'workspace_sources':
                store.publish(op.operation_id, ACCESS, p, lambda: False)
                with pytest.raises(KnowledgeError) as error:
                    begin(store)
                assert error.value.code == 'SOURCE_CAPACITY_EXCEEDED'
            else:
                with pytest.raises(KnowledgeError) as error:
                    store.publish(op.operation_id, ACCESS, p, lambda: False)
                assert error.value.code in ('SOURCE_TOO_LARGE','SOURCE_CAPACITY_EXCEEDED')
        store.delete(op.source_id, ACCESS)
        assert store.list_sources(ACCESS) == ()


@pytest.mark.parametrize('payload', [[bytearray(b'bad')], [b'x'*(1024*1024+1)]])
def test_byte_units_bounded_no_coercion(store, payload):
    op = begin(store)
    with pytest.raises(KnowledgeError):
        store.stage(op.operation_id, ACCESS, payload, lambda: False)
    assert store.get_source(op.source_id, ACCESS).current_revision_id is None


def test_delete_projections_vectors_cache_bytes_and_tombstone_no_resurrection(store):
    src, p, op = published(store)
    c = store._connection
    c.execute('INSERT INTO semantic_spaces VALUES (?,?)', ('synthetic-space-fixture', '{}'))
    c.execute('INSERT INTO semantic_vectors VALUES (?,?,?)', (p.chunks[0].chunk_id,'synthetic-space-fixture',b'fixture-not-embedding'))
    key = p.revision.revision_id + '.' + '0'*64 + '.cache'
    with store.files.open('cache', key, write=True) as stream:
        stream.write(b'synthetic owned cache')
    store.delete(src.source_id, ACCESS)
    store.delete(src.source_id, ACCESS)  # Idempotent, scoped.
    for table in ('documents','document_blocks','chunks','chunk_fts','semantic_vectors'):
        assert c.execute(f'SELECT count(*) FROM {table}').fetchone()[0] == 0
    assert not store.files.path('blobs', p.revision.revision_id+'.bin').exists()
    assert not store.files.path('cache', key).exists()
    assert c.execute('SELECT count(*) FROM source_tombstones').fetchone()[0] == 1
    for callback in (lambda: store.read_blob(p.revision.revision_id,ACCESS), lambda: begin(store,src),
                     lambda: store.publish(op.operation_id,ACCESS,p,lambda:False)):
        with pytest.raises(KnowledgeError):
            callback()
    store.recover(ACCESS)
    assert store.list_sources(ACCESS) == ()


def test_native_foreign_keys_and_tombstone_trigger_prevent_bypass(store):
    src,p,_ = published(store)
    store.delete(src.source_id, ACCESS)
    with pytest.raises(sqlite3.IntegrityError):
        store._connection.execute('INSERT INTO source_revisions VALUES (?,?,?,?,?)',
            (new_revision_id(),src.source_id,json.dumps(p.revision.to_dict()),'unused.bin',1))


def test_original_origin_not_content_authority(store, tmp_path):
    outside = tmp_path / 'origin-secret-synthetic.txt'
    outside.write_text('Not acquired and must not be used', encoding='utf-8')
    src = replace(source(), origin=str(outside))
    src,p,_ = published(store,src)
    outside.write_text('Changed external path',encoding='utf-8')
    assert store.read_blob(p.revision.revision_id,ACCESS) == PAYLOAD


def test_close_session_and_restart_preserve_only_workspace_sources(tmp_path):
    state = tmp_path / 'private'
    with SQLiteKnowledgeStore(state) as store:
        ws,pw,_ = published(store)
        transient,pt,_ = published(store,source(KnowledgeScopeKind.SESSION))
        store.close_session(ACCESS)
    with SQLiteKnowledgeStore(state) as store:
        report = store.recover(OTHER_SESSION)
        assert report.published == (pw.revision.revision_id,)
        assert store.get_source(ws.source_id,OTHER_SESSION) == ws
        assert len(store.list_sources(OTHER_SESSION)) == 1
        assert not store.files.path('blobs',pt.revision.revision_id+'.bin').exists()
