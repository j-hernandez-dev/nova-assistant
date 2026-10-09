"""Synthetic producer/provider doubles, real Application and local store."""
from types import SimpleNamespace
from local_cli.application.commands import ApplicationCommand,CommandKind
from local_cli.application.knowledge_host import KnowledgeCommand
from local_cli.application.session import AgentSessionCoordinator
from local_cli.application.events import EventBufferConfig
from local_cli.bootstrap_knowledge import knowledge_factory
from local_cli.core.contracts import new_command_id
from tests.test_nova_core_phase4_session import ScriptedProvider,start
from tests.knowledge_inputs_v1.k1_helpers import projection,PAYLOAD


def setup(tmp_path,prepare=projection,**kwargs):
    work=tmp_path/'workspace';work.mkdir(exist_ok=True)
    file=tmp_path/'synthetic ñ.txt';file.write_bytes(PAYLOAD)
    app=AgentSessionCoordinator(provider=ScriptedProvider(['Synthetic response']),model='local',
        event_config=EventBufferConfig(),
        tool_factory=lambda w:[],initial_messages_factory=lambda w,t:[{'role':'system','content':'Synthetic system'}],
        knowledge_factory=knowledge_factory(tmp_path/'private-state',prepare=prepare),**kwargs)
    sid=start(app,work).session_id
    actor=app.register_knowledge_actor('cli_tty',lambda:True)
    return SimpleNamespace(app=app,sid=sid,actor=actor,file=file,work=work)


def command(case,name='source_import',args=None,**kw):
    return KnowledgeCommand(kw.get('command_id') or new_command_id(),kw.get('session_id') or case.sid,
        name,args if args is not None else {'path':str(case.file)},
        kw.get('revision',case.app.get_snapshot(case.sid).state_revision))


def invoke(case,name='source_import',args=None,**kw):
    receipt=case.app.execute_knowledge(command(case,name,args,**kw),actor=case.actor)
    assert receipt['accepted'],receipt
    if receipt['createdIds']:
        op=case.app._service_operations[receipt['createdIds']['operationId']]
        assert op.done.wait(5), 'Synthetic operation did not complete'
        return receipt,op
    return receipt,None


def refs(case): return case.app.get_snapshot(case.sid).services['knowledge']['attachmentRefs']


def close(case):
    case.app.close_knowledge()
    assert case.app._knowledge.closed.wait(5)


def submit(case,attachments,content='Actual synthetic user assertion'):
    return case.app.handle(ApplicationCommand(new_command_id(),CommandKind.SUBMIT_USER_INPUT,
        {'content':content,'attachmentRefs':attachments},case.sid))
