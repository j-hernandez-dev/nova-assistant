"""Frozen V2 corpus; real extraction, chunking and FTS, not LLM quality."""
import json
from local_cli.application.knowledge_retrieval import DocumentRetriever
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from tests.knowledge_inputs_v1.k1_helpers import ACCESS
from tests.knowledge_inputs_v1.k4_helpers import load_corpus
from tests.knowledge_inputs_v1.k8_repair2_helpers import read, verify, FIXTURES


def measure(tmp_path):
    verify(FIXTURES/'k8_repair2_freeze_v1.json')
    dataset=read('k8_repair2_corpus_v1.json');rows=[]
    with SQLiteKnowledgeStore(tmp_path/'store') as store:
        ids,_,_=load_corpus(store,dataset);inverse={v:k for k,v in ids.items()}
        retriever=DocumentRetriever(store)
        try:
            for case in dataset['retrieval']:
                result=retriever.retrieve(case['query'],ACCESS)
                ranking=list(dict.fromkeys(inverse[c.source_id] for c in result.candidates))
                row=dict(id=case['id'],subset=case['subset'],gold=case['gold'],ranking=ranking,
                    recall=bool(set(case['gold'])&set(ranking[:5])) if case['gold'] else None,
                    precision=bool(ranking and ranking[0] in case['gold']) if case['gold'] else None,
                    abstained=not ranking,locators=[c.chunk.locator_start.to_dict() for c in result.candidates])
                if case.get('pointer'):
                    row['objectMapping']=bool(result.candidates and
                        result.candidates[0].chunk.locator_start.coordinates.get('pointer')==case['pointer'])
                rows.append(row)
        finally:retriever.close()
    positives=[r for r in rows if r['gold']];negatives=[r for r in rows if not r['gold']]
    result=dict(dataset=dataset['id'],positive=len(positives),negative=len(negatives),
        recallAt5=sum(r['recall'] for r in positives)/len(positives),
        precisionAt1=sum(r['precision'] for r in positives)/len(positives),
        abstention=sum(r['abstained'] for r in negatives)/len(negatives),
        critical=all(r['abstained'] for r in negatives if r['subset']=='critical'),
        objectMapping=all(r.get('objectMapping',True) for r in rows),rows=rows)
    (tmp_path/'retrieval-v2.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


def test_v2_frozen_quality_and_critical(tmp_path):
    r=measure(tmp_path);p=read('k8_repair2_protocol_v1.json')['metrics']
    assert r['recallAt5']>=p['recallAt5']
    assert r['precisionAt1']>=p['precisionAt1']
    assert r['abstention']>=p['abstention']
    assert r['critical'] and r['objectMapping']
