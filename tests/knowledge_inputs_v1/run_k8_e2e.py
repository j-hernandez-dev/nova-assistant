"""K8 explicit real local chat campaign; no scripted responses/embedding calls.

All state is private outside Git. Host fixtures use an explicitly registered
test actor, not a claim of native user clicks. HTTP example.com is the only
public fixture; actual ToolRuntime/S5 acquisition is required for that case.
"""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import time
import urllib.request

from local_cli.application.commands import ApplicationCommand,CommandKind
from local_cli.application.knowledge_host import KnowledgeCommand
from local_cli.application.memory import MemoryCommand
from local_cli.application.providers import ProviderManager
from local_cli.application.rag import RAGService
from local_cli.application.secrets import SecretRedactor
from local_cli.bootstrap_cli import create_cli_application
from local_cli.config import Config
from local_cli.core.contracts import new_command_id,EventKind
from local_cli.ollama_client import OllamaClient
from local_cli.providers.ollama_provider import OllamaProvider
from local_cli.tools.web_fetch_tool import WebFetchTool
from local_cli.tools.write_tool import WriteTool
from local_cli.application.persistence import PersistenceService
from local_cli.infrastructure.persistence import LegacyConversationRepository,LegacySessionSnapshotStore
from tests.knowledge_inputs_v1.k8_fixtures import load,protocol,payload,FIXTURES


ROOT=Path(__file__).resolve().parents[2]
ABSTENTIONS=('unknown','no evidence','not available','no information','cannot determine','no source','no relevant','not provided')


def api(endpoint,data=None):
    url='http://127.0.0.1:11434/api/'+endpoint
    request=urllib.request.Request(url,data=json.dumps(data).encode() if data is not None else None,
        headers={'Content-Type':'application/json'})
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request,timeout=15) as stream:return json.load(stream)


def verify(freeze):
    for row in freeze['files']:
        if hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest()!=row['sha256']:raise ValueError('FROZEN_FILE_CHANGED: '+row['path'])


def grounded_score(case,row):
    """Pure pre-frozen scorer. Never insert gold into a model request."""
    lifecycle=row['turnStatus']=='completed' and row['terminalCount']==1
    values=case.get('goldValues') or ([case['goldValue']] if case.get('goldValue') else [])
    response=row['answer'];correct=all(v.casefold() in response.casefold() for v in values)
    if case.get('abstain'):correct=any(s in response.casefold() for s in ABSTENTIONS)
    evidence=not case.get('requiredSource') or bool(row['admittedSources']) and all(
        v.casefold() in row['admittedText'].casefold() for v in values)
    if case.get('memoryValue'):
        correct &= case['memoryValue'].casefold() in response.casefold()
        evidence &= case['memoryValue'] in row['memoryText']
    citations=not row['invalidAccepted'] and (not case.get('citation') or bool(row['validCitations']) and not row.get('invalidCitations'))
    tools=not case.get('requiredTool') or case['requiredTool'] in row['completedTools'] and any(
        v.casefold() in row['toolText'].casefold() for v in values)
    if case.get('abstain'):evidence &= not row['admittedSources']
    return dict(pass_=bool(lifecycle and correct and evidence and citations and tools and row['authoritySafe']),
        lifecycle=lifecycle,answerCorrect=bool(correct),grounded=bool(evidence and tools),citationValid=bool(citations),
        failureClass='PRODUCT_CONTRACT' if not lifecycle or not row['authoritySafe'] or row['invalidAccepted'] else
            'RETRIEVAL_FAILURE' if not evidence or not tools else 'CITATION_FAILURE' if not citations else
            'MODEL_BEHAVIOR' if not correct else None)


def create(directory,work,state,model):
    requests=[]
    peer=OllamaProvider(base_url=model['endpoint']);original=peer.chat_stream
    def observe(name,messages,**kwargs):
        request=dict(model=name,messages=deepcopy(messages),kwargs=deepcopy(kwargs),response=[])
        requests.append(request)
        for chunk in original(name,messages,**kwargs):request['response'].append(deepcopy(chunk));yield chunk
    peer.chat_stream=observe
    manager=ProviderManager(peer,model['name']);manager.redactor=SecretRedactor(source={})
    config=Config(config_file=str(directory/'missing-config'));config.state_dir=str(state);config.model=model['name']
    config.num_ctx=model['contextWindow'];config.context_resource_limit=model['contextWindow']
    config.temperature=model['temperature'];config.think_mode=model['think'];config.max_iterations=model['maxIterations']
    config.memory_embedding_model='';config.memory_auto_capture='off';config.web_search_enabled=False
    persist=PersistenceService(workspace=work,conversation=LegacyConversationRepository(directory/'transcript',work),
        snapshots=LegacySessionSnapshotStore(directory/'transcript'),redactor=manager.redactor)
    cli=create_cli_application(config=config,provider_manager=manager,tools=[WebFetchTool(),WriteTool(cwd=work)],
        workspace=work,base_messages=[{'role':'system','content':protocol()['system']}],persistence=persist,
        rag_service=RAGService(None),write=lambda _:None)
    app=cli.application;actor=app.register_knowledge_actor('cli_tty',lambda:True)
    memory_actor=app.register_memory_actor('cli_tty',lambda:True)
    return cli,app,actor,memory_actor,requests


def host(app,actor,name,args):
    session=app._session
    cmd=KnowledgeCommand(new_command_id(),session.session_id,name,args,session.state_revision)
    receipt=app.execute_knowledge(cmd,actor=actor)
    if not receipt['accepted']:raise ValueError('HOST_REJECTED: '+receipt['error']['code'])
    op=app._service_operations[receipt['createdIds']['operationId']]
    if not op.done.wait(45):raise TimeoutError('HOST_OPERATION_TIMEOUT')
    if op.status.value!='completed':raise ValueError('HOST_OPERATION_FAILED: '+str(op.result))
    return op.result


def close(cli):
    app=cli.application;cli.close();app.close_knowledge()
    if not app._knowledge.closed.wait(20):raise TimeoutError('KNOWLEDGE_CLOSE_TIMEOUT')
    if app._memory is not None:app._memory.store.close()
    if app.security_audit is not None:app.security_audit.port.close()


def run_campaign(out,freeze):
    verify(freeze);p=protocol();data=load();model=p['model']
    show=api('show',{'model':model['name']});resident=api('ps').get('models',[])
    expected=[r for r in resident if r.get('name')==model['name'] and r.get('digest')==model['expectedDigest']]
    if 'completion' not in show.get('capabilities',[]) or not expected:raise ValueError('MODEL_IDENTITY_OR_CAPABILITY_UNVERIFIED')
    out.mkdir(parents=True,exist_ok=False)
    for key in ('HOME','USERPROFILE','APPDATA','LOCALAPPDATA','TEMP','TMP'):
        folder=out/'private'/key.lower();folder.mkdir(parents=True,exist_ok=True);os.environ[key]=str(folder)
    (out/'attempt.json').write_text(json.dumps(dict(start=datetime.now(timezone.utc).isoformat(),model=model,retries=0,
        scriptedInference=False,cloud=False,embeddingCalls=False,show=show,resident=resident),indent=2),encoding='utf-8')
    rows=[];extraction={r['id']:r for r in data['extraction']}
    for case in data['e2e']:
        directory=out/case['id'];directory.mkdir();work=directory/'workspace';work.mkdir();state=directory/'state'
        cli,app,actor,mactor,requests=create(directory,work,state,model)
        row=dict(id=case['id'],scenario=case['scenario'],model=model,exception=None)
        try:
            if case.get('sourceKey'):
                source=extraction[case['sourceKey']];file=directory/source['filename'];file.write_bytes(payload(source))
                host(app,actor,'source_import',{'path':str(file),'scope':'WORKSPACE' if case['scenario'] in ('multi-session','scope') else 'SESSION'})
                ref=app.get_snapshot(app._session.session_id).services['knowledge']['attachmentRefs'][0]
                if case.get('replacementText'):
                    file=directory/'updated.txt';file.write_text(case['replacementText'],encoding='utf-8')
                    host(app,actor,'source_refresh',{'sourceId':ref['sourceId'],'path':str(file)})
                if case['scenario']=='delete':host(app,actor,'source_delete',{'sourceId':ref['sourceId']})
                if case['scenario'] in ('multi-session','scope'):
                    close(cli)
                    if case['scenario']=='scope':work=directory/'foreign-workspace';work.mkdir()
                    cli,app,actor,mactor,requests=create(directory,work,state,model)
            if case['scenario']=='conflict':
                for i,text in enumerate([case['textA'],case['textB']]):
                    file=directory/f'conflict-{i}.txt';file.write_text(text,encoding='utf-8')
                    host(app,actor,'source_import',{'path':str(file),'scope':'SESSION'})
            if case.get('memoryValue'):
                result=app.execute_memory(MemoryCommand(new_command_id(),app._session.session_id,'memory_remember',
                    {'kind':'PREFERENCE','text':'The synthetic interface accent preference is '+case['memoryValue']+'.','key':'synthetic.accent'}),actor=mactor)
                if not result['completed']:raise ValueError('MEMORY_SEED_FAILED')
            before=app._memory.store.storage_stats()['records'] if app._memory else 0
            submitted=app.handle(ApplicationCommand(new_command_id(),CommandKind.SUBMIT_USER_INPUT,{'content':case['query']},app._session.session_id))
            if not submitted.accepted:raise ValueError('TURN_REJECTED')
            turn=app._session.turns[-1];started=time.perf_counter()
            if not turn.done.wait(model['turnWaitSeconds']):
                turn.cancellation.request();raise TimeoutError('E2E_TURN_TIMEOUT')
            capsule=turn.knowledge_admission.capsule if turn.knowledge_admission else None
            final_prompt=requests[-1]['messages'] if requests else []
            admitted_text='\n'.join(m.get('content','') for m in final_prompt if 'KNOWLEDGE EVIDENCE' in m.get('content',''))
            memory_text='\n'.join(m.get('content','') for m in final_prompt if 'MEMORY CONTEXT' in m.get('content',''))
            after=app._memory.store.storage_stats()['records'] if app._memory else 0
            events=app.poll_events(app.subscribe_events(app._session.session_id,after_sequence=0,include_internal=True))
            completed_tools=[e.payload['name'] for e in events if e.kind is EventKind.TOOL_COMPLETED and
                e.operation_id in turn.tool_operations and e.payload.get('toolStatus')=='completed']
            tool_text='\n'.join(m.get('content','') for m in final_prompt if m.get('role')=='tool')
            names=[call.get('function',{}).get('name') for request in requests for chunk in request['response']
                for call in chunk.get('message',{}).get('tool_calls',[])]
            receipts=turn.citation_reports[-1] if turn.citation_reports else {'valid':[],'invalid':[]}
            targets={e.citation_id:e.target.to_dict() for e in capsule.evidence} if capsule else {}
            invalid_accepted=any(r['citationId'] not in targets or any(r.get(k)!=targets[r['citationId']].get(k)
                for k in ('sourceId','revisionId','chunkId','locator')) for r in receipts['valid'])
            row.update(turnStatus=turn.status.value,terminalCount=turn.terminal_count,answer=turn.final_content,
                elapsedMs=(time.perf_counter()-started)*1000,admittedSources=[e.target.to_dict() for e in capsule.evidence] if capsule else [],
                admittedText=admitted_text,memoryText=memory_text,validCitations=receipts['valid'],invalidCitations=receipts['invalid'],
                invalidAccepted=invalid_accepted,retrievalMode=capsule.retrieval_mode if capsule else 'NONE',
                completedTools=completed_tools,toolText=tool_text,
                authoritySafe=after==before and not (directory/'external_sentinel.txt').exists() and not list(work.glob('external_sentinel*')),
                contextReports=turn.context_reports,generations=len(turn.generations))
            row['score']=grounded_score(case,row)
            post=api('ps');row['residencyAfter']=post
            if not any(r.get('name')==model['name'] and r.get('digest')==model['expectedDigest'] for r in post.get('models',[])):
                row['score']=dict(pass_=False,failureClass='MODEL_REVISION_MISMATCH')
        except Exception as exc:
            row['exception']=type(exc).__name__+': '+str(exc);row['score']=dict(pass_=False,failureClass='HARNESS_OR_ENVIRONMENT')
        finally:
            (directory/'requests.json').write_text(json.dumps(requests,ensure_ascii=False,indent=2),encoding='utf-8')
            (directory/'result.json').write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf-8')
            rows.append(row)
            (out/'report.json').write_text(json.dumps(dict(model=model,dataset=data['id'],rows=rows,
                passed=sum(r['score']['pass_'] for r in rows),total=len(rows),realLocalInference=True,scripted=False,
                semanticProfile='NOT_CERTIFIED',cloud=False),ensure_ascii=False,indent=2),encoding='utf-8')
            close(cli)
        print(case['id'],row['score'],flush=True)
    return all(r['score']['pass_'] for r in rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--freeze',required=True,type=Path);args=parser.parse_args();out=args.output.resolve()
    if out.exists() or out==ROOT or ROOT in out.parents:parser.error('Fresh output outside Git required')
    freeze=json.loads(args.freeze.read_text());raise SystemExit(0 if run_campaign(out,freeze) else 1)

if __name__=='__main__':main()
