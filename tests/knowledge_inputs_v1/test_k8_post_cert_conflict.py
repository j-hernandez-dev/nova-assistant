"""Independent frozen retrieval/admission quality + separate historical regression.

No original exam runner or LLM calls. Real SQLite/K3/K4/K5/Core composition.
"""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import socket
from time import perf_counter
from types import SimpleNamespace

from local_cli.application.context import WorkingMessages
from local_cli.application.knowledge import KnowledgeService
from local_cli.application.knowledge_context import KnowledgeAdmission
from local_cli.application.knowledge_retrieval import DocumentRetriever
from local_cli.application.secrets import SecretRedactor
from local_cli.core.context import ContextManager, ContextSelection
from local_cli.core.knowledge_retrieval import LEXICAL_FLOOR, LEXICAL_CAP, SEMANTIC_CAP, MERGED_CAP, FINAL_CAP, RRF_K
from local_cli.infrastructure.knowledge_query import plan_query
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from tests.knowledge_inputs_v1.k1_helpers import ACCESS, execution
from tests.knowledge_inputs_v1.k4_helpers import load_corpus

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent/'fixtures'
PREFIX = 'k8_post_cert_conflict_'


def read(suffix):
    return json.loads((FIXTURES/(PREFIX+suffix+'.json')).read_text(encoding='utf-8'))


def verify_freeze():
    for pin in read('freeze_v1')['files']:
        assert hashlib.sha256((ROOT/pin['path']).read_bytes()).hexdigest() == pin['sha256'], pin['path']


def structure():
    data, protocol = read('corpus_v1'), read('protocol_v1')
    ids = {s['id'] for s in data['sources']}
    assert len(ids) == len(data['sources'])
    cases = data['cases']
    assert len({c['id'] for c in cases}) == len(cases)
    assert all(set(c['requiredSources']) <= set(c['gold']) == set(c['allowedSources']) <= ids for c in cases)
    assert all(set(c.get('refs', ())) <= ids for c in cases)
    counts = dict(total=len(cases), positive=sum(bool(c['gold']) for c in cases),
        negative=sum(not c['gold'] for c in cases), multiPositive=sum(bool(c['gold']) and c['multi'] for c in cases),
        critical=sum(c['critical'] for c in cases))
    assert counts == protocol['denominators']
    # Structural independence only: never calls scoring/retrieval to select cases.
    for path in FIXTURES.glob('k8*.json'):
        if path.name.startswith(PREFIX): continue
        old = json.loads(path.read_text(encoding='utf-8'))
        for item in old.get('realCases', []):
            assert item['id'] not in {c['id'] for c in cases}
            assert item.get('query') not in {c['query'] for c in cases if c['query']}
        assert not any(s['text'] in path.read_text(encoding='utf-8') for s in data['sources'])
    assert (LEXICAL_FLOOR, LEXICAL_CAP, SEMANTIC_CAP, MERGED_CAP, FINAL_CAP, RRF_K) == (.5, 32, 32, 24, 10, 60)
    return data, protocol


def test_frozen_prospective_structure():
    verify_freeze()
    structure()


class ObservedService(KnowledgeService):
    def retrieve(self, *args, **kwargs):
        self.last_result = super().retrieve(*args, **kwargs)
        return self.last_result


def measure(tmp_path):
    verify_freeze()
    data, protocol = structure()
    # Existing productive source helpers publish real revisions and projections.
    rows = []
    with SQLiteKnowledgeStore(tmp_path/'state') as store:
        ids, revisions, prior = load_corpus(store, data)
        inverse = {v:k for k,v in ids.items()}
        service = ObservedService(store, workspace=tmp_path, access=ACCESS)
        service.retriever = DocumentRetriever(store)
        try:
            for case in data['cases']:
                query = case['query']
                refs = tuple(SimpleNamespace(source_id=ids[k], revision_id=(prior[k] if case.get('previousRevision') == k else revisions[k])) for k in case.get('refs', ()))
                admission = KnowledgeAdmission('turn_'+case['id'].replace('-', '_'), service, SecretRedactor(source={}))
                start = perf_counter()
                admission.retrieve(query, context=execution(tmp_path), refs=refs, local_destination=True)
                elapsed = (perf_counter()-start)*1000
                result = service.last_result
                working = WorkingMessages([dict(role='system', content='Synthetic mandatory Core.'), dict(role='user', content=query)])
                manager = ContextManager(ContextSelection(4096), current_message=query)
                admission.stage(working, manager, ())
                capsule = admission.freeze(working, manager, ())
                prepared = manager.prepare(working, ())
                actual = [inverse[c.source_id] for c in result.candidates]
                admitted = list(dict.fromkeys(inverse[e.target.source_id] for e in capsule.evidence))
                mapping = all(c.revision_id == revisions[inverse[c.source_id]] for c in result.candidates)
                targets = {(c.source_id, c.revision_id, c.chunk.chunk_id) for c in admission.candidates}
                mapping = mapping and all((e.target.source_id, e.target.revision_id, e.target.chunk_id) in targets for e in capsule.evidence)
                original = dict(role='user', content=query) in prepared.messages
                allowed = set(case['allowedSources'])
                false_expansion = bool((set(actual) | set(admitted)) - allowed)
                row = dict(id=case['id'], gold=case['gold'], requiredSources=case['requiredSources'],
                    multi=case['multi'], critical=case['critical'], ranking=actual, admitted=admitted,
                    recall=set(case['gold']) <= set(actual[:5]) if case['gold'] else None,
                    precision=bool(actual and actual[0] in case['gold']) if case['gold'] else None,
                    requiredAdmitted=set(case['requiredSources']) <= set(admitted),
                    abstained=not actual and not capsule.evidence, falseExpansion=false_expansion,
                    scopeCurrentDelete=mapping and not false_expansion, originalInputPreserved=original,
                    plan=asdict(plan_query(query)), mode=result.mode, semanticState=result.semantic_state,
                    retrievalCount=admission.retrieval_count, elapsedMs=elapsed,
                    budget=prepared.budget.to_dict(), tokens=capsule.token_cost,
                    provenance=[dict(sourceId=e.target.source_id, sourceKey=inverse[e.target.source_id],
                        revisionId=e.target.revision_id, chunkId=e.target.chunk_id, citationId=e.citation_id,
                        locator=e.target.locator.to_dict(), text=e.text, truncated=e.truncated) for e in capsule.evidence])
                rows.append(row)
        finally:
            service.retriever.close()
    pos = [r for r in rows if r['gold']]
    neg = [r for r in rows if not r['gold']]
    multi = [r for r in pos if r['multi']]
    metric = lambda selected, field: dict(passed=sum(r[field] for r in selected), total=len(selected), value=sum(r[field] for r in selected)/len(selected))
    metrics = dict(recallAt5=metric(pos, 'recall'), precisionAt1=metric(pos, 'precision'),
        multiSourceRequiredAdmissions=metric(multi, 'requiredAdmitted'), abstention=metric(neg, 'abstained'),
        scopeCurrentDelete=metric(rows, 'scopeCurrentDelete'),
        falseSourceExpansion=dict(count=sum(r['falseExpansion'] for r in rows if r['critical']), total=sum(r['critical'] for r in rows)))
    gates = {k:(metrics[k]['count'] == threshold if k == 'falseSourceExpansion' else metrics[k]['value'] >= threshold) for k,threshold in protocol['gates'].items()}
    result = dict(dataset=data['id'], metrics=metrics, gates=gates,
        requiredSourcesMicro=dict(passed=sum(len(set(r['requiredSources']) & set(r['admitted'])) for r in multi), total=sum(len(r['requiredSources']) for r in multi)),
        inputPreserved=all(r['originalInputPreserved'] for r in rows),
        singleRetrieval=all(r['retrievalCount'] == 1 for r in rows),
        p95Ms=sorted(r['elapsedMs'] for r in rows)[int(.95*(len(rows)-1))], rows=rows)
    (tmp_path/'postcert-quality.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


def test_frozen_prospective_quality(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('No network/model inference in post-certification quality')
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    result = measure(tmp_path)
    assert result['inputPreserved'] and result['singleRetrieval']
    assert all(result['gates'].values()), result['metrics']


def test_historical_source_conflict_regression_only(tmp_path):
    # Exact observed historical data. Never imports/runs the original E2E scorer.
    from tests.knowledge_inputs_v1.test_k5_integration import case, run, finish
    from tests.knowledge_inputs_v1.k2_helpers import invoke, refs
    query = 'What do the two sources say about SABLE_ROUTE? Report both conflicting values; do not choose one as truth.'
    c = case(tmp_path, steps=('Scripted regression response [K1] [K2]',), context_selection=8192)
    try:
        c.file.write_text('Synthetic SABLE_ROUTE conflict route is NORTH.', encoding='utf-8')
        invoke(c)
        second = c.file.with_name('conflict-second.txt')
        second.write_text('Synthetic SABLE_ROUTE conflict route is SOUTH.', encoding='utf-8')
        invoke(c, args={'path':str(second)})
        attachment_refs = refs(c)
        turn = run(c, query, attached=attachment_refs)
        admission = turn.knowledge_admission
        capsule = admission.capsule
        observed = dict(purpose='Historical regression only, original source-conflict remains FAIL / RETRIEVAL_FAILURE',
            mode=admission.mode, retrievalCount=admission.retrieval_count, query=query,
            expectedSources=[r['sourceId'] for r in attachment_refs],
            admittedSources=[s.source_id for s in capsule.source_registry],
            texts=[e.text for e in capsule.evidence], userUnchanged=any(m.get('role') == 'user' and m.get('content') == query for m in c.p.captured[0]))
        (tmp_path/'historical-regression.json').write_text(json.dumps(observed, indent=2), encoding='utf-8')
        assert set(observed['expectedSources']) == set(observed['admittedSources']) and len(observed['admittedSources']) == 2
        assert all(any(value in e.text for e in capsule.evidence) for value in ('NORTH', 'SOUTH'))
        assert observed['userUnchanged'] and admission.retrieval_count == 1
    finally:
        finish(c)
