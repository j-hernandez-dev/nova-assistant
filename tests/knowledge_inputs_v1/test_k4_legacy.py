"""Explicit original-source rebuild; legacy vectors/bytes never reinterpreted."""
import hashlib
import sqlite3
from pathlib import Path
import pytest
from local_cli.application.knowledge_legacy import rebuild_legacy_sources
from local_cli.bootstrap_knowledge import knowledge_factory
from local_cli.core.knowledge import KnowledgeScopeKind
from local_cli.core.knowledge_legacy import LegacySourceSelection
from local_cli.core.knowledge_chunking import CHUNK_PROFILE
from tests.knowledge_inputs_v1.k1_helpers import ACCESS, execution


def fixture(tmp_path):
    work=tmp_path/'workspace';work.mkdir()
    original=work/'original.txt';original.write_text('Synthetic violet navigation badge.',encoding='utf-8')
    legacy=tmp_path/'rag_index.db'
    with sqlite3.connect(legacy) as c:
        c.execute('CREATE TABLE chunks(id INTEGER PRIMARY KEY,file_path TEXT,chunk_index INTEGER,content TEXT,file_hash TEXT,embedding BLOB)')
        c.execute('INSERT INTO chunks VALUES (1,?,?,?,?,?)',('../untrusted-never-open.txt',0,'poisoned legacy content','old-hash',b'not-a-v1-vector'))
    svc=knowledge_factory(tmp_path/'state')(work,ACCESS.session_id,lambda k,v:None)
    return svc,execution(work),original,legacy


def test_explicit_legacy_source_rebuild_real_k2_k3_k4_fts_no_vector_migration(tmp_path):
    svc,ctx,original,legacy=fixture(tmp_path);before=legacy.read_bytes()
    try:
        selections=(LegacySourceSelection('synthetic-rag-entry-one',str(original)),)
        result=rebuild_legacy_sources(svc,selections,context=ctx,acquisition=svc.acquisition)
        assert result.status=='READY' and len(result.completed)==1
        retrieved=svc.retrieve('violet badge',context=ctx)
        assert retrieved.candidates and retrieved.candidates[0].source_id==result.completed[0]
        assert retrieved.candidates[0].chunk.chunking_profile==CHUNK_PROFILE
        assert not svc.retrieve('poisoned legacy content',context=ctx).candidates
        assert svc.store._connection.execute('SELECT count(*) FROM semantic_vectors').fetchone()[0]==0
        assert legacy.read_bytes()==before
        again=rebuild_legacy_sources(svc,selections,context=ctx,acquisition=svc.acquisition)
        assert again.completed==result.completed
        assert len(svc.store.list_sources(svc.access))==1
    finally:svc.close()


def test_missing_original_cannot_rebuild_from_legacy_chunk_text(tmp_path):
    svc,ctx,original,legacy=fixture(tmp_path);before=legacy.read_bytes()
    try:
        selected=LegacySourceSelection('synthetic-rag-entry-one',str(original.parent/'missing.txt'))
        result=rebuild_legacy_sources(svc,(selected,),context=ctx,acquisition=svc.acquisition)
        assert result.status=='LEGACY_REBUILD_REQUIRED' and result.completed==() and result.failed
        assert svc.retrieve('poisoned legacy content',context=ctx).mode=='NONE'
        assert legacy.read_bytes()==before
    finally:svc.close()


def test_delete_then_rebuild_same_legacy_key_cannot_resurrect_even_after_restart(tmp_path):
    svc,ctx,original,legacy=fixture(tmp_path);before=legacy.read_bytes()
    selected=(LegacySourceSelection('synthetic-rag-entry-one',str(original)),)
    result=rebuild_legacy_sources(svc,selected,context=ctx,acquisition=svc.acquisition)
    svc.delete(result.completed[0],context=ctx);svc.close()
    svc=knowledge_factory(tmp_path/'state')(ctx.workspace,ACCESS.session_id,lambda k,v:None)
    try:
        failed=rebuild_legacy_sources(svc,selected,context=ctx,acquisition=svc.acquisition)
        assert failed.completed==() and failed.failed[0][1]=='SOURCE_NOT_FOUND'
        assert svc.retrieve('violet badge',context=ctx).mode=='NONE'
        assert svc.store._connection.execute('SELECT count(*) FROM source_tombstones').fetchone()[0]==1
        assert legacy.read_bytes()==before
    finally:svc.close()


def test_corrupt_original_keeps_legacy_and_no_ready_projection(tmp_path):
    svc,ctx,original,legacy=fixture(tmp_path);before=legacy.read_bytes()
    fake=original.parent/'fake.pdf';fake.write_bytes(b'%PDF-1.7\nnot a PDF')
    try:
        result=rebuild_legacy_sources(svc,(LegacySourceSelection('synthetic-corrupt',str(fake)),),context=ctx,acquisition=svc.acquisition)
        assert result.status=='LEGACY_REBUILD_REQUIRED' and result.failed[0][1]=='CORRUPT_DOCUMENT'
        assert svc.store._connection.execute('SELECT count(*) FROM chunk_fts').fetchone()[0]==0
        assert legacy.read_bytes()==before
    finally:svc.close()


def test_promoted_k4_chunks_rebind_block_spans_and_never_reuse_vectors(tmp_path):
    svc,ctx,original,legacy=fixture(tmp_path)
    try:
        imported=svc.import_file(context=ctx,selected_path=str(original),acquisition=svc.acquisition)
        from dataclasses import replace
        from local_cli.core.contracts import new_operation_id
        promoted=svc.promote(imported.source.source_id,context=replace(ctx,operation_id=new_operation_id()))
        assert promoted.source.scope.kind is KnowledgeScopeKind.WORKSPACE
        first=svc.store.read_prepared(imported.source.current_revision_id,svc.access)
        second=svc.store.read_prepared(promoted.source.current_revision_id,svc.access)
        assert first.chunks[0].text==second.chunks[0].text
        assert first.chunks[0].block_spans!=second.chunks[0].block_spans
        assert second.chunks[0].block_spans[0].block_id==second.document.blocks[0].block_id
        assert not svc.store._connection.execute('SELECT 1 FROM semantic_vectors').fetchone()
    finally:svc.close()
