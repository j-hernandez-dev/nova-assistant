"""Read-only product diagnosis on NEW synthetic stores, no rank adjustments."""
import argparse
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import struct

from local_cli.application.memory_recall import MemoryRetriever,hybrid_fusion
from local_cli.core.memory import MemoryAccessScope,MemoryQuery
from local_cli.infrastructure.memory_semantic import vector_checked
from tests.memory_v1.m8_evaluation import load_dataset
from tests.memory_v1.run_m8_quality import create,seed,projection,close
from tests.memory_v1.run_m8_candidate import CANDIDATE,capability,residency,frozen_protocol

CASES=('paraphrase-dark','paraphrase-metric','paraphrase-diet',
    'paraphrase-offline','paraphrase-morning')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    out=p.parse_args().output.resolve()
    if out.exists():p.error('NEW output required; prior evidence is immutable')
    out.mkdir(parents=True);work=out/'workspace';work.mkdir()
    data,digest=load_dataset()
    report={'kind':'DIAGNOSIS_BEFORE_PRODUCT_CHANGE','datasetSha256':digest,
        'frozenProtocolHashes':frozen_protocol(),'capability':capability(),'rows':[]}
    app,sid,actor,audit=create(out,work,4096,data['chatModel'])
    try:
        mapping=seed(app,sid,actor,data);inverse={v:k for k,v in mapping.items()}
        report['projection']=projection(app,work,CANDIDATE)
        sem=app._memory.semantic;adapter,index=sem.embeddings,sem.index
        report['matrixNorms']=[float(v) for v in index.np.linalg.norm(index._matrix,axis=1)]
        report['cacheStampBefore']=index._signature
        request=adapter._request;search=index.search;captured={};requests=[];vectors=[]
        def observed_request(path,deadline,data=None):
            if path=='/api/embed':requests.append(data)
            return request(path,deadline,data)
        def observed_search(vector,query,space_id):
            normalized=vector_checked(vector,index.space.dimension);vectors.append(normalized)
            positions=index._eligible_positions(query)
            scores=index.np.einsum('ij,j->i',index._matrix[positions],
                index.np.asarray(normalized,dtype=index.np.float32),optimize=False)
            order=index.np.lexsort((index._fields['memory_id'][positions],-scores))
            captured['cosines']=[{'id':inverse[str(index._fields['memory_id'][positions[i]])],
                'cosine':float(scores[i])} for i in order]
            captured['rawQueryNorm']=sum(v*v for v in vector)**.5
            captured['normalizedQueryNorm']=sum(v*v for v in normalized)**.5
            captured['queryVectorSha256']=hashlib.sha256(struct.pack('<'+'d'*len(normalized),*normalized)).hexdigest()
            rows=search(vector,query,space_id);captured['semantic']=rows
            return rows
        adapter._request=observed_request;index.search=observed_search
        for case in data['queries']:
            if case['id'] not in CASES:continue
            at=datetime.now(timezone.utc);retriever=MemoryRetriever(app._memory)
            text=retriever.composer.compose(case['question'])
            query=MemoryQuery(text=text,scope=MemoryAccessScope(app._memory.subject,
                app._memory.identity.resolve_workspace(str(work))),at=at,limit=24,match_any=True)
            lexical=app._memory.lexical.search(query);before=len(requests)
            snapshot=retriever.retrieve(case['question'],workspace=work,at=at)
            semantic=captured.get('semantic',());combined=hybrid_fusion(lexical,semantic)
            ids=lambda rows:[inverse[r.memory_id] for r in rows]
            # Annotation uses gold only AFTER the actual unmodified ranking.
            report['rows'].append({'case':case['id'],'queryText':text,
                'embedRequests':requests[before:],'lexicalRanking':ids(lexical),
                'semanticRanking':ids(semantic),'semanticCosinesAllEligible':captured.get('cosines'),
                'finalFusionRanking':ids(combined),'finalHydratedRanking':[inverse[r.memory_id] for r in snapshot.records],
                'queryVectorSha256':captured.get('queryVectorSha256'),
                'rawQueryNorm':captured.get('rawQueryNorm'),'normalizedQueryNorm':captured.get('normalizedQueryNorm'),
                'metadata':snapshot.metadata(),'goldAnnotation':case['gold']})
        report['queryPairCosines']=[[sum(a*b for a,b in zip(x,y)) for y in vectors] for x in vectors]
        report['distinctQueries']=len({r['queryText'] for r in report['rows']})
        report['distinctEmbeddingHashes']=len({r['queryVectorSha256'] for r in report['rows']})
        report['embedRequestCount']=len(requests)
        report['cacheStampAfter']=index._signature
        report['minimumSimilarity']=index.minimum_similarity
        report['after']=residency();report['frozenProtocolUnchanged']=report['frozenProtocolHashes']==frozen_protocol()
    except Exception as exc:report['errorCode']=getattr(exc,'code',type(exc).__name__)
    finally:close(app,audit)
    (out/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    print(json.dumps({'error':report.get('errorCode'),'distinctVectors':report.get('distinctEmbeddingHashes'),
        'ranks':[{'case':r['case'],'semantic':r['semanticRanking'],'final':r['finalHydratedRanking']} for r in report['rows']]}))
    raise SystemExit(1 if report.get('errorCode') else 0)


if __name__=='__main__':main()
