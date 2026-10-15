"""M5 real local model gate. No model download/load/unload/cloud or private data.

Requires an already resident embedding-capable model selected by the host.
Missing/cold capability exits 2 / NOT_EVALUATED, not a product failure or fake quality PASS.
Compare exact/FTS, semantic and hybrid on a fixed bilingual synthetic dataset.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import platform
import statistics
from time import perf_counter,monotonic

from local_cli.application.memory_recall import MemoryRetriever,admit_capsule
from local_cli.application.memory_semantic import SemanticAdmission
from local_cli.application.context import WorkingMessages
from local_cli.application.secrets import SecretRedactor
from local_cli.core.memory import MemoryError,MemoryAccessScope
from local_cli.infrastructure.memory_embeddings import LocalOllamaEmbeddings
from local_cli.infrastructure.memory_semantic import NumpySemanticIndex
from local_cli.memory_config import memory_factory
from tests.memory_v1.m1_fixtures import AT,record
from tests.memory_v1.test_m4_context import manager,invariants,WINDOWS


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True); p.add_argument('--model',default='')
    p.add_argument('--endpoint',default='http://127.0.0.1:11434')
    args=p.parse_args(); out=args.output.resolve()
    if out.exists(): p.error('Output must be new')
    out.mkdir(parents=True)
    # Metadata only even if no selected model; never warms a capability.
    adapter=LocalOllamaEmbeddings(args.endpoint,args.model or 'unselected-capability-probe')
    result=dict(phase='M5',component='M5_SEMANTIC_QUALITY',status='NOT_EVALUATED',
        platform=platform.platform(),syntheticOnly=True,
        realModelQuality='UNKNOWN',embeddingDimension='UNKNOWN',coldEmbeddingLatency='UNKNOWN_NO_LOAD_AUTHORIZED',
        ramVram='UNKNOWN',chatCoexistence='UNKNOWN',model=args.model or None,autoDownload=False,cloud=False)
    try:
        tags=adapter._request('/api/tags',monotonic()+.6)
        resident=adapter._request('/api/ps',monotonic()+.6)
        result['installedModels']=[dict(name=r.get('name'),capabilities=r.get('capabilities')) for r in tags.get('models',[])]
        result['residentModels']=[dict(name=r.get('name'),size=r.get('size'),sizeVram=r.get('size_vram'))
            for r in resident.get('models',[])]
        if not args.model:
            result['blocker']='No host-selected installed embedding model; semantic quality gate NOT DEMONSTRATED'
        else:
            space=adapter.status(); result['space']=asdict(space); result['space']['created_at']=space.created_at.isoformat()
            result['embeddingDimension']=space.dimension
            corpus=json.loads((Path(__file__).parent/'fixtures/m5_paraphrases.json').read_text(encoding='utf-8'))
            work=out/'synthetic-workspace';work.mkdir()
            service=memory_factory(out/'synthetic-state')(work,SecretRedactor(source={}))
            try:
                for value in corpus['records']:
                    service.store.insert(record(value['id'],subject_id=service.subject,canonical_text=value['text']))
                scope=MemoryAccessScope(service.subject,service.identity.resolve_workspace(str(work)))
                semantic=SemanticAdmission(adapter,lambda s:NumpySemanticIndex(service.store,s))
                t=perf_counter(); maintenance=semantic.maintain(service.store,scope,at=AT,redactor=service.redactor)
                result['projectionMs']=(perf_counter()-t)*1000;result['maintenance']=maintenance
                rows=[];lex_hits=hybrid_hits=0
                for item in corpus['queries']:
                    service.semantic=None
                    lex=MemoryRetriever(service).retrieve(item['text'],workspace=work,at=AT)
                    service.semantic=semantic
                    hybrid=MemoryRetriever(service).retrieve(item['text'],workspace=work,at=AT)
                    lex_hit=item['expected'] in [r.memory_id for r in lex.records[:3]]
                    hybrid_hit=item['expected'] in [r.memory_id for r in hybrid.records[:3]]
                    lex_hits+=lex_hit;hybrid_hits+=hybrid_hit
                    context=[]
                    for n in WINDOWS:
                        cm=manager(n,current_message=item['text'])
                        working=WorkingMessages([dict(role='system',content='Mandatory Core/SECURITY.'),
                            dict(role='user',content=item['text'])])
                        selected=admit_capsule(working,cm,[],hybrid)
                        b=invariants(cm.prepare(working),n,item['text'])
                        context.append(dict(window=n,tokens=b.memory_tokens,budget=b.memory_token_budget,
                            selected=len(selected.records),currentUserPreserved=True))
                    rows.append(dict(expected=item['expected'],language=item['language'],lexicalHit3=lex_hit,
                        hybridHit3=hybrid_hit,lexicalIds=[r.memory_id for r in lex.records],
                        hybridIds=[r.memory_id for r in hybrid.records],
                        lexicalHit1=bool(lex.records and lex.records[0].memory_id==item['expected']),
                        hybridHit1=bool(hybrid.records and hybrid.records[0].memory_id==item['expected']),
                        metadata=hybrid.metadata(),context=context))
                # Normative gate allows honest degraded queries. Requiring ALL
                # queries warm would contradict M5's required fallback contract.
                good=hybrid_hits>lex_hits and all(r['metadata']['retrievalLatencyMs']<=600 and
                    (r['metadata']['embeddingStatus']=='WARM' or
                     r['metadata']['errorCode'] in ('MEMORY_RETRIEVAL_TIMEOUT','MEMORY_EMBEDDING_UNAVAILABLE',
                        'MEMORY_EMBEDDING_SPACE_MISMATCH')) for r in rows)
                result.update(status='PASS' if good else 'FAIL',realModelQuality='MEASURED',rows=rows,
                    lexicalRecall3=lex_hits/len(rows),hybridRecall3=hybrid_hits/len(rows),
                    lexicalRecall1=sum(r['lexicalHit1'] for r in rows)/len(rows),
                    hybridRecall1=sum(r['hybridHit1'] for r in rows)/len(rows),
                    lexicalPrecision3=lex_hits/max(1,sum(min(3,len(r['lexicalIds'])) for r in rows)),
                    hybridPrecision3=hybrid_hits/max(1,sum(min(3,len(r['hybridIds'])) for r in rows)),
                    gate='observed improvement + operational deadline + context contracts; M8 thresholds unresolved')
            finally: service.store.close()
    except MemoryError as exc:
        result.update(errorCode=exc.code,blocker='Required capability unavailable/cold/incompatible; quality NOT DEMONSTRATED')
    (out/'model.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
    raise SystemExit(0 if result['status']=='PASS' else 1 if result['status']=='FAIL' else 2)


if __name__=='__main__': main()
