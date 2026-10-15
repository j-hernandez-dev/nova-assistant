"""Real local RAG+MEMORY/CLI-Desktop backend parity/provider switch fixture.

Document port is test-only real SQLite FTS5, not fake vector/model quality.
No inference/ToolResult substitution; same Application and authenticated controls.
"""
import argparse
import json
from pathlib import Path
import sqlite3
from unittest.mock import patch
from local_cli.application.commands import ApplicationCommand,CommandKind
from local_cli.application.memory import MemoryCommand
from local_cli.application.rag import RAGService
from local_cli.core.contracts import new_command_id
from local_cli.interfaces.cli_application import CliApplicationClient
from local_cli.interfaces.jsonl_application import JsonlApplicationAdapter
from local_cli.interfaces.approval_proof import approval_proof
from tests.memory_v1.run_m8_quality import create,control,answer,close


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();out=args.output.resolve()
    if out.exists():p.error('New output required')
    out.mkdir(parents=True);work=out/'workspace';work.mkdir()
    doc=sqlite3.connect(out/'documents.db',check_same_thread=False);doc.execute('CREATE VIRTUAL TABLE docs USING fts5(path,text)')
    doc.execute('INSERT INTO docs VALUES (?,?)',('synthetic-cedar.md','The Cedar deployment region is EAST_ZONE.'));doc.commit()
    class Documents:
        def index(self):return {'files':1,'chunks':1}
        def query(self,text,top_k):
            return [dict(file_path=row[0],content=row[1],chunk_index=0,score=1.0)
                for row in doc.execute('SELECT path,text FROM docs WHERE docs MATCH ? LIMIT ?',('Cedar',top_k))]
    app,sid,actor,audit=create(out,work,4096,'qwen3.5:9b');frames=[];key='b7'*32
    report={'phase':'M8','syntheticOnly':True,'scriptedInference':False,'ragAdapter':'TEST_ONLY_REAL_SQLITE_FTS5_NOT_SEMANTIC_MODEL',
        'desktopUI':'NOT_LAUNCHED_BACKEND_PARITY_ONLY'}
    desktop=None;cli=None
    try:
        with patch.object(CliApplicationClient,'_human_tty',staticmethod(lambda:True)):
            cli=CliApplicationClient(app,sid,write=lambda _:None)
            first=cli.memory('memory_remember',{'kind':'PREFERENCE','text':'The interface accent preference is COBALT_UI.','key':'preference.accent'})
            assert first['completed']
        desktop=JsonlApplicationAdapter(app,sid,frames.append,host_approval_key=key)
        command=MemoryCommand('m8-desktop-inspect',sid,'memory_show',{'memoryId':first['data']['memoryId']},app.get_snapshot(sid).state_revision)
        desktop.handle(dict(type='memory_command',id='inspect',command=command.to_dict(),hostMemoryProof=approval_proof(key,command.to_dict())))
        inspection=frames[-1]['data'];assert inspection['completed']
        assert inspection['data']['record']['canonicalText']=='The interface accent preference is COBALT_UI.'
        app._rag=RAGService(Documents());app._rag.set_enabled(True)
        case={'id':'rag-memory','type':'rag_memory','question':'What Cedar deployment region and interface accent are configured?',
            'gold':None,'accepted':[]}
        measured=answer(app,sid,case,{})
        value=measured.get('answer') or '';b=measured.get('budget') or {}
        report['ragMemory']=dict(**measured,combinedCorrect='EAST_ZONE' in value and 'COBALT_UI' in value,
            sharedCapCorrect=b.get('retrieval_tokens',0)<=int(.15*b.get('available',0)),
            memoryRecords=app._memory.store.storage_stats()['records'])
        transition=app.handle(ApplicationCommand(new_command_id(),CommandKind.CHANGE_MODEL,{'modelId':'qwen2.5:7b'},session_id=sid))
        report['providerSwitch']={'accepted':transition.accepted,'error':transition.error.to_dict() if transition.error else None}
        if transition.accepted:
            switched=answer(app,sid,case,{})
            report['providerSwitch'].update(result=switched,sameSubject=app._memory.subject.value==inspection['data']['record']['subjectId'],
                currentModel=app._session.model,oneMainSession=len({t for t in [sid,app._session.session_id]})==1,
                combinedCorrect='EAST_ZONE' in (switched.get('answer') or '') and 'COBALT_UI' in (switched.get('answer') or ''),
                lifecycleCorrect=switched.get('turnStatus')=='completed' and switched.get('terminalCount')==1)
        report['parity']={'cliWriteReal':first['completed'],'desktopInspectReal':inspection['completed'],
            'sameRecordId':first['data']['memoryId']==inspection['data']['record']['memoryId'],'humanTtyObservationFixture':True}
        report['pass']=bool(report['ragMemory']['combinedCorrect'] and report['ragMemory']['sharedCapCorrect'] and
            report['ragMemory']['memoryRecords']==1 and transition.accepted and report['providerSwitch']['sameSubject'] and
            report['providerSwitch']['oneMainSession'] and report['providerSwitch']['combinedCorrect'] and
            report['providerSwitch']['lifecycleCorrect'])
    except Exception as exc:report.update(errorCode=getattr(exc,'code',type(exc).__name__),pass_=False);report['pass']=False
    finally:
        if desktop:desktop.close()
        if cli:cli.close()
        doc.close();close(app,audit)
        (out/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
        print(json.dumps({'pass':report.get('pass'),'errorCode':report.get('errorCode'),'ragMemory':report.get('ragMemory',{}).get('answer')},ensure_ascii=True))
    raise SystemExit(0 if report.get('pass') else 1)


if __name__=='__main__':main()
