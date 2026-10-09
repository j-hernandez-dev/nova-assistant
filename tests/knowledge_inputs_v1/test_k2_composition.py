"""Normal composition and audit are real. No inference or parser doubles here."""
from types import SimpleNamespace
import pytest
from local_cli.application.knowledge_host import KnowledgeCommand
from local_cli.application.providers import ProviderManager
from local_cli.application.rag import RAGService
from local_cli.application.secrets import SecretRedactor
from local_cli.bootstrap_cli import create_cli_application
from local_cli.bootstrap_server import create_server_application
from local_cli.config import Config
from local_cli.core.contracts import new_command_id
from local_cli.core.knowledge import KnowledgeError
from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit
from local_cli.interfaces.approval_proof import approval_proof
from local_cli.interfaces.cli_application import CliApplicationClient
from local_cli.interfaces.jsonl_application import JsonlApplicationAdapter
from tests.test_nova_core_phase8_providers import Provider
from tests.knowledge_inputs_v1.k2_helpers import setup,command,invoke,refs,close


def test_cli_and_server_normal_roots_activate_host_route_with_k3_extraction(tmp_path,monkeypatch):
    work=tmp_path/'workspace';work.mkdir();file=tmp_path/'synthetic.txt';file.write_bytes(b'Synthetic normal host bytes')
    config=Config();config.state_dir=str(tmp_path/'state');config.model='old'
    provider=Provider();manager=ProviderManager(provider,'old');manager.redactor=SecretRedactor(source={})
    audit=JsonlSecurityAudit(tmp_path/'cli-audit',workspace=work)
    monkeypatch.setattr('local_cli.bootstrap_cli.create_security_audit',lambda w:audit)
    monkeypatch.setattr(CliApplicationClient,'_human_tty',staticmethod(lambda:True))
    cli=create_cli_application(config=config,provider_manager=manager,tools=[],workspace=work,
        base_messages=[{'role':'system','content':'Synthetic system'}],persistence=None,
        rag_service=RAGService(None),write=lambda t:None)
    try:
        assert cli.application._knowledge.service is None and not (tmp_path/'state/knowledge').exists()
        receipt=cli.knowledge('source_import',{'path':str(file),'scope':'WORKSPACE'})
        assert receipt['accepted']
        assert cli.application._service_operations[receipt['createdIds']['operationId']].done.wait(5)
        op=cli.application._service_operations[receipt['createdIds']['operationId']]
        assert op.status.value=='completed'
        old_ref=cli.snapshot().services['knowledge']['attachmentRefs'][0]
        assert old_ref['state']=='READY' and cli.snapshot().turns==()
    finally:
        cli.close();assert cli.application._knowledge.closed.wait(5);audit.close()
    audit=JsonlSecurityAudit(tmp_path/'server-audit',workspace=work)
    monkeypatch.setattr('local_cli.bootstrap_server.create_security_audit',lambda w:audit)
    server=SimpleNamespace(_config=config,_cwd=work,_provider=provider,_provider_manager=manager,
        _tools=[],_system_prompt='Synthetic system',_messages=[{'role':'system','content':'Synthetic system'}],
        _skills_loader=None,_tool_cache=None,_token_tracker=None,_conversation_store=None,_rag_service=RAGService(None),
        _sub_agent_runner=None,_auxiliary_services=None,_environment={},_approval_host_key='ab'*32,
        _sync_provider_projection=lambda:None)
    frames=[];create_server_application(server,send=frames.append)
    try:
        app=server._application;sid=server._app_adapter.session_id
        assert app._knowledge.service is None and app._memory is None
        wire=KnowledgeCommand(new_command_id(),sid,'source_list',{},app.get_snapshot(sid).state_revision).to_dict()
        server._app_adapter.handle(dict(id='synthetic',type='knowledge_command',command=wire,hostKnowledgeProof=approval_proof('ab'*32,wire)))
        receipt=frames[-1]['data'];assert receipt['accepted']
        op=app._service_operations[receipt['createdIds']['operationId']];assert op.done.wait(5)
        assert op.status.value=='completed' and app.get_snapshot(sid).services['knowledge']['attachmentRefs'][0]['sourceId']==old_ref['sourceId']
        assert provider.requests==[] and app.get_snapshot(sid).turns==()
    finally:
        server._app_adapter.close();assert app._knowledge.closed.wait(5);audit.close()


def test_audit_pre_effect_failure_denies_acquisition_no_store_or_auto_retry(tmp_path,monkeypatch):
    c=setup(tmp_path);audit=JsonlSecurityAudit(tmp_path/'audit',workspace=c.work)
    from local_cli.application.security_audit import SecurityAuditService
    from local_cli.core.security_audit import SecurityAuditError
    c.app.security_audit=SecurityAuditService(audit,redactor=c.app.redactor)
    def fail(*args,**kwargs):raise SecurityAuditError('SECURITY_AUDIT_DELIVERY_FAILED')
    monkeypatch.setattr(c.app.security_audit,'before_effect',fail)
    try:
        _,op=invoke(c)
        assert op.status.value=='failed' and c.app._knowledge.service is None
        assert not (tmp_path/'private-state').exists()
    finally:close(c);audit.close()


def test_workspace_rebind_invalidates_session_refs_and_cannot_cross_scope_or_reopen_origin(tmp_path):
    c=setup(tmp_path)
    try:
        invoke(c);old=refs(c)[0];previous=c.app._knowledge
        new=tmp_path/'other-workspace';new.mkdir()
        c.app.rebind_legacy_workspace(new,base_messages=[{'role':'system','content':'Synthetic new system'}],persistence=None,rag=None)
        assert previous.closed.is_set() and refs(c)==[]
        receipt,op=invoke(c,'source_list',{})
        assert op.status.value=='completed' and refs(c)==[]
        svc=c.app._knowledge.service
        with pytest.raises(KnowledgeError):svc.store.get_source(old['sourceId'],svc.access)
    finally:close(c)


def test_terminal_audit_gap_keeps_observed_publication_and_never_retries_or_rolls_back(tmp_path,monkeypatch):
    c=setup(tmp_path);audit=JsonlSecurityAudit(tmp_path/'audit',workspace=c.work)
    from local_cli.application.security_audit import SecurityAuditService
    c.app.security_audit=SecurityAuditService(audit,redactor=c.app.redactor)
    original=audit.flush;calls=[]
    def flush():
        calls.append(1)
        if len(calls)>1:raise OSError('Synthetic terminal fsync failure')
        return original()
    monkeypatch.setattr(audit,'flush',flush)
    try:
        _,op=invoke(c)
        assert op.status.value=='completed' and refs(c)[0]['state']=='READY'
        assert op.result['securityAudit']['gap'] is True
        assert op.result['securityAudit']['retryAllowed'] is False
        svc=c.app._knowledge.service
        assert svc.store.read_blob(refs(c)[0]['revisionId'],svc.access)
        assert svc.store._connection.execute('SELECT count(*) FROM import_operations').fetchone()[0]==1
    finally:close(c);audit.close()


@pytest.mark.parametrize('mode',['chat','application_command'])
def test_jsonl_malformed_attachment_returns_error_without_crashing_reader_or_creating_turn(tmp_path,mode):
    c=setup(tmp_path);frames=[];adapter=JsonlApplicationAdapter(c.app,c.sid,frames.append)
    try:
        payload=dict(content='Actual synthetic input',attachmentRefs=[{'path':'/forged'}])
        request=dict(type='chat',id=1,**payload) if mode=='chat' else dict(type=mode,id=1,command={
            'schemaVersion':1,'kind':'SubmitUserInput','commandId':new_command_id(),'sessionId':c.sid,
            'expectedRevision':None,'payload':payload})
        assert adapter.handle(request)
        assert frames[-1]['type']=='error' and frames[-1]['code']=='INVALID_APPLICATION_COMMAND'
        assert c.app.get_snapshot(c.sid).turns==()
    finally:adapter.close();close(c)
