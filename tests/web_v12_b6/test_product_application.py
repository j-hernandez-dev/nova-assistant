"""Real Coordinator/frontend wiring with discovery doubles: CONTRACT evidence only.

The four exported snapshots originate from AgentSessionCoordinator.get_snapshot.
These tests do not certify transport, WebView2 or compatibility evidence profiles.
"""
from dataclasses import replace
from pathlib import Path
import json
import os

import pytest

from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.events import EventBufferConfig
from local_cli.application.session import AgentSessionCoordinator
from local_cli.application.web_product_v12 import WebProductV12
from local_cli.core.contracts import new_command_id
from local_cli.core.web_capabilities_v12 import (
    BROWSER_RISK_ACKNOWLEDGEMENT_VERSION, ControlledFetchCapabilityV12,
    InteractiveBrowserCapabilityV12, WebCapabilitiesV12, WebUnavailableReason,
)
from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit
from local_cli.infrastructure.web_discovery_v12 import WebV12FeatureConfiguration
from local_cli.interfaces.approval_proof import approval_proof
from local_cli.interfaces.cli_application import CliApplicationClient
from local_cli.interfaces.jsonl_application import JsonlApplicationAdapter
from tests.test_nova_core_phase4_session import ScriptedProvider


class ContractDiscovery:
    """Explicit double; never used as a productive compatibility checker."""
    def __init__(self, fetch, browser):
        self.config=WebV12FeatureConfiguration(fetch,browser,
            BROWSER_RISK_ACKNOWLEDGEMENT_VERSION if browser else None)

    def configuration(self):
        return self.config

    def configure(self,fetch,browser,ack):
        self.config=WebV12FeatureConfiguration(fetch,browser,ack)

    def capture(self):
        config=self.config
        return WebCapabilitiesV12(
            ControlledFetchCapabilityV12.state(None if config.controlled_fetch_enabled else
                WebUnavailableReason.FEATURE_DISABLED,compatible=config.controlled_fetch_enabled),
            InteractiveBrowserCapabilityV12.state(None if config.interactive_browser_enabled else
                WebUnavailableReason.FEATURE_DISABLED,compatible=config.interactive_browser_enabled,
                profile='IB_B6_CONTRACT_DISCOVERY_DOUBLE'))


class ContractProductFactory:
    productive=True
    def __init__(self,fetch=False,browser=False):
        self.discovery=ContractDiscovery(fetch,browser)
        self.services=[];self.browser_builds=[];self.records=[]

    def __call__(self,owner,redactor,publish):
        def browser_builder(*args):
            self.browser_builds.append(args)
            raise AssertionError('Native browser forbidden in contract discovery fixture')
        service=WebProductV12(owner,discovery=self.discovery,configure=self.discovery.configure,
            browser_builder=browser_builder,resolver=None,
            record=lambda value:self.records.append(value),redactor=redactor)
        self.services.append(service)
        return service


@pytest.fixture
def product(tmp_path):
    resources=[]
    def create(fetch=False,browser=False):
        workspace=tmp_path/f'workspace-{len(resources)}';workspace.mkdir()
        factory=ContractProductFactory(fetch,browser)
        store=JsonlSecurityAudit(tmp_path/f'audit-{len(resources)}',workspace=workspace)
        app=AgentSessionCoordinator(provider=ScriptedProvider(['contract response']),model='synthetic',
            tool_factory=lambda _:[],web_v12_factory=factory,event_config=EventBufferConfig(),
            security_audit_port=store)
        started=app.handle(ApplicationCommand(new_command_id(),CommandKind.START_SESSION,
            {'workspace':str(workspace.resolve())}))
        assert started.accepted
        resources.append((app,store))
        return app,factory,started.session_id
    yield create
    for app,store in resources:
        app.close_browser()
        store.close()


def host_command(session_id,args,command_id=None):
    return dict(commandId=command_id or new_command_id(),sessionId=session_id,
        name='configure_web_v12',arguments=args)


def export_snapshot(name,snapshot,fetch,browser):
    """Only the owned temp file requested by root; no docs/evidence write here."""
    destination=os.environ.get('NOVA_B6_DESKTOP_SNAPSHOT_PATH')
    if not destination:
        return
    path=Path(destination)
    assert path.is_absolute()
    repo=Path(__file__).resolve().parents[2]
    assert not path.resolve().is_relative_to(repo)
    path.parent.mkdir(parents=True,exist_ok=True)
    corpus=json.loads(path.read_text(encoding='utf-8')) if path.exists() else dict(schemaVersion=1,
        source='AgentSessionCoordinator.get_snapshot',evidenceKind='APPLICATION_CONTRACT_PARITY',
        nativeCertification=False,cases=[])
    corpus['cases']=[case for case in corpus['cases'] if case['name']!=name]
    corpus['cases'].append(dict(name=name,snapshot=snapshot,
        expectedControlledFetchAvailable=fetch,expectedInteractiveBrowserAvailable=browser))
    path.write_text(json.dumps(corpus,ensure_ascii=False,indent=2),encoding='utf-8')


@pytest.mark.parametrize('name,fetch,browser',[
    ('both_unavailable',False,False),('fetch_only',True,False),
    ('browser_only',False,True),('both_available',True,True)],ids=lambda value:str(value))
def test_single_application_snapshot_cli_jsonl_and_desktop_contract_export(product,name,fetch,browser):
    app,factory,sid=product(fetch,browser)
    cli=CliApplicationClient(app,sid,write=lambda _:None,write_error=lambda _:None)
    frames=[];jsonl=JsonlApplicationAdapter(app,sid,frames.append)
    try:
        canonical=app.get_snapshot(sid).to_dict()
        assert cli.application is jsonl.application is app
        assert cli.snapshot().to_dict()==canonical
        jsonl.handle(dict(id='parity',type='get_snapshot',sessionId=sid))
        assert frames[-1]['data']==canonical
        snapshot=canonical['services']['webCapabilitiesV12']
        assert snapshot==factory.services[0].snapshot().to_dict()
        assert snapshot['controlledFetch']['available']['value'] is fetch
        assert snapshot['interactiveBrowser']['available']['value'] is browser
        assert snapshot['interactiveBrowser']['networkIsolation']['value']=='NOT_PROVIDED'
        assert snapshot['interactiveBrowser']['controlClass']['value']=='HOST_UNISOLATED'
        assert canonical['capabilities']['webCapabilitiesV12']==snapshot
        assert canonical['services']['activeWeb']['capabilities']['available']['value'] is not True
        assert app._session.tool_runtime._web_v12 is factory.services[0]
        assert not factory.browser_builds
        export_snapshot(name,canonical,fetch,browser)
    finally:
        cli.close();jsonl.close()


def test_feature_risk_acknowledgement_does_not_issue_approval_or_operation_grant(product):
    app,factory,sid=product()
    actor=app.register_browser_actor('desktop_host',lambda:True)
    args=dict(controlledFetchEnabled=True,interactiveBrowserEnabled=True,
        acknowledgementVersion=BROWSER_RISK_ACKNOWLEDGEMENT_VERSION)
    before=app._session.tool_runtime._issuer.ceiling
    issued_before=dict(app._session.tool_runtime._issuer._issued)
    result=app.execute_browser_control(host_command(sid,args),actor=actor)
    assert factory.discovery.configuration().risk_acknowledgement_version==BROWSER_RISK_ACKNOWLEDGEMENT_VERSION
    assert result['capabilities']['interactiveBrowser']['available']['value'] is True
    assert not app._session.approval_gate.pending()
    after=app._session.tool_runtime._issuer.ceiling
    additions=[cap for cap in after.capabilities if cap not in before.capabilities]
    assert additions and all(cap.permission.name=='application.tool.invoke' for cap in additions)
    assert not any(cap.permission.name in ('network.fetch','browser.act','browser.read') for cap in additions)
    assert app._session.tool_runtime._issuer._issued==issued_before
    assert not factory.services[0]._plans and not factory.browser_builds


def test_host_configuration_replay_does_not_reenable_revoked_browser(product):
    app,factory,sid=product()
    actor=app.register_browser_actor('desktop_host',lambda:True)
    enabled=dict(controlledFetchEnabled=False,interactiveBrowserEnabled=True,acknowledgementVersion=BROWSER_RISK_ACKNOWLEDGEMENT_VERSION)
    command=host_command(sid,enabled)
    initial_revision=app._session.state_revision
    app.execute_browser_control(command,actor=actor)
    assert app._session.state_revision>initial_revision
    app.execute_browser_control(host_command(sid,{**enabled,'interactiveBrowserEnabled':False}),actor=actor)
    replay=app.execute_browser_control(command,actor=actor)
    assert replay['capabilities']['interactiveBrowser']['available']['value']is False
    assert not factory.discovery.config.interactive_browser_enabled


@pytest.mark.parametrize('field',['available','publicOnly','networkIsolation','evidenceProfile',
    'riskAcknowledged','certified'])
def test_untrusted_json_flags_cannot_enable_capabilities(product,field):
    app,factory,sid=product()
    frames=[];adapter=JsonlApplicationAdapter(app,sid,frames.append)
    try:
        args=dict(controlledFetchEnabled=True,interactiveBrowserEnabled=True,
            acknowledgementVersion=BROWSER_RISK_ACKNOWLEDGEMENT_VERSION,**{field:True})
        adapter.handle(dict(id='untrusted-config',type='browser_control',command=host_command(sid,args),
            hostBrowserProof='0'*64,**{field:True}))
        assert frames[-1]['type']=='error'
        assert frames[-1]['code']=='BROWSER_HUMAN_CONTROL_DENIED'
        assert factory.discovery.config==WebV12FeatureConfiguration()
        assert not factory.browser_builds and not factory.services[0]._plans
    finally:
        adapter.close()


@pytest.mark.parametrize('field',['available','publicOnly','networkIsolation','evidenceProfile',
    'riskAcknowledged','certified'])
def test_authenticated_host_wire_still_rejects_unknown_authority_fields(product,field):
    app,factory,sid=product()
    frames=[];key='1a'*32;adapter=JsonlApplicationAdapter(app,sid,frames.append,host_approval_key=key)
    try:
        args=dict(controlledFetchEnabled=True,interactiveBrowserEnabled=True,
            acknowledgementVersion=BROWSER_RISK_ACKNOWLEDGEMENT_VERSION,**{field:True})
        command=host_command(sid,args)
        adapter.handle(dict(id='closed-config',type='browser_control',command=command,
            hostBrowserProof=approval_proof(key,command)))
        assert frames[-1]['type']=='error'
        assert factory.discovery.config==WebV12FeatureConfiguration()
        assert not factory.browser_builds
    finally:
        adapter.close()


def test_jsonl_authenticated_host_configuration_reaches_same_application_service(product):
    app,factory,sid=product()
    frames=[];key='2b'*32;adapter=JsonlApplicationAdapter(app,sid,frames.append,host_approval_key=key)
    try:
        command=host_command(sid,dict(controlledFetchEnabled=True,interactiveBrowserEnabled=False,
            acknowledgementVersion=BROWSER_RISK_ACKNOWLEDGEMENT_VERSION))
        adapter.handle(dict(id='exact-config',type='browser_control',command=command,
            hostBrowserProof=approval_proof(key,command)))
        assert frames[-1]['type']=='browser_control_result'
        assert factory.discovery.config.controlled_fetch_enabled is True
        assert factory.discovery.config.interactive_browser_enabled is False
        assert factory.discovery.config.risk_acknowledgement_version is None
        assert adapter.application is app
        assert not app._session.approval_gate.pending() and not factory.browser_builds
    finally:
        adapter.close()


def test_non_web_human_turn_is_not_broken_by_absent_web_target(product):
    app,factory,sid=product()
    receipt=app.handle(ApplicationCommand(new_command_id(),CommandKind.SUBMIT_USER_INPUT,
        {'content':'Responde hola, sin herramientas.'},session_id=sid))
    assert receipt.accepted
    assert app.wait_for_turn(receipt.created_ids['turnId'],5)
    assert not factory.browser_builds and not factory.services[0]._plans
    assert app.get_snapshot(sid).to_dict()['turns'][0]['status']=='completed'


def test_real_human_url_turn_binds_owner_task_without_creating_browser(product):
    app,factory,sid=product(True,False)
    receipt=app.handle(ApplicationCommand(new_command_id(),CommandKind.SUBMIT_USER_INPUT,
        {'content':'Lee https://public.test/a mediante HTTP.'},session_id=sid))
    assert receipt.accepted and app.wait_for_turn(receipt.created_ids['turnId'],5)
    service=factory.services[0];ticket=service._tasks[receipt.created_ids['turnId']]
    assert ticket.owner_id==sid
    assert ticket.approved_targets==('https://public.test/a',)
    assert not ticket.interaction_reasons
    assert not factory.browser_builds


def test_live_configuration_revocation_projects_false_without_cached_available(product):
    app,factory,sid=product(True,True)
    first=app.get_snapshot(sid).to_dict()['services']['webCapabilitiesV12']
    assert first['controlledFetch']['available']['value'] is True
    factory.discovery.config=replace(factory.discovery.config,controlled_fetch_enabled=False,
        interactive_browser_enabled=False,risk_acknowledgement_version=None)
    second=app.get_snapshot(sid).to_dict()['services']['webCapabilitiesV12']
    assert second['controlledFetch']['available']['value'] is False
    assert second['interactiveBrowser']['available']['value'] is False
    assert second['interactiveBrowser']['unavailableReason']=='FEATURE_DISABLED'


def cli_contract_client(app,sid,monkeypatch,*,tty=True,answers=()):
    """Controlled TTY/read double tests host wiring, not a native human gate."""
    monkeypatch.setattr(CliApplicationClient,'_human_tty',staticmethod(lambda:tty))
    output=[];responses=iter(answers)
    client=CliApplicationClient(app,sid,write=output.append,write_error=output.append,
        read=lambda _:next(responses))
    return client,output


def test_cli_web_status_projects_host_snapshot_without_acknowledgement_or_grant(product,monkeypatch):
    app,factory,sid=product()
    client,output=cli_contract_client(app,sid,monkeypatch,tty=False)
    try:
        client.web_v12('status')
        displayed=json.loads(''.join(output))
        assert displayed==app.get_snapshot(sid).services['webCapabilitiesV12']
        assert displayed['interactiveBrowser']['networkIsolation']['value']=='NOT_PROVIDED'
        assert displayed['interactiveBrowser']['unavailableReason']=='FEATURE_DISABLED'
        assert not factory.services[0]._plans and not factory.browser_builds
        assert not app._session.tool_runtime._issuer._issued
        assert not app._session.approval_gate.pending()
    finally:
        client.close()


def test_cli_browser_optin_cancellation_keeps_productive_configuration_disabled(product,monkeypatch):
    app,factory,sid=product()
    client,output=cli_contract_client(app,sid,monkeypatch,answers=['NO'])
    try:
        client.web_v12('browser on')
        assert 'no proporciona aislamiento exhaustivo de red' in ''.join(output)
        assert 'no aprueba efectos remotos' in ''.join(output)
        assert factory.discovery.config==WebV12FeatureConfiguration()
        assert not app._session.tool_runtime.registry.names
        assert not app._session.tool_runtime._issuer._issued
        assert not app._session.approval_gate.pending()
    finally:
        client.close()


def test_cli_browser_optin_uses_same_application_control_not_action_approval(product,monkeypatch):
    app,factory,sid=product()
    client,output=cli_contract_client(app,sid,monkeypatch,answers=['ACEPTO'])
    try:
        client.web_v12('browser on')
        assert client.application is app
        assert factory.discovery.config.interactive_browser_enabled is True
        assert factory.discovery.config.risk_acknowledgement_version==BROWSER_RISK_ACKNOWLEDGEMENT_VERSION
        assert json.loads(output[-1])['capabilities']==factory.services[0].snapshot().to_dict()
        assert 'browser_act' in app._session.tool_runtime.registry.names
        assert not app._session.tool_runtime._issuer._issued
        assert not app._session.approval_gate.pending()
        assert not factory.services[0]._plans and not factory.browser_builds
    finally:
        client.close()


def test_cli_non_tty_cannot_turn_text_acknowledgement_into_host_authority(product,monkeypatch):
    from local_cli.core.active_web_transfers import BrowserTransferError
    app,factory,sid=product()
    client,_=cli_contract_client(app,sid,monkeypatch,tty=False,answers=['ACEPTO'])
    try:
        with pytest.raises(BrowserTransferError,match='BROWSER_HUMAN_ACTOR_INVALID'):
            client.web_v12('browser on')
        assert factory.discovery.config==WebV12FeatureConfiguration()
        assert not app._session.tool_runtime._issuer._issued
        assert not factory.browser_builds
    finally:
        client.close()


def test_cli_fetch_configuration_has_no_browser_risk_prompt_or_fallback(product,monkeypatch):
    app,factory,sid=product()
    client,_=cli_contract_client(app,sid,monkeypatch)
    try:
        client.web_v12('fetch on')
        assert factory.discovery.config.controlled_fetch_enabled is True
        assert factory.discovery.config.interactive_browser_enabled is False
        assert factory.discovery.config.risk_acknowledgement_version is None
        assert app._session.tool_runtime.registry.names==('web_access',)
        assert not app._session.tool_runtime._issuer._issued
        assert not factory.browser_builds
        client.web_v12('fetch off')
        assert not app._session.tool_runtime.registry.names
        assert not factory.discovery.config.controlled_fetch_enabled
    finally:
        client.close()


def test_cli_web_slash_entrypoint_reaches_same_application_contract(product,monkeypatch):
    from types import SimpleNamespace
    from local_cli.cli import _handle_application_slash_command
    from local_cli.config import Config
    app,factory,sid=product()
    client,output=cli_contract_client(app,sid,monkeypatch)
    context=SimpleNamespace(config=Config(),current_mode='agent')
    try:
        assert _handle_application_slash_command('/web status',client,context)
        assert json.loads(output[-1])==factory.services[0].snapshot().to_dict()
        assert _handle_application_slash_command('/web fetch on',client,context)
        assert factory.discovery.config.controlled_fetch_enabled is True
        assert not app.get_snapshot(sid).turns
        assert not app._session.tool_runtime._issuer._issued
    finally:
        client.close()


def test_parent_delegation_strips_web_authority_after_host_ceiling_extension(product):
    from datetime import datetime,timedelta,timezone
    from local_cli.application.cancellation import CancellationController
    from local_cli.core.contracts import ExecutionContext,new_operation_id,new_turn_id,new_agent_id
    from local_cli.core.security import Capability,ControlClass,Permission,ResourceScope,ScopeKind
    app,factory,sid=product(True,True)
    service=factory.services[0];runtime=app._session.tool_runtime
    session_ref='bws_'+'ab'*16
    retained=Capability(Permission('application.tool.invoke'),ResourceScope(ScopeKind.SESSION,sid),
        ControlClass.APPLICATION_ENFORCED,{'tool':'ask_user'})
    web_caps=(
        Capability(Permission('network.fetch'),ResourceScope(ScopeKind.ORIGIN,'https://fixture.test'),
            ControlClass.APPLICATION_ENFORCED,{'capabilityId':'CONTROLLED_FETCH_V1_2','profile':'GET_HEAD_CONTRACT_ONLY'}),
        Capability(Permission('browser.read'),ResourceScope(ScopeKind.SESSION,session_ref),
            ControlClass.APPLICATION_ENFORCED,{'capabilityId':'INTERACTIVE_BROWSER_V1_2'}),
        Capability(Permission('browser.act'),ResourceScope(ScopeKind.SESSION,session_ref),
            ControlClass.APPLICATION_ENFORCED,{'capabilityId':'INTERACTIVE_BROWSER_V1_2'}),
    )
    service._add_caps((*web_caps,retained))
    assert all(cap in runtime._issuer.ceiling.capabilities for cap in web_caps)
    assert any(cap.restrictions.get('tool')=='web_access' for cap in runtime._issuer.ceiling.capabilities)
    context=ExecutionContext(workspace=app._session.workspace,cwd=app._session.workspace,
        environment=app._session.environment,session_id=sid,turn_id=new_turn_id(),operation_id=new_operation_id(),
        agent_id=new_agent_id(),cancellation_token=CancellationController(),
        deadline=datetime.now(timezone.utc)+timedelta(seconds=10),capabilities=app._session.capabilities,
        policy_revision=runtime.policy.revision)
    parent=runtime.delegation_for(context)
    assert retained in parent.request.capabilities
    assert not any(cap.permission.name.startswith('browser.') for cap in parent.request.capabilities)
    assert not any(cap.restrictions.get('capabilityId') in ('CONTROLLED_FETCH_V1_2','INTERACTIVE_BROWSER_V1_2')
        for cap in parent.request.capabilities)
    assert not any(cap.restrictions.get('tool')=='web_access' or
        str(cap.restrictions.get('tool','')).startswith('browser_') for cap in parent.request.capabilities)
    serialized=json.dumps([cap._binding() for cap in parent.request.capabilities])
    assert session_ref not in serialized
    assert 'CONTROLLED_FETCH_V1_2' not in serialized and 'INTERACTIVE_BROWSER_V1_2' not in serialized
    assert not factory.browser_builds
