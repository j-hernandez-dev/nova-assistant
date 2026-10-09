"""Real SQLite/FTS tests; synthetic sources, no model or cloud."""
from dataclasses import replace
import json
from pathlib import Path
import pytest
from local_cli.application.knowledge_retrieval import DocumentRetriever, fuse
from local_cli.core.knowledge import (KnowledgeError, KnowledgeScopeKind,
    SourceKind, SourceLifecycle, new_source_id)
from local_cli.core.knowledge_retrieval import (DocumentRetrievalFilter,
    DocumentRetrievalPort, terms)
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from tests.knowledge_inputs_v1.k1_helpers import (ACCESS, OTHER_SESSION, OTHER_WORKSPACE,
    source, execution)
from tests.knowledge_inputs_v1.k4_helpers import publish_text


def test_exact_fts_native_and_literal_query_not_fts_program(tmp_path):
    with SQLiteKnowledgeStore(tmp_path/'state') as store:
        assert isinstance(store,DocumentRetrievalPort)
        src,p=publish_text(store,'Synthetic copper capsule code KI4-045.')
        r=DocumentRetriever(store)
        try:
            result=r.retrieve('KI4-045',ACCESS)
            assert result.mode=='lexical' and result.semantic_state=='DISABLED'
            c=result.candidates[0]
            assert c.exact and c.source_id==src.source_id and c.revision_id==p.revision.revision_id
            assert c.chunk.locator_start==p.document.blocks[0].locator
            assert not r.retrieve('NEAR("xylophone" "zirconium")',ACCESS).candidates
            assert not r.retrieve('" OR * --',ACCESS).candidates
        finally:r.close()


@pytest.mark.parametrize('scope',[KnowledgeScopeKind.WORKSPACE,KnowledgeScopeKind.SESSION])
def test_scope_filters_precede_candidate_cap_and_scoring(tmp_path,scope):
    with SQLiteKnowledgeStore(tmp_path/'state') as store:
        # Foreign high-relevance results must not consume the current cap.
        for n in range(35): publish_text(store,'unique tungsten receipt',src=source(access=OTHER_WORKSPACE),access=OTHER_WORKSPACE)
        src,p=publish_text(store,'unique tungsten receipt',src=source(scope))
        candidates=store.lexical_candidates('tungsten receipt',ACCESS,DocumentRetrievalFilter(scope=scope))
        assert len(candidates)==1 and candidates[0].source_id==src.source_id
        if scope is KnowledgeScopeKind.SESSION:
            assert store.lexical_candidates('tungsten receipt',OTHER_SESSION,DocumentRetrievalFilter())==()
        else:
            assert len(store.lexical_candidates('tungsten receipt',OTHER_SESSION,DocumentRetrievalFilter()))==1


def test_source_revision_media_kind_state_filters_and_stale_exclusion(tmp_path):
    with SQLiteKnowledgeStore(tmp_path/'state') as store:
        src,p=publish_text(store,'prism turquoise signal')
        current,q=publish_text(store,'prism crimson signal',src=src)
        assert store.lexical_candidates('turquoise signal',ACCESS,DocumentRetrievalFilter(revision_ids=(p.revision.revision_id,)))==()
        assert store.lexical_candidates('crimson signal',ACCESS,DocumentRetrievalFilter(source_ids=(new_source_id(),)))==()
        assert store.lexical_candidates('crimson signal',ACCESS,DocumentRetrievalFilter(media_types=('application/pdf',)))==()
        assert store.lexical_candidates('crimson signal',ACCESS,DocumentRetrievalFilter(kinds=(SourceKind.URL_SNAPSHOT,)))==()
        for state in (SourceLifecycle.DELETED,SourceLifecycle.FAILED,SourceLifecycle.SUPERSEDED):
            assert store.lexical_candidates('crimson signal',ACCESS,DocumentRetrievalFilter(states=(state,)))==()
        result=store.lexical_candidates('crimson signal',ACCESS,DocumentRetrievalFilter(revision_ids=(q.revision.revision_id,)))
        assert len(result)==1 and result[0].revision_id==current.current_revision_id


def test_delete_and_refresh_between_scoring_and_validation_remove_result(tmp_path):
    with SQLiteKnowledgeStore(tmp_path/'state') as store:
        src,p=publish_text(store,'synthetic azure certificate')
        old=store.lexical_candidates('azure certificate',ACCESS,DocumentRetrievalFilter())
        src,q=publish_text(store,'synthetic amber certificate',src=src)
        assert store.validate_candidates(old,ACCESS,DocumentRetrievalFilter())==()
        new=store.lexical_candidates('amber certificate',ACCESS,DocumentRetrievalFilter())
        store.delete(src.source_id,ACCESS)
        assert store.validate_candidates(new,ACCESS,DocumentRetrievalFilter())==()
        assert store.lexical_candidates('certificate',ACCESS,DocumentRetrievalFilter())==()
        assert store._connection.execute('SELECT count(*) FROM chunk_fts').fetchone()[0]==0


def test_same_text_keeps_distinct_provenance_dedup_is_not_cross_source(tmp_path):
    with SQLiteKnowledgeStore(tmp_path/'state') as store:
        a,p=publish_text(store,'same synthetic heliotrope badge')
        b,q=publish_text(store,'same synthetic heliotrope badge')
        r=DocumentRetriever(store)
        try:
            first=r.retrieve('heliotrope badge',ACCESS)
            assert {c.source_id for c in first.candidates}=={a.source_id,b.source_id}
            assert r.retrieve('heliotrope badge',ACCESS)==first
            merged=fuse(first.candidates,first.candidates)
            assert len(merged)==2
        finally:r.close()


def test_exact_phrase_admitted_before_candidate_cap_not_demoted_by_short_partials(tmp_path):
    with SQLiteKnowledgeStore(tmp_path/'state') as store:
        for n in range(35):publish_text(store,'zirconium other separator emerald')
        exact,p=publish_text(store,'zirconium emerald '+('synthetic filler '*150))
        candidates=store.lexical_candidates('zirconium emerald',ACCESS,DocumentRetrievalFilter())
        assert len(candidates)<=32 and candidates[0].source_id==exact.source_id and candidates[0].exact


def test_caps_floor_no_zero_score_fill_and_no_context_or_memory_side_effect(tmp_path):
    with SQLiteKnowledgeStore(tmp_path/'state') as store:
        for n in range(40):publish_text(store,'shared synthetic badge '+str(n))
        raw=store.lexical_candidates('shared badge',ACCESS,DocumentRetrievalFilter())
        assert len(raw)==32 and all(c.score>0 for c in raw)
        r=DocumentRetriever(store)
        try:
            result=r.retrieve('shared badge',ACCESS)
            assert len(result.candidates)==10
            assert len(fuse(raw,raw))<=24
            for query in ('','the and of','el la de','absent xenolith','badge absent'):
                assert r.retrieve(query,ACCESS).mode=='NONE'
        finally:r.close()


def test_chunk_row_tampering_not_returned_as_valid_evidence(tmp_path):
    with SQLiteKnowledgeStore(tmp_path/'state') as store:
        src,p=publish_text(store,'original cobalt serial')
        store._connection.execute('DROP TRIGGER immutable_chunk')
        c=p.chunks[0].to_dict();c['locatorStart']['coordinates']['lineStart']=88;c['locatorStart']['coordinates']['lineEnd']=88
        store._connection.execute('UPDATE chunks SET chunk_json=?',(json.dumps(c),))
        with pytest.raises(KnowledgeError):store.lexical_candidates('cobalt serial',ACCESS,DocumentRetrievalFilter())


def test_application_context_scope_and_events_only_ids_no_content(tmp_path):
    from local_cli.bootstrap_knowledge import knowledge_factory
    work=tmp_path/'workspace';work.mkdir()
    path=work/'fact.txt';path.write_text('synthetic ruby certificate',encoding='utf-8')
    events=[];factory=knowledge_factory(tmp_path/'state')
    svc=factory(work,ACCESS.session_id,lambda k,v:events.append((k,v)))
    try:
        ctx=execution(work)
        outcome=svc.import_file(context=ctx,selected_path=str(path),acquisition=svc.acquisition,scope_kind=KnowledgeScopeKind.WORKSPACE)
        assert outcome.source is not None and factory.retrieval_available
        result=svc.retrieve('ruby certificate',context=ctx)
        assert result.candidates and 'ruby' not in str(events[-1])
        assert set(events[-1][1])=={'operationId','sourceIds','revisionIds','count','mode','semanticState','code','elapsedMs'}
        assert events[-1][1]['elapsedMs']>=0
        for invalid in (replace(ctx,agent_id='synthetic-child'),replace(ctx,workspace=tmp_path)):
            with pytest.raises(KnowledgeError) as exc:svc.retrieve('ruby',context=invalid)
            assert exc.value.code=='SOURCE_NOT_AUTHORIZED'
        from datetime import datetime,timezone,timedelta
        with pytest.raises(KnowledgeError) as exc:svc.retrieve('ruby',context=replace(ctx,deadline=datetime.now(timezone.utc)-timedelta(seconds=1)))
        assert exc.value.code=='IMPORT_CANCELLED'
    finally:svc.close()
