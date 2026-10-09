"""One frozen V3 local-model campaign, no original K8 E2E or case retries."""
import argparse
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
from local_cli.application.commands import ApplicationCommand,CommandKind
from local_cli.application.memory import MemoryCommand
from local_cli.core.contracts import new_command_id
from local_cli.core.memory import MemoryAccessScope
from local_cli.core.network import NetworkError
from tests.knowledge_inputs_v1.run_k8_e2e import create,host,close,api
from tests.knowledge_inputs_v1.k8_repair3_helpers import read,verify,score,FIXTURES


class NoExternalNetwork:
    """Harness-only protective double. Any network request is still a FAIL."""
    def resolve(self,*args,**kwargs):raise NetworkError('TEST_UNRELATED_NETWORK_BLOCKED')
    def get(self,*args,**kwargs):raise NetworkError('TEST_UNRELATED_NETWORK_BLOCKED')


def memory_snapshot(app,work):
    service=app._memory
    if service is None:return []
    access=MemoryAccessScope(service.subject,service.identity.resolve_workspace(work))
    page=service.store.list(access,limit=100)
    if page.next_cursor:raise ValueError('Synthetic fixture unexpectedly unbounded')
    return [json.loads(json.dumps(asdict(r),default=str,sort_keys=True)) for r in page.records]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();root=Path(__file__).resolve().parents[2];out=args.output.resolve()
    if out.exists() or out==root or root in out.parents:parser.error('Fresh external output required')
    verify(FIXTURES/'k8_repair3_freeze_v1.json')
    verify(root/'docs/knowledge_inputs_v1/k8_repair3_evidence/product_freeze_v1.json')
    p=read('k8_repair3_protocol_v1.json');data=read('k8_repair3_corpus_v1.json');model=p['model']
    show=api('show',{'model':model['name']});resident=api('ps')
    if 'completion' not in show.get('capabilities',[]) or not any(m.get('name')==model['name'] and m.get('digest')==model['expectedDigest'] for m in resident.get('models',[])):
        raise ValueError('MODEL_IDENTITY_OR_RESIDENCY_UNVERIFIED; no automatic model loading')
    out.mkdir(parents=True)
    for key in ('HOME','USERPROFILE','APPDATA','LOCALAPPDATA','TEMP','TMP'):
        folder=out/'private'/key.lower();folder.mkdir(parents=True);os.environ[key]=str(folder)
    (out/'attempt.json').write_text(json.dumps(dict(start=datetime.now(timezone.utc).isoformat(),
        model=model,show=show,resident=resident,retries=0,scripted=False,cloud=False,embeddings=False,
        networkProtection='harness broker double; any requested network fails',originalCampaignExecuted=False),indent=2),encoding='utf-8')
    rows=[]
    for case in data['realCases']:
        directory=out/case['id'];directory.mkdir();work=directory/'workspace';work.mkdir()
        sentinel=directory/'external-sentinel.txt';sentinel.write_text('synthetic V3 external sentinel',encoding='utf-8')
        sentinel_sha=hashlib.sha256(sentinel.read_bytes()).hexdigest()
        cli,app,actor,mactor,requests=create(directory,work,directory/'state',model)
        runtime=app._session.tool_runtime;observed=[];original=runtime.execute
        # Retain the offered tool schemas, Policy/Grant/ToolRuntime. Protect
        # public I/O only at the test transport; never hide a model tool call.
        runtime._network_service.broker=NoExternalNetwork()
        def observe(invocation,**kwargs):
            result=original(invocation,**kwargs)
            observed.append(dict(name=invocation.name,arguments=dict(invocation.arguments),
                operationId=str(invocation.operation_id),result=result.to_dict()))
            return result
        runtime.execute=observe
        row=dict(id=case['id'],group=case['group'],pair=case.get('pair'),mode=case.get('mode'),exception=None)
        try:
            for doc in case['documents']:
                path=directory/doc['name'];path.write_text(doc['text'],encoding='utf-8')
                host(app,actor,'source_import',{'path':str(path),'scope':'SESSION'})
            if case.get('memory'):
                result=app.execute_memory(MemoryCommand(new_command_id(),app._session.session_id,'memory_remember',
                    {'kind':'PREFERENCE','text':case['memory'],'key':'repair3.accent'}),actor=mactor)
                if not result['completed']:raise ValueError('MEMORY_SEED_FAILED')
            before_memory=memory_snapshot(app,work);before_ceiling=runtime._issuer.ceiling.fingerprint;before_policy=runtime.policy.revision
            start=perf_counter()
            receipt=app.handle(ApplicationCommand(new_command_id(),CommandKind.SUBMIT_USER_INPUT,{'content':case['query']},app._session.session_id))
            if not receipt.accepted:raise ValueError('TURN_REJECTED')
            turn=app._session.turns[-1]
            if not turn.done.wait(model['turnWaitSeconds']):
                turn.cancellation.request();raise TimeoutError('TURN_TIMEOUT')
            capsule=turn.knowledge_admission.capsule;prompt=requests[-1]['messages'] if requests else []
            content=lambda key:'\n'.join(m.get('content','') for m in prompt if key in m.get('content',''))
            reports=turn.citation_reports[-1] if turn.citation_reports else dict(valid=[],invalid=[])
            targets={e.citation_id:e.target.to_dict() for e in capsule.evidence}
            files=sorted(str(f.relative_to(work)) for f in work.rglob('*') if f.is_file())
            after_memory=memory_snapshot(app,work)
            row.update(turnStatus=turn.status.value,terminalCount=turn.terminal_count,answer=turn.final_content,
                admittedSources=[e.target.to_dict() for e in capsule.evidence],admittedText=content('KNOWLEDGE EVIDENCE'),
                memoryText=content('MEMORY CONTEXT'),validCitations=reports['valid'],invalidCitations=reports['invalid'],
                invalidAccepted=any(r['citationId'] not in targets or any(r.get(k)!=targets[r['citationId']].get(k) for k in ('sourceId','revisionId','chunkId','locator')) for r in reports['valid']),
                createdFiles=files,fileContents={name:(work/name).read_text(encoding='utf-8') for name in files},
                memoryUnchanged=before_memory==after_memory,memoryBefore=before_memory,memoryAfter=after_memory,
                authorityUnchanged=runtime._issuer.ceiling.fingerprint==before_ceiling and runtime.policy.revision==before_policy,
                sentinelUnchanged=hashlib.sha256(sentinel.read_bytes()).hexdigest()==sentinel_sha,
                sentinelSha256=sentinel_sha,ceilingBefore=before_ceiling,ceilingAfter=runtime._issuer.ceiling.fingerprint,
                policyRevision=before_policy,toolResults=observed,filesystemMutationDenied=turn.effect_constraints.filesystem_mutation_denied,
                retrievalMode=capsule.retrieval_mode,elapsedMs=(perf_counter()-start)*1000,contextReports=turn.context_reports)
            row['score']=score(case,row);row['residentAfter']=api('ps')
            if not any(m.get('name')==model['name'] and m.get('digest')==model['expectedDigest'] for m in row['residentAfter'].get('models',[])):
                row['score']['passed']=False;row['score']['failure']='MODEL_REVISION_MISMATCH'
        except Exception as exc:
            row['exception']=type(exc).__name__+': '+str(exc);row['score']=dict(passed=False,failure='HARNESS_OR_ENVIRONMENT')
        finally:
            (directory/'requests.json').write_text(json.dumps(requests,ensure_ascii=False,indent=2),encoding='utf-8')
            (directory/'result.json').write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf-8')
            rows.append(row);close(cli)
            groups={g:dict(passed=sum(r['score']['passed'] for r in rows if r['group']==g),total=sum(r['group']==g for r in rows)) for g in ('citation','grounding','effects')}
            (out/'report.json').write_text(json.dumps(dict(dataset=data['id'],groups=groups,rows=rows,realLocal=True,scripted=False,retries=0,
                originalCampaignExecuted=False,status='PASS' if all(r['score']['passed'] for r in rows) else 'FAIL',end=datetime.now(timezone.utc).isoformat()),ensure_ascii=False,indent=2),encoding='utf-8')
        print(case['id'],row['score'],flush=True)
    raise SystemExit(0 if all(r['score']['passed'] for r in rows) else 1)


if __name__=='__main__':main()
