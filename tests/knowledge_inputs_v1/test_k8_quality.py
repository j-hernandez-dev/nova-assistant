"""Frozen K8 Core corpus: real parsers/SQLite/FTS, no model/semantic calls."""
from dataclasses import replace
from datetime import datetime,timezone
import hashlib
import json
from uuid import NAMESPACE_URL,uuid5
from time import perf_counter

from local_cli.bootstrap_knowledge import build_knowledge_service
from local_cli.core.contracts import OperationStatus
from local_cli.core.knowledge import (KnowledgeScope,KnowledgeScopeKind,Source,SourceKind,SourceTrustClass,KnowledgeError)
from local_cli.core.knowledge_store import KnowledgeAccess
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from local_cli.infrastructure.knowledge_extraction import prepare_revision
from local_cli.application.knowledge_retrieval import DocumentRetriever
from tests.knowledge_inputs_v1.k8_fixtures import load,protocol,payload,FIXTURES
from tests.knowledge_inputs_v1.k4_helpers import publish_text
from tests.knowledge_inputs_v1.test_k4_quality import percentile
from tests.knowledge_inputs_v1.k1_helpers import begin,source,ACCESS


def publish(store,row,access=ACCESS):
    src=replace(source(KnowledgeScopeKind.SESSION if row.get('scope') in ('SESSION','OTHER_SESSION') else KnowledgeScopeKind.WORKSPACE,access),
        source_id=str(uuid5(NAMESPACE_URL,'nova-k8:'+row['id'])))
    raw=payload(row);op=begin(store,src=src,access=access)
    digest,size=store.stage(op.operation_id,access,[raw],lambda:False)
    try:
        prepared=prepare_revision(op,digest,size,raw,row['filename'])
        return store.publish(op.operation_id,access,prepared,lambda:False),prepared,None
    except KnowledgeError as exc:
        store.finish(op.operation_id,access,OperationStatus.FAILED,exc.code)
        return src,None,exc.code
    except Exception as exc:
        store.finish(op.operation_id,access,OperationStatus.FAILED,'EXTRACTION_FAILED')
        return src,None,type(exc).__name__


def check_pins():
    frozen=json.loads((FIXTURES/'k8_freeze_v1.json').read_text())
    root=FIXTURES.parents[2]
    for row in frozen['files']:
        assert hashlib.sha256((root/row['path']).read_bytes()).hexdigest()==row['sha256'],row['path']


def test_k8_frozen_extraction_parse_mapping_typing(tmp_path):
    check_pins();data=load();p=protocol();rows=[];critical=[]
    with SQLiteKnowledgeStore(tmp_path/'state') as store:
        for row in data['extraction']:
            src,prepared,code=publish(store,row)
            success=prepared is not None and prepared.revision.extraction_status.value==row['expectStatus']
            content=prepared.document.text if prepared else ''
            mapping=success and row['expectedNeedle'] in content
            if prepared:
                mapping &= prepared.revision.source_id==src.source_id and all(c.revision_id==src.current_revision_id for c in prepared.chunks)
                if row['format']=='pdf':
                    mapping &= [b.locator.coordinates['page'] for b in prepared.document.blocks]==row.get('expectedPages',[1])
                if row.get('expectedLastLine'):
                    mapping &= prepared.document.blocks[-1].locator.coordinates['lineStart']==row['expectedLastLine']
                if row.get('structure')=='script-style':success &= 'FORBIDDEN_SCRIPT_TEXT' not in content and 'FORBIDDEN_STYLE_TEXT' not in content
                if row.get('structure')=='heading':mapping &= prepared.document.blocks[0].kind=='heading'
            rows.append(dict(id=row['id'],format=row['format'],success=success,mapping=bool(mapping),error=code,
                sourceId=src.source_id,revisionId=src.current_revision_id,locators=[b.locator.to_dict() for b in prepared.document.blocks] if prepared else []))
        for row in data['critical']:
            src,prepared,code=publish(store,row)
            critical.append(dict(id=row['id'],expected=row['code'],actual=code,passed=code==row['code'] and prepared is None))
    report=dict(dataset=data['id'],parsed=sum(r['success'] for r in rows),total=len(rows),
        parseSuccess=sum(r['success'] for r in rows)/len(rows),mapping=sum(r['mapping'] for r in rows)/len(rows),
        criticalTyping=sum(r['passed'] for r in critical)/len(critical),rows=rows,critical=critical)
    (tmp_path/'extraction.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    assert report['parseSuccess']>=p['quality']['parseSuccess'],report
    assert report['mapping']==1 and report['criticalTyping']==1,report


def test_k8_frozen_exact_fts_scopes_updates_conflicts_abstention(tmp_path):
    check_pins();data=load();p=protocol();rows=[];source_ids={};revision_ids={}
    extraction={r['id']:r for r in data['extraction']}
    with SQLiteKnowledgeStore(tmp_path/'state') as store:
        for raw in data['retrieval']['sources']:
            row=extraction[raw['extractionId']] if raw.get('extractionId') else dict(raw,format='txt')
            access=KnowledgeAccess('foreign-workspace','foreign-session') if raw['scope']=='FOREIGN_WORKSPACE' else \
                KnowledgeAccess(ACCESS.workspace_id,'other-session') if raw['scope']=='OTHER_SESSION' else ACCESS
            if raw['state']=='FAILED':row=dict(raw,text='{invalid json',format='json')
            src,prepared,code=publish(store,row,access)
            source_ids[raw['id']]=src.source_id
            if prepared:revision_ids[raw['id']]=prepared.revision.revision_id
            if raw['state']=='SUPERSEDED':publish_text(store,'Synthetic refreshed source with no old marker.',src=src,access=access)
            if raw['state']=='DELETED':store.delete(src.source_id,access)
        reverse={v:k for k,v in source_ids.items()};retriever=DocumentRetriever(store)
        try:
            for case in data['retrieval']['cases']:
                started=perf_counter();result=retriever.retrieve(case['query'],ACCESS)
                ranking=list(dict.fromkeys(reverse[c.source_id] for c in result.candidates));gold=set(case['gold'])
                mapping=all(c.source_id==source_ids[reverse[c.source_id]] and c.chunk.revision_id==c.revision_id for c in result.candidates)
                rows.append(dict(id=case['id'],subset=case['subset'],ranking=ranking,gold=case['gold'],
                    recallAt5=len(gold&set(ranking[:5]))/len(gold) if gold else None,
                    precisionAt1=int(bool(ranking and ranking[0] in gold)) if gold else None,
                    abstained=not ranking,mapping=mapping,elapsedMs=(perf_counter()-started)*1000,
                    candidates=[dict(sourceId=c.source_id,revisionId=c.revision_id,chunkId=c.chunk.chunk_id,score=c.score,
                        locator=c.chunk.locator_start.to_dict()) for c in result.candidates]))
        finally:retriever.close()
    positives=[r for r in rows if r['gold']];negatives=[r for r in rows if not r['gold']]
    report=dict(dataset=data['id'],positive=len(positives),negative=len(negatives),
        recallAt5=sum(r['recallAt5'] for r in positives)/len(positives),precisionAt1=sum(r['precisionAt1'] for r in positives)/len(positives),
        abstention=sum(r['abstained'] for r in negatives)/len(negatives),mapping=all(r['mapping'] for r in rows),rows=rows)
    (tmp_path/'retrieval.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    assert report['positive']==p['denominators']['retrievalPositive'] and report['negative']==p['denominators']['retrievalNegative']
    assert report['recallAt5']>=p['quality']['recallAt5'] and report['precisionAt1']>=p['quality']['precisionAt1'],report
    assert report['abstention']>=p['quality']['abstention'] and report['mapping'],report
    assert all(r['abstained'] for r in negatives if r['subset']!='negative')


def test_k8_fts_performance_frozen_scale(tmp_path):
    check_pins();p=protocol();count=p['performance']['chunks']
    text={str(n):f'Synthetic performance entry PERFKEY{n:04d} has batch {n}.' for n in range(count)}
    with SQLiteKnowledgeStore(tmp_path/'state') as store:
        src,prepared=publish_text(store,json.dumps(text),filename='scale.json')
        assert len(prepared.chunks)==count
        timings=[]
        for n in range(p['performance']['queries']):
            query=f'PERFKEY{(n*19)%count:04d}';started=perf_counter();rows=store.lexical_candidates(query,ACCESS)
            timings.append((perf_counter()-started)*1000);assert rows and query in rows[0].chunk.text
        report=dict(chunks=count,queries=len(timings),p50Ms=percentile(timings,.5),p95Ms=percentile(timings,.95),
            maxMs=max(timings),timingsMs=timings,footprint={f.name:f.stat().st_size for f in store.files.root.glob('knowledge.db*')})
        (tmp_path/'performance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        assert report['p95Ms']<=p['quality']['ftsP95Ms']
