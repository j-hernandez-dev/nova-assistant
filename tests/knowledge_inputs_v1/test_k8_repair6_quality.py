"""Prospective V6 native SQLite/FTS + annotated plan. No model inference."""
import hashlib
import json
from pathlib import Path
import re
import socket
from time import perf_counter

from local_cli.application.knowledge_retrieval import DocumentRetriever
from local_cli.core.knowledge_retrieval import terms, LEXICAL_FLOOR, LEXICAL_CAP, RRF_K
from local_cli.infrastructure.knowledge_lexical import documentary_terms
from local_cli.infrastructure.knowledge_query import plan_query
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from tests.knowledge_inputs_v1.k4_helpers import load_corpus,case_filters
from tests.knowledge_inputs_v1.k1_helpers import ACCESS

ROOT=Path(__file__).resolve().parents[2]
FIXTURES=Path(__file__).parent/'fixtures'


def read(name): return json.loads((FIXTURES/name).read_text(encoding='utf-8'))


HISTORICAL_PRODUCT_IDENTITY = 'POST_K8_REPAIR_V6'
CURRENT_PRODUCT_IDENTITY = 'POST_CERT_MULTI_SOURCE'
HISTORICAL_VERIFIER_SOURCE_SHA256 = 'e8032aee9b02b271688add7b640f404c46efcf08c81f0c0185349f5028d2fb12'


def verify_historical_v6_freeze():
    # Append-only implementation re-freeze after demonstrated regression.
    # Corpus, gold, metrics and scoring below are unchanged.
    freeze=read('k8_repair6_freeze_v2.json')
    assert hashlib.sha256((FIXTURES/'k8_repair6_freeze_v2.json').read_bytes()).hexdigest() == 'cdbe771621f93c1c98b5268a7e2c1f232f399977c8eca45ba0f6eb15467b71b1'
    assert hashlib.sha256((ROOT/'docs/knowledge_inputs_v1/k8_repair6_manifest.json').read_bytes()).hexdigest() == 'facc970921ec1cc5f21ebd3c52f5a4487a4d7870089e31ac6e3443b160a2217a'
    expected = {
        'local_cli/infrastructure/knowledge_query.py': '6590bab13e77718d9aa9c3de75779fc5683a502fec83c623f0709dffb302df2c',
        'local_cli/infrastructure/knowledge_retrieval_sqlite.py': 'f8b499ed545c6ed1e12d3f5ca9dc47b3b7b3b7103bd65c6b4d1c55a655b25412',
    }
    pins = {pin['path']: pin['sha256'] for pin in freeze['files']}
    for path, sha in expected.items():
        assert pins[path] == sha
    assert HISTORICAL_PRODUCT_IDENTITY == 'POST_K8_REPAIR_V6'
    assert HISTORICAL_VERIFIER_SOURCE_SHA256 == 'e8032aee9b02b271688add7b640f404c46efcf08c81f0c0185349f5028d2fb12'
    assert freeze['noInference'] and not freeze['originalK8Executed']


# Keep the original historical verifier available under its original name for
# forensic callers.  Product identity is intentionally not repinned here.
verify_freeze = verify_historical_v6_freeze


def verify_current_post_cert_identity():
    """Verify the separately captured current post-cert product identity.

    This is deliberately a different route from the V6 verifier.  The proof
    is external to the checkout because the dirty working tree is shared with
    the certification evidence; it is read-only and must contain all 241 pins.
    """
    proof = Path('C:/Users/joseh/AppData/Local/Temp/nova-k8-post-cert-supplemental-8k-citation-proof-20261008-a/citation-identity-proof.json')
    assert proof.exists(), 'CURRENT_POST_CERT_IDENTITY_PROOF_MISSING'
    evidence = json.loads(proof.read_text(encoding='utf-8'))
    assert evidence['currentProductIdentity'].startswith(CURRENT_PRODUCT_IDENTITY)
    pins = evidence['productPins']
    assert len(pins) == 241
    for pin in pins:
        actual = hashlib.sha256((ROOT / pin['path']).read_bytes()).hexdigest()
        assert actual == pin['sha256'], pin['path']
    authorized = {row['path']: row['currentSha256'] for row in evidence['exactAuthorizedDeltaFromV6']}
    assert set(authorized) == {
        'local_cli/infrastructure/knowledge_query.py',
        'local_cli/infrastructure/knowledge_retrieval_sqlite.py',
    }
    v6 = read('k8_repair6_freeze_v2.json')['files']
    v6 = {row['path']: row['sha256'] for row in v6}
    assert {path for path, sha in zip(authorized, authorized.values()) if sha != v6[path]} == set(authorized)
    current_paths = {pin['path'] for pin in pins}
    assert len(current_paths) == len(pins) == 241
    return evidence


def test_prospective_structure_and_frozen_artifacts():
    verify_current_post_cert_identity()
    data=read('k8_repair6_corpus_v1.json');protocol=read('k8_repair6_protocol_v1.json')
    sources={s['id'] for s in data['sources']}
    assert len(sources)==len(data['sources'])
    assert len(data['retrieval'])==len({c['id'] for c in data['retrieval']})==protocol['denominators']['total']
    assert sum(bool(c['gold']) for c in data['retrieval'])==protocol['denominators']['positive']
    assert sum(not c['gold'] for c in data['retrieval'])==protocol['denominators']['negative']
    assert all(set(c['gold'])<=sources for c in data['retrieval'])
    assert len({c['query'] for c in data['retrieval']})==len(data['retrieval'])
    # Corpus construction/IDs do not reuse any historical quality cases.
    for path in FIXTURES.glob('k8*corpus*.json'):
        if path.name=='k8_repair6_corpus_v1.json':continue
        old=json.loads(path.read_text(encoding='utf-8'))
        previous=old.get('retrieval',[])+old.get('realCases',[])
        assert not {c['id'] for c in previous}&{c['id'] for c in data['retrieval']}
        assert not {c.get('query') for c in previous}&{c['query'] for c in data['retrieval']}
    assert (LEXICAL_FLOOR,LEXICAL_CAP,RRF_K)==(.5,32,60)


def test_current_post_cert_identity_is_separate_from_historical_v6():
    evidence = verify_current_post_cert_identity()
    assert evidence['v6Guards']['originalAssertionAndFreezeUnchanged'] is True
    assert evidence['v6Guards']['integrationPendingHumanDecision'] is True
    assert evidence['currentProductIdentity'].startswith(CURRENT_PRODUCT_IDENTITY)


def test_historical_v6_evidence_is_intact_without_applying_v6_to_current_product():
    verify_historical_v6_freeze()


def measure(tmp_path):
    verify_current_post_cert_identity();data=read('k8_repair6_corpus_v1.json');rows=[]
    with SQLiteKnowledgeStore(tmp_path/'state') as store:
        ids,revisions,prior=load_corpus(store,data);inverse={v:k for k,v in ids.items()}
        retriever=DocumentRetriever(store)
        try:
            for case in data['retrieval']:
                query=case['query'];plan=plan_query(query);signal=documentary_terms(query)
                expected=terms(case['factual'])
                controls=all(any(fragment in query[s.start:s.end] for s in getattr(plan,category))
                    for category,fragments in case['controls'].items() for fragment in fragments)
                expected_keys=tuple(t for t in expected if any(c.isalpha() for c in t) and any(c.isdigit() for c in t))
                key_signal=set(terms(' '.join(query[s.start:s.end] for s in plan.identifiers)))
                identifiers=set(expected_keys)<=key_signal and all(any(f.start<=s.start<s.end<=f.end
                    for f in plan.factual_spans) for s in plan.identifiers)
                spans=sorted((*plan.factual_spans,*plan.controls),key=lambda s:s.start)
                offsets=all(0<=s.start<s.end<=len(query) for s in spans) and all(a.end<=b.start for a,b in zip(spans,spans[1:]))
                start=perf_counter()
                result=retriever.retrieve(query,ACCESS,case_filters(case,ids,revisions,prior))
                elapsed=(perf_counter()-start)*1000
                ranking=list(dict.fromkeys(inverse[c.source_id] for c in result.candidates))
                gold=case['gold']
                row=dict(id=case['id'],subset=case['subset'],language=case['language'],gold=gold,
                    ranking=ranking,signal=signal,expectedSignal=expected,
                    plan={k:[dict(start=s.start,end=s.end,kind=s.kind,text=query[s.start:s.end]) for s in getattr(plan,k)]
                        for k in ('factual_spans','identifiers','source_constraints','output_controls','effect_controls')},
                    factualPreserved=signal==expected,controlsSeparated=controls,identifiersPreserved=identifiers,
                    offsetsValid=offsets,falseStripping=not set(case.get('mustKeep',()))<=set(signal),
                    recall=set(gold)<=set(ranking[:5]) if gold else None,
                    precision=bool(ranking and ranking[0] in gold) if gold else None,
                    abstained=not ranking,elapsedMs=elapsed,mode=result.mode,semanticState=result.semantic_state,
                    currentMapping=all(c.revision_id==revisions[inverse[c.source_id]] for c in result.candidates),
                    locators=[c.chunk.locator_start.to_dict() for c in result.candidates])
                if case.get('pointer'):
                    row['locatorPreserved']=bool(result.candidates and
                        result.candidates[0].chunk.locator_start.coordinates.get('pointer')==case['pointer'])
                rows.append(row)
        finally:retriever.close()
    positive=[r for r in rows if r['gold']];negative=[r for r in rows if not r['gold']]
    result=dict(dataset=data['id'],positive=len(positive),negative=len(negative),total=len(rows),
        recallAt5=sum(r['recall'] for r in positive)/len(positive),
        precisionAt1=sum(r['precision'] for r in positive)/len(positive),
        abstention=sum(r['abstained'] for r in negative)/len(negative),
        critical=all(r['abstained'] for r in negative if r['subset'].startswith('critical-')),
        mapping=all(r['currentMapping'] and r.get('locatorPreserved',True) for r in rows),
        identifiers=sum(r['identifiersPreserved'] for r in rows)/len(rows),
        factualPreservation=sum(r['factualPreserved'] for r in rows)/len(rows),
        controlSeparation=sum(r['controlsSeparated'] and r['offsetsValid'] for r in rows)/len(rows),
        falseStripping=sum(r['falseStripping'] for r in rows),
        p95Ms=sorted(r['elapsedMs'] for r in rows)[int(.95*(len(rows)-1))],rows=rows)
    (tmp_path/'retrieval-v6.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


def test_frozen_v6_quality(tmp_path,monkeypatch):
    def forbidden(*a,**k):raise AssertionError('V6 forbids network/model inference')
    monkeypatch.setattr(socket,'create_connection',forbidden)
    result=measure(tmp_path);p=read('k8_repair6_protocol_v1.json')
    assert (result['positive'],result['negative'],result['total'])==tuple(p['denominators'][k] for k in ('positive','negative','total'))
    for key,value in p['metrics'].items():
        if key=='falseStripping':assert result[key]==value
        else:assert result[key]>=value,(key,result[key])
    assert result['mapping'] and all(r['semanticState']=='DISABLED' for r in result['rows'])
