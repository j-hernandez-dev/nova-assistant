"""Frozen V3 standalone actual SQLite/parser/FTS, not model quality."""
import json
from time import perf_counter
from local_cli.application.knowledge_retrieval import DocumentRetriever
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from tests.knowledge_inputs_v1.k4_helpers import load_corpus
from tests.knowledge_inputs_v1.k1_helpers import ACCESS
from tests.knowledge_inputs_v1.k8_repair3_helpers import read,verify,FIXTURES


def measure(tmp_path):
    verify(FIXTURES/'k8_repair3_freeze_v1.json')
    data=read('k8_repair3_corpus_v1.json');rows=[];latencies=[]
    with SQLiteKnowledgeStore(tmp_path/'store') as store:
        ids,revisions,prior=load_corpus(store,data);inverse={v:k for k,v in ids.items()}
        retriever=DocumentRetriever(store)
        try:
            for case in data['retrieval']:
                start=perf_counter();result=retriever.retrieve(case['query'],ACCESS)
                latencies.append((perf_counter()-start)*1000)
                ranking=list(dict.fromkeys(inverse[c.source_id] for c in result.candidates))
                row=dict(id=case['id'],subset=case['subset'],gold=case['gold'],ranking=ranking,
                    recall=bool(set(case['gold'])&set(ranking[:5])) if case['gold'] else None,
                    precision=bool(ranking and ranking[0] in case['gold']) if case['gold'] else None,
                    abstained=not ranking,locators=[c.chunk.locator_start.to_dict() for c in result.candidates],
                    currentMapping=all(c.revision_id==revisions[inverse[c.source_id]] for c in result.candidates))
                if case.get('pointer'):
                    row['objectMapping']=bool(result.candidates and result.candidates[0].chunk.locator_start.coordinates.get('pointer')==case['pointer'])
                rows.append(row)
        finally:retriever.close()
    positives=[r for r in rows if r['gold']];negatives=[r for r in rows if not r['gold']]
    result=dict(dataset=data['id'],positive=len(positives),negative=len(negatives),
        recallAt5=sum(r['recall'] for r in positives)/len(positives),
        precisionAt1=sum(r['precision'] for r in positives)/len(positives),
        abstention=sum(r['abstained'] for r in negatives)/len(negatives),
        critical=all(r['abstained'] for r in negatives if r['subset']=='critical'),
        mapping=all(r.get('objectMapping',True) and r['currentMapping'] for r in rows),
        p95Ms=sorted(latencies)[int(.95*(len(latencies)-1))],rows=rows)
    (tmp_path/'retrieval-v3.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


def test_v3_frozen_standalone(tmp_path):
    r=measure(tmp_path);p=read('k8_repair3_protocol_v1.json')['metrics']
    assert (r['positive'],r['negative'])==(48,40)
    assert r['recallAt5']>=p['recallAt5'] and r['precisionAt1']>=p['precisionAt1']
    assert r['abstention']>=p['abstention'] and r['critical'] and r['mapping']
    assert r['p95Ms']<=100
