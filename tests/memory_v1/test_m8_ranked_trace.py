"""Synthetic observation contracts, not real semantic/LLM quality evidence."""
from copy import deepcopy

import pytest

from local_cli.application.memory_recall import MemoryRetriever, hybrid_fusion
from local_cli.application.memory_semantic import SemanticAdmission
from local_cli.infrastructure.memory_semantic import NumpySemanticIndex
from tests.memory_v1.m1_fixtures import AT
from tests.memory_v1.m5_fixtures import SyntheticEmbeddings, space
from tests.memory_v1.m8_quality_isolation import wait_quiescent
from tests.memory_v1.m8_ranked_trace import RankedRecallTrace
from tests.memory_v1.test_m5_application import service, add


def test_actual_cosine_bm25_rrf_observed_without_changing_rankings(tmp_path):
    svc, work = service(tmp_path)
    one = add(svc, 'one', 'Synthetic cobalt notebook.')
    two = add(svc, 'two', 'Synthetic cobalt paper notebook.')
    # Real SQLite/NumPy, deterministic port fixture (no model quality claim).
    embeddings = SyntheticEmbeddings()
    embeddings._request = lambda *_: None
    index = NumpySemanticIndex(svc.store, space())
    index.upsert(one.memory_id, (1., 0., 0.), space().embedding_space_id)
    index.upsert(two.memory_id, (.8, .6, 0.), space().embedding_space_id)
    index.rebuild(space().embedding_space_id)
    svc.semantic = SemanticAdmission(embeddings, lambda _: index)
    svc.semantic.index = index
    original_np, original_search = index.np, index.search
    try:
        before = MemoryRetriever(svc).retrieve('cobalt', workspace=work, at=AT)
        wait_quiescent(svc.semantic, [], limit_seconds=1)
        with RankedRecallTrace(svc) as trace:
            snap, row = trace.recall('synthetic-case', 'cobalt', work, AT)
            row['teardown'] = wait_quiescent(svc.semantic, trace.threads, limit_seconds=1)
            actual = trace.annotate(row, mapping={'gold-synthetic': 'one', 'other': 'two'}, gold='gold-synthetic')
            assert snap.records == before.records and snap.capsule == before.capsule
            ranks = actual['rankings']
            assert ranks['semantic'][0]['id'] == 'gold-synthetic'
            assert ranks['semantic'][0]['cosine'] == pytest.approx(1)
            assert ranks['semantic'][1]['cosine'] == pytest.approx(.8)
            assert all(r['bm25'] < 0 for r in ranks['lexical'])
            lex, sem = row['_fusion_inputs']
            assert row['_fusion_rows'] == hybrid_fusion(lex, sem)
            expected = sum(1/(60+r.rank) for ranking in (lex, sem) for r in ranking if r.memory_id == 'one')
            assert next(r['rrfTotal'] for r in ranks['fusion'] if r['memoryId'] == 'one') == expected
            assert actual['goldRanks'] == dict(semantic=1, lexical=1, fusion=1, semanticEligiblePreFloor=1)
            assert actual['snapshotUnchangedAfterQuiescence'] and not actual['lateResultUsed']
            assert actual['goldAnnotation']['usedForRanking'] is False
            assert '_query_vector' not in actual and '_cosines' not in actual
        assert index.np is original_np and index.search == original_search
        assert (svc.semantic.soft_ms, svc.semantic.hard_ms, svc.semantic.fallback_reserve_ms) == (350, 600, 50)
    finally:
        svc.store.close()


def test_gold_absent_is_not_fabricated_or_used_to_rescore(tmp_path):
    svc, work = service(tmp_path)
    item = add(svc, 'one', 'Synthetic amber folder.')
    embeddings = SyntheticEmbeddings()
    embeddings._request = lambda *_: None
    index = NumpySemanticIndex(svc.store, space())
    index.upsert(item.memory_id, (1., 0., 0.), space().embedding_space_id)
    index.rebuild(space().embedding_space_id)
    svc.semantic = SemanticAdmission(embeddings, lambda _: index)
    svc.semantic.index = index
    try:
        with RankedRecallTrace(svc) as trace:
            snap, row = trace.recall('unlabeled', 'amber', work, AT)
            row['teardown'] = wait_quiescent(svc.semantic, trace.threads, limit_seconds=1)
            saved = deepcopy((snap.metadata(), snap.records, snap.capsule))
            observation = trace.annotate(row, gold='missing-synthetic')
            assert set(observation['goldRanks'].values()) == {None}
            assert (snap.metadata(), snap.records, snap.capsule) == saved
            assert observation['queryEmbedding']['hash'] is None  # No real /api/embed in this fixture.
            assert observation['queryEmbedding']['admitted']  # Port contract WARM, not real quality.
    finally:
        svc.store.close()


@pytest.mark.parametrize('post_mismatch', [False, True])
def test_real_adapter_response_hash_does_not_imply_post_validation_admission(tmp_path, post_mismatch):
    from tests.memory_v1.test_m8_metadata_admission import backend
    svc, work = service(tmp_path)
    item = add(svc, 'one', 'Synthetic turquoise ink.')
    adapter, calls, state, base = backend()
    actual_space = adapter.status()
    index = NumpySemanticIndex(svc.store, actual_space)
    index.upsert(item.memory_id, (1.,0.,0.), actual_space.embedding_space_id)
    index.rebuild(actual_space.embedding_space_id)
    svc.semantic = SemanticAdmission(adapter, lambda _: index)
    svc.semantic.index = index
    def transport(path, data, timeout):
        response = base(path, data, timeout)
        if path == '/api/embed' and post_mismatch:
            state['digest'] = 'synthetic-revision-changed'
        return response
    adapter._transport = transport
    try:
        with RankedRecallTrace(svc) as trace:
            snap, row = trace.recall('synthetic-validation', 'turquoise', work, AT)
            row['teardown'] = wait_quiescent(svc.semantic, trace.threads, limit_seconds=1)
            output = trace.annotate(row)
            assert output['queryEmbedding']['dimension'] == 3
            assert len(output['queryEmbedding']['hash']) == 64
            assert output['queryEmbedding']['responseObserved']
            assert output['queryEmbedding']['admitted'] is (not post_mismatch)
            if post_mismatch:
                assert snap.error_code == 'MEMORY_EMBEDDING_SPACE_MISMATCH'
                assert snap.retrieval_mode == 'lexical' and output['rankings']['semantic'] == []
                assert all(r['rrfTotal'] is None for r in output['rankings']['fusion'])
            else:
                assert output['rankings']['semantic'][0]['cosine'] == pytest.approx(1)
    finally:
        svc.store.close()


def test_distinct_actual_response_vectors_get_distinct_observational_hashes(tmp_path):
    from tests.memory_v1.test_m8_metadata_admission import backend
    svc, work = service(tmp_path)
    item = add(svc, 'one', 'Synthetic emerald pencil.')
    adapter, calls, state, base = backend()
    actual_space = adapter.status()
    index = NumpySemanticIndex(svc.store, actual_space)
    index.upsert(item.memory_id, (1.,0.,0.), actual_space.embedding_space_id)
    index.rebuild(actual_space.embedding_space_id)
    svc.semantic = SemanticAdmission(adapter, lambda _: index)
    svc.semantic.index = index
    queries = []
    def transport(path, data, timeout):
        response = base(path, data, timeout)
        if path == '/api/embed':
            queries.append(data['input'][0])
            response['embeddings'] = [[1.,0.,0.] if len(queries)==1 else [.8,.6,0.]]
        return response
    adapter._transport = transport
    try:
        with RankedRecallTrace(svc) as trace:
            hashes = []
            for text in ('emerald', 'synthetic writing utensil'):
                snap, row = trace.recall(text, text, work, AT)
                row['teardown'] = wait_quiescent(svc.semantic, trace.threads, limit_seconds=1)
                output = trace.annotate(row)
                hashes.append(output['queryEmbedding']['hash'])
                assert snap.embedding_status == 'WARM'
            assert len(set(hashes)) == 2 and queries == ['emerald', 'synthetic writing utensil']
    finally:
        svc.store.close()
