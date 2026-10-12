"""B7 actual JSONL/server bootstrap -> AgentLoop -> frozen HTTPS Fetch profile.

Only model proposal production is scripted. Owned DNS packets, numeric TCP,
standard TLS verification, HTTP framing and Policy/Grant dispatch remain real.
The exact fixture CA is trusted only in this process; no productive exception.
"""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import os
import socket
import ssl
import time

from local_cli.application.providers import ProviderManager
from local_cli.application.rag import RAGService
from local_cli.application.web_product_v12 import WebProductV12
from local_cli.bootstrap_server import create_server_application
from local_cli.bootstrap_web_v12 import WebV12Factory,CANDIDATE
from local_cli.config import Config
from local_cli.core.contracts import ToolStatus,new_command_id
from local_cli.core.network import NetworkEndpoint
from local_cli.core.web_capabilities_v12 import CF,FETCH_EVIDENCE_PROFILE,BROWSER_RISK_ACKNOWLEDGEMENT_VERSION
from local_cli.infrastructure.controlled_fetch_dns import ProcessScopedDNSResolver
from local_cli.infrastructure.controlled_fetch_transport import RealControlledFetchTransport
from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit
from local_cli.interfaces.approval_proof import approval_proof
from local_cli.interfaces.jsonl_application import JsonlApplicationAdapter
from tests.test_nova_core_phase4_session import ScriptedProvider
from tests.controlled_fetch_v12_b6.test_productive_fetch import native_fetch_environment

ROOT=Path(__file__).resolve().parents[2]


def test_actual_server_jsonl_agentloop_https_read_frozen_fetch_profile(native_fetch_environment,tmp_path,monkeypatch):
    import local_cli.bootstrap_server as server_root
    import local_cli.bootstrap_web_v12 as web_root
    environment=native_fetch_environment
    target='https://cf-public.test/b7-server-jsonl-agentloop'
    arguments=dict(url=target,method='GET',resultMode='TEXT',requiresInteraction=False,reason='')
    provider=ScriptedProvider([dict(role='assistant',content='',tool_calls=[
        dict(function=dict(name='web_access',arguments=arguments))]),'B7 JSONL HTTP retrieval observed.'])
    provider.name='b7-scripted'
    workspace=tmp_path/'workspace';workspace.mkdir()
    config=Config();config.state_dir=str(tmp_path/'state');config.model='b7-server-scripted'
    config.num_ctx=32768
    dns=[];transport=[];factories=[]
    resolver=ProcessScopedDNSResolver(NetworkEndpoint('127.0.0.1',socket.AF_INET,environment.dns.port),observe=dns.append)
    tls=ssl.create_default_context(cafile=str(environment.cert))
    assert tls.verify_mode==ssl.CERT_REQUIRED and tls.check_hostname
    def owned_factory(state_dir):
        # Frozen productive profiles load from the trusted installed candidate.
        # Only actual owned DNS endpoint and exact fixture TLS trust are injected.
        factory=WebV12Factory(state_dir,resolver=resolver,tls_context=tls,transport_observer=transport.append)
        factories.append(factory)
        return factory
    monkeypatch.setattr(web_root,'web_v12_factory',owned_factory)
    store=JsonlSecurityAudit(tmp_path/'audit',workspace=workspace)
    monkeypatch.setattr(server_root,'create_security_audit',lambda _:store)
    monkeypatch.setattr(server_root,'memory_factory',lambda *args,**kwargs:None)
    monkeypatch.setattr(server_root,'knowledge_factory',lambda *args,**kwargs:None)
    frames=[];key='4d'*32
    server=SimpleNamespace(_cwd=workspace,_config=config,_provider=provider,
        _provider_manager=ProviderManager(provider,config.model),_tools=[],
        _messages=[{'role':'system','content':'Nova B7 actual server root fixture. Use the exact registered tool.'}],
        _skills_loader=None,_tool_cache=None,_token_tracker=None,_conversation_store=None,
        _rag_service=RAGService(None),_sub_agent_runner=None,_auxiliary_services=None,
        _environment={},_approval_host_key=key,_sync_provider_projection=lambda:None)
    before_dns=len(dns);before_transport=len(transport);before_https=len(environment.https.events)
    before_sockets=len(environment.socket_attempts);before_private=len(environment.private.connections)
    try:
        create_server_application(server,send=frames.append)
        adapter=server._app_adapter;app=server._application;sid=adapter.session_id
        assert type(adapter)is JsonlApplicationAdapter and adapter.application is app
        assert type(app._web_v12)is WebProductV12
        assert app._web_v12_factory is factories[0]and factories[0].fetch_profile.evidence_profile==FETCH_EVIDENCE_PROFILE
        command=dict(commandId=new_command_id(),sessionId=sid,name='configure_web_v12',arguments=dict(
            controlledFetchEnabled=True,interactiveBrowserEnabled=False,
            acknowledgementVersion=BROWSER_RISK_ACKNOWLEDGEMENT_VERSION))
        adapter.handle(dict(id='b7-server-config',type='browser_control',command=command,
            hostBrowserProof=approval_proof(key,command)))
        configured=frames[-1]
        assert configured['type']=='browser_control_result'
        assert configured['data']['capabilities']['controlledFetch']['available']['value']is True
        assert configured['data']['capabilities']['interactiveBrowser']['available']['value']is False
        adapter.handle(dict(id='b7-server-read',type='chat',content='Lee '+target+' mediante recuperación HTTP controlada.'))
        assert app._session.turns,'Actual JSONL chat must create a real Application turn.'
        turn_id=app._session.turns[-1].turn_id
        assert app.wait_for_turn(turn_id,20)
        time.sleep(.02)
        adapter.handle(dict(id='b7-server-snapshot',type='get_snapshot',sessionId=sid))
        snapshot=frames[-1]['data']
        assert frames[-1]['type']=='snapshot'and snapshot==app.get_snapshot(sid).to_dict()
        turn=next(item for item in snapshot['turns']if item['turnId']==turn_id)
        assert turn['status']=='completed'
        results=[result for _,result in app._session.tool_runtime._outcomes.values()
            if result.metadata.get('capabilityId')==CF]
        assert len(results)==1 and results[0].status is ToolStatus.COMPLETED
        body=json.loads(results[0].stdout)
        assert body['capabilityId']==CF and body['outcome']=='SUCCEEDED_OBSERVED'
        observed_transport=transport[before_transport:];events=environment.https.events[before_https:]
        attempts=environment.socket_attempts[before_sockets:]
        assert len(observed_transport)==len(events)==len(attempts)==1
        assert observed_transport[0]['admittedEndpoint']==observed_transport[0]['connectedEndpoint']==[environment.address,443]
        assert observed_transport[0]['httpRequestBytesSent']>0 and observed_transport[0]['dnsAnswers']
        assert events[0]['method']=='GET'and events[0]['host']=='cf-public.test'and events[0]['version']=='HTTP/1.1'
        assert events[0]['acceptEncoding']=='identity'and events[0]['connection']=='close'
        assert not events[0]['forbiddenHeadersPresent']
        assert environment.https.snis[-1]=='cf-public.test'
        assert len(environment.private.connections)-before_private==0
        assert app._web_v12.browser is None
        operation=body['operationId'];plan=app._web_v12._plans[operation]
        assert type(plan['service'].transport)is RealControlledFetchTransport
        assert app._session.tool_runtime._web_v12 is app._web_v12
        receipts=[]
        for path in (Path(config.state_dir)/'web_v12').glob('*.receipts.jsonl'):
            receipts.extend(json.loads(line)for line in path.read_text(encoding='utf-8').splitlines())
        relevant=[item for item in receipts if item['operationId']==operation]
        assert [item['outcome']for item in relevant]==['STARTED','SUCCEEDED_OBSERVED']
        caps=snapshot['services']['webCapabilitiesV12']
        assert caps['controlledFetch']['evidenceProfile']['value']==FETCH_EVIDENCE_PROFILE
        assert caps['controlledFetch']['networkEgressControl']['value']=='ENFORCED'
        assert caps['controlledFetch']['publicOnly']['value']=='ENFORCED'
        assert caps['interactiveBrowser']['networkIsolation']['value']=='NOT_PROVIDED'
        output=Path(os.environ['NOVA_B5_TEST_OUTPUT']).resolve()/'b7_product_roots'
        assert output.is_absolute()and not output.is_relative_to(ROOT)
        output.mkdir(parents=True,exist_ok=True)
        evidence=dict(scope='ACTUAL_SERVER_JSONL_AGENTLOOP_CONTROLLED_FETCH_HTTPS',
            proposalProducer='SCRIPTED_PROVIDER_ONLY',operationId=operation,turnId=turn_id,
            productivePath=['bootstrap_server.create_server_application','JsonlApplicationAdapter.chat',
                'AgentSessionCoordinator','AgentLoop','LegacyToolAdapter','ToolRuntime','WebProductV12',
                'PolicyEngineV2','GrantIssuer','ControlledFetchService','RealControlledFetchTransport'],
            candidateManifestSha256=hashlib.sha256(CANDIDATE.read_bytes()).hexdigest(),
            profile=FETCH_EVIDENCE_PROFILE,outcome=body['outcome'],method='GET',
            payloadSha256=hashlib.sha256((body['payload']or'').encode()).hexdigest(),
            dns=dns[before_dns:],transport=observed_transport,serverEvents=events,
            nativeTCPConnectAttempts=attempts,forbiddenPrivateCanaryHits=0,browserCreated=False,
            receipts=[dict(operationId=item['operationId'],outcome=item['outcome'])for item in relevant],
            capabilitySnapshot=caps,exactFixtureProcessScopedTrust=True,globalCAStoreModified=False,
            browserNetworkIsolationClaim='NOT_PROVIDED',fullElectronGuiEndToEnd=False)
        (output/'server_jsonl_https.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    finally:
        if hasattr(server,'_app_adapter'):server._app_adapter.close()
        store.close()
