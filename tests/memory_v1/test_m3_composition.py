"""Normal CLI/server composition with synthetic provider catalog, no inference.

Filesystem, MemoryService, SQLite/FTS, audit and Application are real. Only
unrelated RAG/logger resources and the human TTY observation are fixtures.
"""
from types import SimpleNamespace

from local_cli.application.memory import MemoryCommand
from local_cli.application.providers import ProviderManager
from local_cli.application.rag import RAGService
from local_cli.application.secrets import SecretRedactor
from local_cli.config import Config
from local_cli.core.contracts import new_command_id
from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit
from local_cli.interfaces.approval_proof import approval_proof
from local_cli.interfaces.cli_application import CliApplicationClient
from tests.test_nova_core_phase8_providers import Provider


def test_normal_composition_roots_share_durable_identity_without_llm_or_eager_store(tmp_path,monkeypatch):
    from local_cli.bootstrap_cli import create_cli_application
    from local_cli.bootstrap_server import create_server_application
    work=tmp_path/'workspace'; work.mkdir()
    config=Config(); config.state_dir=str(tmp_path/'state'); config.model='old'
    provider=Provider(); manager=ProviderManager(provider,'old')
    manager.redactor=SecretRedactor(source={})
    cli_audit=JsonlSecurityAudit(tmp_path/'cli-audit',workspace=work)
    monkeypatch.setattr('local_cli.bootstrap_cli.create_security_audit',lambda _:cli_audit)
    monkeypatch.setattr(CliApplicationClient,'_human_tty',staticmethod(lambda:True))
    cli=create_cli_application(config=config,provider_manager=manager,tools=[],workspace=work,
        base_messages=[{'role':'system','content':'Synthetic system'}],persistence=None,rag_service=RAGService(None),write=lambda _:None)
    assert cli.application._memory is None and not (tmp_path/'state/memory').exists()
    first=cli.memory('memory_remember',{'kind':'PREFERENCE','text':'Synthetic normal composition preference'})
    assert first['completed']; cli.close(); cli.application._memory.store.close(); cli_audit.close()
    server_audit=JsonlSecurityAudit(tmp_path/'server-audit',workspace=work)
    monkeypatch.setattr('local_cli.bootstrap_server.create_security_audit',lambda _:server_audit)
    server=SimpleNamespace(_config=config,_cwd=work,_provider=provider,_provider_manager=manager,
        _tools=[],_system_prompt='Synthetic system',_messages=[{'role':'system','content':'Synthetic system'}],
        _skills_loader=None,_tool_cache=None,_token_tracker=None,_conversation_store=None,_rag_service=RAGService(None),
        _sub_agent_runner=None,_auxiliary_services=None,_environment={},_approval_host_key='ab'*32,
        _sync_provider_projection=lambda:None)
    frames=[]; create_server_application(server,send=frames.append)
    assert server._application._memory is None
    def control(action,args):
        app=server._application; sid=server._app_adapter.session_id
        command=MemoryCommand(new_command_id(),sid,'memory_'+action,args,app.get_snapshot(sid).state_revision).to_dict()
        server._app_adapter.handle(dict(type='memory_command',id=action,command=command,
            hostMemoryProof=approval_proof('ab'*32,command)))
        return frames[-1]['data']
    found=control('search',{'query':'composition'})
    assert found['completed'] and found['data']['records'][0]['memoryId']==first['data']['memoryId']
    new=control('correct',{'memoryId':first['data']['memoryId'],'revision':1,'text':'Synthetic corrected composition preference'})
    assert new['completed'] and new['data']['supersedesMemoryId']==first['data']['memoryId']
    deleted=control('forget',{'memoryId':new['data']['memoryId'],'revision':1})
    assert deleted['completed'] and control('search',{'query':'corrected'})['data']['records']==[]
    assert provider.requests==[] and server._application.get_snapshot(server._app_adapter.session_id).turns==()
    assert not any('MEMORY' in command for command in [str(t) for t in server._tools])
    server._app_adapter.close(); server._application._memory.store.close(); server_audit.close()
