"""Real adapters/common Application; authenticated host channel doubles."""
import pytest
from local_cli.core.contracts import new_command_id
from local_cli.interfaces.cli_application import CliApplicationClient
from local_cli.interfaces.jsonl_application import JsonlApplicationAdapter
from local_cli.interfaces.approval_proof import approval_proof
from local_cli.interfaces.knowledge_cli import handle_knowledge_command
from tests.knowledge_inputs_v1.k2_helpers import setup,command,invoke,refs,close


@pytest.mark.parametrize('proof_kind',['valid','missing','tampered','wrong-session','no-key'])
def test_jsonl_import_requires_authenticated_exact_host_intent(proof_kind,tmp_path):
    c=setup(tmp_path);sent=[];key='34'*32
    adapter=JsonlApplicationAdapter(c.app,c.sid,sent.append,host_approval_key=None if proof_kind=='no-key' else key)
    try:
        wire=command(c).to_dict()
        if proof_kind=='wrong-session': wire['sessionId']='ses_foreign'
        proof=approval_proof(key,wire)
        if proof_kind=='tampered':wire['arguments']['scope']='WORKSPACE'
        adapter.handle(dict(type='knowledge_command',id=9,command=wire,
                            **({} if proof_kind=='missing' else {'hostKnowledgeProof':proof})))
        if proof_kind=='valid':
            result=sent[-1]['data'];assert sent[-1]['type']=='knowledge_result' and result['accepted']
            assert c.app._service_operations[result['createdIds']['operationId']].done.wait(5)
            assert refs(c)[0]['state']=='READY'
        else:
            assert sent[-1]['code']=='SOURCE_NOT_AUTHORIZED'
            assert c.app._knowledge.service is None and not (tmp_path/'private-state').exists()
    finally:adapter.close();close(c)


def test_closed_pipe_cannot_reuse_authenticated_host_actor(tmp_path):
    c=setup(tmp_path);adapter=JsonlApplicationAdapter(c.app,c.sid,lambda value:None,host_approval_key='45'*32)
    cmd=command(c);adapter.close()
    assert not c.app.execute_knowledge(cmd,actor=adapter._knowledge_actor)['accepted']
    close(c)


@pytest.mark.parametrize('tty',[True,False])
def test_cli_explicit_path_spaces_default_session_and_host_tty_enforcement(tmp_path,monkeypatch,tty):
    monkeypatch.setattr(CliApplicationClient,'_human_tty',staticmethod(lambda:tty))
    c=setup(tmp_path);out=[];console=CliApplicationClient(c.app,c.sid,write=out.append)
    try:
        handle_knowledge_command('"'+str(c.file)+'"',console,attach=True)
        if tty:
            assert refs(c)[0]['state']=='READY' and console._attachment_refs==refs(c)
            handle_knowledge_command('detach',console);assert console._attachment_refs==[]
            handle_knowledge_command('select '+refs(c)[0]['sourceId'],console)
            assert console._attachment_refs==refs(c)
            receipt=console.submit_user_input('Only actual synthetic text')
            assert receipt.accepted
            assert console._attachment_refs==[]
            assert next(m for m in c.app._session.transcript if m['role']=='user')['content']=='Only actual synthetic text'
        else:
            assert c.app._knowledge.service is None and 'SOURCE_NOT_AUTHORIZED' in ''.join(out)
    finally:console.close();close(c)


def test_cli_workspace_import_list_promote_delete_share_backend_no_second_loop(tmp_path,monkeypatch):
    monkeypatch.setattr(CliApplicationClient,'_human_tty',staticmethod(lambda:True))
    c=setup(tmp_path);console=CliApplicationClient(c.app,c.sid,write=lambda x:None)
    try:
        handle_knowledge_command(str(c.file),console,attach=True)
        original=refs(c)[0]
        handle_knowledge_command('promote '+original['sourceId'],console)
        assert len(refs(c))==2
        handle_knowledge_command('list',console)
        handle_knowledge_command('delete '+original['sourceId'],console)
        assert len(refs(c))==1 and c.app._session.turns==[]
        handle_knowledge_command('import '+str(c.file),console)
        assert len(refs(c))==2
    finally:console.close();close(c)
