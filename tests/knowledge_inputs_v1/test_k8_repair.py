"""Prospective retrieval repair campaign, real SQLite/FTS, no model calls."""
import json
from collections import defaultdict
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from local_cli.application.knowledge_retrieval import DocumentRetriever
from local_cli.core.knowledge_context import CitationRegistry
from tests.knowledge_inputs_v1.k4_helpers import load_corpus
from tests.knowledge_inputs_v1.k1_helpers import ACCESS
from tests.knowledge_inputs_v1.k8_repair_helpers import corpus, protocol, verify_freeze, FIXTURES, score


def measure(directory):
    data = corpus(); rows = []
    with SQLiteKnowledgeStore(directory / 'store') as store:
        source_ids, _, _ = load_corpus(store, data)
        keys = {v: k for k, v in source_ids.items()}
        retriever = DocumentRetriever(store)
        try:
            for case in data['retrieval']:
                result = retriever.retrieve(case['query'], ACCESS)
                ranking = list(dict.fromkeys(keys[c.source_id] for c in result.candidates))
                gold = set(case['gold'])
                rows.append(dict(id=case['id'],subset=case['subset'],gold=case['gold'],ranking=ranking,
                    recall=len(gold & set(ranking[:5])) / len(gold) if gold else None,
                    precision=int(bool(ranking and ranking[0] in gold)) if gold else None,
                    abstained=not ranking,rankProfile=result.rank_profile))
        finally:
            retriever.close()
    positive = [r for r in rows if r['gold']]; negative = [r for r in rows if not r['gold']]
    subsets = defaultdict(list)
    for r in positive: subsets[r['subset']].append(r['recall'])
    return dict(dataset=data['id'],positive=len(positive),negative=len(negative),
        recallAt5=sum(r['recall'] for r in positive)/len(positive),
        precisionAt1=sum(r['precision'] for r in positive)/len(positive),
        abstention=sum(r['abstained'] for r in negative)/len(negative),
        criticalIsolation=all(r['abstained'] for r in negative if r['subset']=='critical-negative'),
        subsets={k:sum(v)/len(v) for k,v in subsets.items()},rows=rows)


def test_independent_frozen_retrieval_repair(tmp_path):
    verify_freeze(FIXTURES / 'k8_repair_freeze_v1.json')
    result=measure(tmp_path); p=protocol()['metrics']
    (tmp_path/'retrieval.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    assert result['recallAt5']>=p['recallAt5']
    assert result['precisionAt1']>=p['precisionAt1']
    assert result['abstention']>=p['abstention']
    assert result['criticalIsolation']


def test_repair_scorer_rejects_guess_wrong_citation_and_side_effect():
    case={'gold':['GROUNDABLE'],'group':'citation'}
    row=dict(turnStatus='completed',terminalCount=1,answer='GROUNDABLE [K1]',admittedSources=[{}],
        admittedText='GROUNDABLE',memoryText='',validCitations=[{}],invalidCitations=[],invalidAccepted=False,
        sideEffectAttempts=[],createdFiles=[],memoryCountUnchanged=True)
    assert score(case,row)['passed']
    for change in ({'admittedSources':[]},{'admittedText':''},{'validCitations':[]},
        {'sideEffectAttempts':['write']},{'createdFiles':['side.txt']},{'memoryCountUnchanged':False}):
        assert not score(case,{**row,**change})['passed']


def test_citation_alternatives_are_never_accepted():
    registry=CitationRegistry('turn_repair')
    assert not registry.validate('[Citation: K1] (K1) https://invented.invalid/K1',turn_id='turn_repair')['valid']
    assert registry.validate('[K999]',turn_id='turn_repair')['invalid']==['K999']
