"""No inference/scoring tuning: explain preserved E2E NONE on frozen queries."""
import argparse
import json
from pathlib import Path
from local_cli.core.knowledge_retrieval import terms,lexical_text,LEXICAL_FLOOR
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from tests.knowledge_inputs_v1.k8_fixtures import load
from tests.knowledge_inputs_v1.test_k8_quality import publish
from tests.knowledge_inputs_v1.k1_helpers import ACCESS


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    root=Path(__file__).resolve().parents[2];out=args.output.resolve()
    if out.exists() or out==root or root in out.parents:p.error('Fresh external output required')
    out.mkdir(parents=True);data=load();extraction={r['id']:r for r in data['extraction']};results=[]
    for case in data['e2e']:
        if case['id'] not in ('memory-plus-knowledge','document-injection','source-conflict'):continue
        with SQLiteKnowledgeStore(out/case['id']) as store:
            texts=[]
            if case['scenario']=='conflict':
                for i,text in enumerate([case['textA'],case['textB']]):
                    _,prepared,code=publish(store,{'id':'forensic-'+str(i),'text':text,'filename':'fixture.txt','format':'txt','scope':'WORKSPACE'})
                    assert prepared is not None and code is None;texts.append(prepared.document.text)
            else:
                row=dict(extraction[case['sourceKey']]);row['text']=case.get('replacementText',row['text'])
                _,prepared,code=publish(store,row);assert prepared is not None and code is None;texts.append(prepared.document.text)
            query_terms=terms(case['query']);coverage=[]
            for text in texts:
                content=set(lexical_text(text).split());matched=[t for t in query_terms if t in content]
                coverage.append(dict(matched=matched,queryTerms=list(query_terms),coverage=len(matched)/len(query_terms),
                    floor=LEXICAL_FLOOR,strictlyAboveFloor=len(matched)/len(query_terms)>LEXICAL_FLOOR))
            candidates=store.lexical_candidates(case['query'],ACCESS)
            results.append(dict(id=case['id'],candidateCount=len(candidates),coverage=coverage,
                classification='RETRIEVAL_LIMITATION' if not candidates else 'ADMISSION_REQUIRES_FURTHER_DIAGNOSIS',
                inferenceCalls=0,weightsFloorCapsChanged=False))
    (out/'report.json').write_text(json.dumps(dict(rows=results,realSQLiteFTS=True,modelCalls=0,reranked=False),indent=2),encoding='utf-8')
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
