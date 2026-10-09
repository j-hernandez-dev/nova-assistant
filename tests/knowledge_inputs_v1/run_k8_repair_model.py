"""One independent real-local compliance campaign; never the 14 original cases."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.memory import MemoryCommand
from local_cli.core.contracts import EventKind, new_command_id
from tests.knowledge_inputs_v1.run_k8_e2e import create, host, close, api
from tests.knowledge_inputs_v1.k8_repair_helpers import corpus, protocol, verify_freeze, score, FIXTURES


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--product-freeze',required=True,type=Path);args=parser.parse_args()
    root=Path(__file__).resolve().parents[2];out=args.output.resolve()
    if out.exists() or out==root or root in out.parents: parser.error('Fresh external output required')
    verify_freeze(FIXTURES/'k8_repair_freeze_v1.json');verify_freeze(args.product_freeze)
    p=protocol();model=p['model'];show=api('show',{'model':model['name']});resident=api('ps')
    if 'completion' not in show.get('capabilities',[]) or not any(m.get('digest')==model['expectedDigest'] and
        m.get('name')==model['name'] for m in resident.get('models',[])):
        raise ValueError('MODEL_IDENTITY_OR_RESIDENCY_UNVERIFIED; no automatic model loading')
    out.mkdir(parents=True)
    for key in ('HOME','USERPROFILE','APPDATA','LOCALAPPDATA','TEMP','TMP'):
        folder=out/'private'/key.lower();folder.mkdir(parents=True);os.environ[key]=str(folder)
    (out/'attempt.json').write_text(json.dumps(dict(start=datetime.now(timezone.utc).isoformat(),
        model=model,retries=0,scripted=False,cloud=False,embeddings=False,originalCampaignExecuted=False),indent=2),encoding='utf-8')
    rows=[]
    for case in corpus()['realCases']:
        directory=out/case['id'];directory.mkdir();work=directory/'workspace';work.mkdir()
        cli,app,actor,mactor,requests=create(directory,work,directory/'state',model)
        row=dict(id=case['id'],group=case['group'],exception=None)
        try:
            for document in case['documents']:
                path=directory/document['name'];path.write_text(document['text'],encoding='utf-8')
                host(app,actor,'source_import',{'path':str(path),'scope':'SESSION'})
            if case.get('memory'):
                result=app.execute_memory(MemoryCommand(new_command_id(),app._session.session_id,'memory_remember',
                    {'kind':'PREFERENCE','text':case['memory'],'key':'repair.display'}),actor=mactor)
                if not result['completed']:raise ValueError('MEMORY_SEED_FAILED')
            before=app._memory.store.storage_stats()['records'];started=perf_counter()
            receipt=app.handle(ApplicationCommand(new_command_id(),CommandKind.SUBMIT_USER_INPUT,
                {'content':case['query']},app._session.session_id))
            if not receipt.accepted:raise ValueError('TURN_REJECTED')
            turn=app._session.turns[-1]
            if not turn.done.wait(model['turnWaitSeconds']):
                turn.cancellation.request();raise TimeoutError('TURN_TIMEOUT')
            capsule=turn.knowledge_admission.capsule
            messages=requests[-1]['messages'];content=lambda key:'\n'.join(m.get('content','') for m in messages if key in m.get('content',''))
            reports=turn.citation_reports[-1] if turn.citation_reports else dict(valid=[],invalid=[])
            targets={e.citation_id:e.target.to_dict() for e in capsule.evidence}
            names=[call.get('function',{}).get('name') for request in requests for chunk in request['response']
                for call in chunk.get('message',{}).get('tool_calls',[])]
            row.update(turnStatus=turn.status.value,terminalCount=turn.terminal_count,answer=turn.final_content,
                admittedSources=[e.target.to_dict() for e in capsule.evidence],admittedText=content('KNOWLEDGE EVIDENCE'),
                memoryText=content('MEMORY CONTEXT'),validCitations=reports['valid'],invalidCitations=reports['invalid'],
                invalidAccepted=any(r['citationId'] not in targets or any(r.get(k)!=targets[r['citationId']].get(k)
                    for k in ('sourceId','revisionId','chunkId','locator')) for r in reports['valid']),
                sideEffectAttempts=[n for n in names if n not in ('read','grep','glob','web_fetch','web_search')],
                createdFiles=[str(f.relative_to(work)) for f in work.rglob('*') if f.is_file()],
                memoryCountUnchanged=app._memory.store.storage_stats()['records']==before,
                mode=capsule.retrieval_mode,elapsedMs=(perf_counter()-started)*1000,contextReports=turn.context_reports)
            row['score']=score(case,row);row['residencyAfter']=api('ps')
            if not any(m.get('digest')==model['expectedDigest'] and m.get('name')==model['name'] for m in row['residencyAfter'].get('models',[])):
                row['score']['passed']=False;row['score']['failure']='MODEL_REVISION_MISMATCH'
        except Exception as exc:
            row['exception']=type(exc).__name__+': '+str(exc);row['score']=dict(passed=False,failure='HARNESS_OR_ENVIRONMENT')
        finally:
            (directory/'requests.json').write_text(json.dumps(requests,ensure_ascii=False,indent=2),encoding='utf-8')
            (directory/'result.json').write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf-8')
            rows.append(row);close(cli)
            groups={g:dict(passed=sum(r['score']['passed'] for r in rows if r['group']==g),
                total=sum(r['group']==g for r in rows)) for g in ('citation','grounding','injection')}
            report=dict(dataset=corpus()['id'],groups=groups,rows=rows,retries=0,realLocal=True,scripted=False,
                originalCampaignExecuted=False,status='PASS' if all(r['score']['passed'] for r in rows) else 'FAIL')
            (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(case['id'],row['score'],flush=True)
    raise SystemExit(0 if all(r['score']['passed'] for r in rows) else 1)


if __name__=='__main__':main()
