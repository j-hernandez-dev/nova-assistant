"""Prospectively frozen Core quality/performance. No embeddings or gold tuning."""
import hashlib
import json
import math
from pathlib import Path
from time import perf_counter
from local_cli.application.knowledge_retrieval import DocumentRetriever
from local_cli.core.knowledge_retrieval import DocumentRetrievalFilter
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from tests.knowledge_inputs_v1.k1_helpers import ACCESS
from tests.knowledge_inputs_v1.k4_helpers import load_corpus,case_filters,publish_text


FIXTURES=Path(__file__).parent/'fixtures'
DATA_SHA='72fabd4b1c43a33438ee3f67e29693e2c1299f93d19eb932ef6958eb4a8e2b65'
PROTOCOL_SHA='31045a14ae3a50a3cbd4d4990c9fb6966394597748437758b108ac7bc6aa0586'


def percentile(values,p):return sorted(values)[max(0,math.ceil(len(values)*p)-1)]


def test_frozen_quality_corpus_real_exact_fts_and_honest_abstention(tmp_path):
    data=(FIXTURES/'k4_core_frozen_v1.json').read_bytes();protocol=(FIXTURES/'k4_protocol_v1.json').read_bytes()
    assert hashlib.sha256(data).hexdigest()==DATA_SHA and hashlib.sha256(protocol).hexdigest()==PROTOCOL_SHA
    dataset=json.loads(data);criteria=json.loads(protocol)
    assert len({r['id'] for r in dataset['sources']})==len(dataset['sources'])
    assert len({r['id'] for r in dataset['cases']})==len(dataset['cases'])
    assert all(set(c['gold'])<={r['id'] for r in dataset['sources']} for c in dataset['cases'])
    with SQLiteKnowledgeStore(tmp_path/'state') as store:
        sources,revisions,prior=load_corpus(store,dataset)
        retriever=DocumentRetriever(store);rows=[]
        try:
            reverse={v:k for k,v in sources.items()}
            for case in dataset['cases']:
                filters=case_filters(case,sources,revisions,prior)
                started=perf_counter();result=retriever.retrieve(case['query'],ACCESS,filters)
                elapsed=(perf_counter()-started)*1000
                ranking=list(dict.fromkeys(reverse[c.source_id] for c in result.candidates))
                gold=set(case['gold'])
                recall=len(gold&set(ranking[:5]))/len(gold) if gold else None
                precision=bool(ranking and ranking[0] in gold) if gold else None
                # Check every returned candidate's immutable revision and real locator.
                for c in result.candidates:
                    assert c.revision_id==revisions[reverse[c.source_id]]
                    assert c.chunk.revision_id==c.revision_id and c.chunk.block_spans
                    assert c.chunk.locator_start.coordinates['lineStart']>=1
                rows.append(dict(id=case['id'],subset=case['subset'],gold=case['gold'],ranking=ranking,
                    recallAt5=recall,precisionAt1=precision,abstained=result.mode=='NONE',mode=result.mode,
                    elapsedMs=elapsed,sourceRevisionMap=[dict(sourceId=c.source_id,revisionId=c.revision_id,
                        chunkId=c.chunk.chunk_id,locatorStart=c.chunk.locator_start.to_dict(),locatorEnd=c.chunk.locator_end.to_dict()) for c in result.candidates]))
            positive=[r for r in rows if r['gold']];negative=[r for r in rows if not r['gold']]
            recall=sum(r['recallAt5'] for r in positive)/len(positive)
            precision=sum(r['precisionAt1'] for r in positive)/len(positive)
            abstention=sum(r['abstained'] for r in negative)/len(negative)
            subsets={s:dict(count=len(group),recallAt5=sum(r['recallAt5'] for r in group)/len(group),
                precisionAt1=sum(r['precisionAt1'] for r in group)/len(group)) for s in sorted({r['subset'] for r in positive})
                if (group:=[r for r in positive if r['subset']==s])}
            report=dict(datasetSha256=DATA_SHA,protocolSha256=PROTOCOL_SHA,positive=len(positive),negative=len(negative),
                recallAt5=recall,precisionAt1=precision,abstention=abstention,subsets=subsets,queries=rows,
                p95RecallMs=percentile([r['elapsedMs'] for r in rows],.95),semanticQuality='NOT_EVALUATED',documentSemanticProfile='NOT_CERTIFIED')
            (tmp_path/'quality.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            assert len(positive)==criteria['denominators']['positive'] and len(negative)==criteria['denominators']['negative']
            assert recall>=criteria['quality']['recallAt5'],report
            assert precision>=criteria['quality']['precisionAt1'],report
            assert abstention>=criteria['quality']['abstention'],report
            assert subsets['exact']['recallAt5']==1 and subsets['exact']['precisionAt1']==1
            critical=['negative-deleted','negative-wrong-workspace','negative-wrong-session','negative-corrupt','negative-old-revision']
            assert all(r['abstained'] for r in rows if r['id'] in critical)
        finally:retriever.close()


def test_fts_p95_on_published_thousand_chunk_synthetic_corpus(tmp_path):
    # Independent scale fixture, fixed generation before any timings. Real K3
    # JSON pointer blocks + K4 + FTS, no precomputed/fixture-only projections.
    content={f'item_{n:04d}':f'Synthetic scale zirconium label REG{n:04d} belongs to bin {n}.' for n in range(1000)}
    with SQLiteKnowledgeStore(tmp_path/'state') as store:
        src,prepared=publish_text(store,json.dumps(content),filename='scale.json')
        assert len(prepared.chunks)==1000
        queries=[f'REG{(n*17)%1000:04d}' for n in range(60)]
        timings=[]
        for query in queries:
            started=perf_counter();found=store.lexical_candidates(query,ACCESS,DocumentRetrievalFilter())
            timings.append((perf_counter()-started)*1000)
            assert found and query in found[0].chunk.text
        footprint={p.name:p.stat().st_size for p in store.files.root.glob('knowledge.db*')}
        report=dict(profile='1000-json-values-v1/60-distinct-exact-queries',sources=1,chunks=1000,
            queries=len(queries),p50Ms=percentile(timings,.5),p95Ms=percentile(timings,.95),maxMs=max(timings),
            timingsMs=timings,footprintBytes=footprint,thresholdP95Ms=100,externalInference=False)
        (tmp_path/'performance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        assert report['p95Ms']<=100,report
