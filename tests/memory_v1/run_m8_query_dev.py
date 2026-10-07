"""Single DEV contract experiment. No product modifications or quality tuning."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

from local_cli.core.memory import MemoryAccessScope,MemoryError,MemoryErrorCode
from local_cli.infrastructure.memory_embeddings import LocalOllamaEmbeddings
from tests.memory_v1.run_m8_candidate import CANDIDATE,capability,residency
from tests.memory_v1.run_m8_quality import create,seed,close

DATASET=Path(__file__).parent/'fixtures/m8_query_dev_v1.json'
INSTRUCTION='Given a user request, retrieve the most relevant durable user or workspace memory needed to answer it.'


class Prototype(LocalOllamaEmbeddings):
    def embed_query(self,text):
        if not isinstance(text,str) or not text.strip() or len(text)>4096:
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)
        return self._embed(['Instruct: '+INSTRUCTION+'\nQuery: '+text])[0]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    out=p.parse_args().output.resolve()
    if out.exists():p.error('NEW output required')
    out.mkdir(parents=True);work=out/'workspace';work.mkdir()
    raw=DATASET.read_bytes();data=json.loads(raw)
    assert data['instruction']==INSTRUCTION
    report={'datasetVersion':data['datasetVersion'],'datasetSha256':hashlib.sha256(raw).hexdigest(),
        'instruction':INSTRUCTION,'instructionTuned':False,'qualityMeasured':False,
        'prototypeOnly':True,'productModified':False,'capability':capability(),'queries':[]}
    app,sid,actor,audit=create(out,work,4096,data['chatModel'])
    try:
        mapping=seed(app,sid,actor,data);service=app._memory
        scope=MemoryAccessScope(service.subject,service.identity.resolve_workspace(str(work)))
        records=service.store.list(scope,limit=32).records
        adapter=Prototype('http://127.0.0.1:11434',CANDIDATE)
        request=adapter._request;calls=[]
        def observed(path,deadline,data=None):
            if path=='/api/embed':calls.append(data)
            return request(path,deadline,data)
        adapter._request=observed
        document_vectors=adapter.embed_records(tuple(records))
        report['documentEmbedPayload']=calls[-1]
        assert calls[-1]['input']==[r.canonical_text for r in records]
        for query in data['queries']:
            vector=adapter.embed_query(query)
            assert calls[-1]['input']==['Instruct: '+INSTRUCTION+'\nQuery: '+query]
            report['queries'].append({'input':calls[-1]['input'][0],
                'dimension':len(vector),'rawNorm':sum(v*v for v in vector)**.5})
        report['documentDimensions']=[len(v) for v in document_vectors]
        report['documentTextUnchanged']=True;report['singleGenericInstruction']=True
        report['queryRequestCount']=len(calls)-1;report['after']=residency();report['status']='PASS_CONTRACT_ONLY'
    except Exception as exc:report['errorCode']=getattr(exc,'code',type(exc).__name__);report['status']='FAIL'
    finally:close(app,audit)
    (out/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':report['status'],'error':report.get('errorCode'),'queryCount':report.get('queryRequestCount')}))
    raise SystemExit(0 if report['status']=='PASS_CONTRACT_ONLY' else 1)


if __name__=='__main__':main()
