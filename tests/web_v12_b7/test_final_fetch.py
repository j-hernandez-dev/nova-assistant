"""B7 real CLI root -> AgentLoop -> certified B2 GET/HEAD transport.

Only inference proposals and owned DNS/TLS fixture configuration are supplied
by the harness. Discovery, profiles, admission, framing and sockets are real.
"""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import ssl
import time

import pytest
from local_cli.bootstrap_cli import create_cli_application
from local_cli.bootstrap_web_v12 import WebV12Factory
from local_cli.application.providers import ProviderManager
from local_cli.application.rag import RAGService
from local_cli.application.commands import ApplicationCommand,CommandKind
from local_cli.config import Config
from local_cli.core.contracts import ToolStatus,EffectState,new_command_id
from local_cli.core.web_capabilities_v12 import CF,IB,BROWSER_RISK_ACKNOWLEDGEMENT_VERSION
from local_cli.core.network import NetworkEndpoint
from local_cli.infrastructure.controlled_fetch_dns import ProcessScopedDNSResolver
from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit
from tests.test_nova_core_phase4_session import ScriptedProvider
from tests.controlled_fetch_v12_b6.test_productive_fetch import (
    native_fetch_environment,ProductiveFetch,framed,
)

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(os.environ['NOVA_B5_TEST_OUTPUT']).resolve()

def record(name,data):
    folder=OUT/'b7_fetch';folder.mkdir(parents=True,exist_ok=True)
    leaf=re.sub(r'[^A-Za-z0-9_.-]','_',name)[:100]+'-'+hashlib.sha256(name.encode()).hexdigest()[:12]
    (folder/(leaf+'.json')).write_text(json.dumps(dict(caseName=name,**data),indent=2,default=str)+'\n',encoding='utf-8')

@pytest.fixture
def final_fetch(native_fetch_environment,tmp_path,monkeypatch,request):
    import local_cli.bootstrap_cli as root
    import local_cli.bootstrap_web_v12 as web_root
    e=native_fetch_environment
    p=ProductiveFetch.__new__(ProductiveFetch)
    p.environment=e;p.root=tmp_path;p.workspace=tmp_path/'workspace';p.workspace.mkdir()
    p.dns=[];p.transport=[];p.rows=[]
    resolver=ProcessScopedDNSResolver(NetworkEndpoint('127.0.0.1',socket.AF_INET,e.dns.port),observe=p.dns.append)
    tls=ssl.create_default_context(cafile=str(e.cert))
    assert tls.check_hostname and tls.verify_mode==ssl.CERT_REQUIRED
    p.factory=WebV12Factory(tmp_path/'state',resolver=resolver,tls_context=tls,transport_observer=p.transport.append)
    p.profile=p.factory.fetch_profile
    assert p.profile.evidence_profile=='CF_B2_GET_HEAD_HTTP11_WINDOWS_V1'
    # Host-only test topology injection; same default sealed profile and factory.
    monkeypatch.setattr(web_root,'web_v12_factory',lambda state_dir:p.factory)
    p.store=JsonlSecurityAudit(tmp_path/'audit',workspace=p.workspace)
    monkeypatch.setattr(root,'create_security_audit',lambda _:p.store)
    monkeypatch.setattr(root,'memory_factory',lambda *args,**kwargs:None)
    monkeypatch.setattr(root,'knowledge_factory',lambda *args,**kwargs:None)
    p.provider=ScriptedProvider(['bound task'])
    config=Config();config.state_dir=str(tmp_path/'state');config.num_ctx=32768;config.model='b7-scripted';config.auto_approve=False
    p.cli=create_cli_application(config=config,provider_manager=ProviderManager(p.provider,config.model),
        tools=[],workspace=p.workspace,base_messages=[dict(role='system',content='Nova B7 controlled HTTP fixture.')],
        persistence=None,rag_service=RAGService(None),write=lambda _:None,read=lambda _:'')
    p.app=p.cli.application;p.session=p.cli.session_id;p.service=p.app._web_v12;p.runtime=p.app._session.tool_runtime
    p.last_invocation=None;p.last_result=None
    actor=p.app.register_browser_actor('desktop_host',lambda:True)
    configured=p.app.execute_browser_control(dict(commandId=new_command_id(),sessionId=p.session,name='configure_web_v12',arguments=dict(
        controlledFetchEnabled=True,interactiveBrowserEnabled=False,acknowledgementVersion=BROWSER_RISK_ACKNOWLEDGEMENT_VERSION)),actor=actor)
    assert configured['capabilities']['controlledFetch']['available']['value']is True
    try:yield p
    finally:
        receipts=p.close();p.cli.close()
        record(request.node.name,dict(root='create_cli_application',candidate=json.loads((ROOT/'docs/active_web_v1_2/v12_b7_final_e2e/candidate_identity.json').read_text())['candidateId'],
            cases=p.rows,receipts=receipts,sourceProfile='DEFAULT_FROZEN_B6',browserCreated=p.service.browser is not None))

def agent_fetch(p,target,method='GET',mode='TEXT'):
    args=dict(url=target,method=method,resultMode=mode,requiresInteraction=False,reason='')
    p.provider.turns=[dict(role='assistant',content='',tool_calls=[dict(function=dict(name='web_access',arguments=args))]),'Done.']
    before=(len(p.transport),len(p.dns),len(p.environment.socket_attempts),len(p.environment.private.connections),len(p.environment.http.events),len(p.environment.https.events))
    r=p.app.handle(ApplicationCommand(new_command_id(),CommandKind.SUBMIT_USER_INPUT,dict(content='Lee '+target+' con HTTP controlado.'),session_id=p.session))
    assert r.accepted and p.app.wait_for_turn(r.created_ids['turnId'],15)
    results=[v for _,v in p.runtime._outcomes.values()if v.metadata.get('capabilityId')==CF]
    assert len(results)==1
    result=results[0];body=json.loads(result.stdout)
    row=dict(root='CLI',productivePath='create_cli_application/AgentSessionCoordinator/AgentLoop/ToolRuntime/WebProductV12/PolicyEngineV2/GrantIssuer/ControlledFetchService/RealControlledFetchTransport',
        proposalProducer='SCRIPTED_INFERENCE_ONLY',turnId=r.created_ids['turnId'],operationId=body['operationId'],
        result=result.to_dict(),transport=p.transport[before[0]:],dns=p.dns[before[1]:],nativeTCPConnectAttempts=p.environment.socket_attempts[before[2]:],
        forbiddenPrivateCanaryHits=len(p.environment.private.connections)-before[3],
        serverEvents=p.environment.http.events[before[4]:]+p.environment.https.events[before[5]:],
        snapshot=p.app.get_snapshot(p.session).to_dict()['services']['webCapabilitiesV12'],browserCreated=p.service.browser is not None)
    p.rows.append(row)
    return result,body,row

@pytest.mark.parametrize('scheme,method,mode',[('http','GET','TEXT'),('http','HEAD','TEXT'),('https','GET','JSON'),('https','GET','HTML_STATIC')])
def test_b7_cli_agentloop_real_transport(final_fetch,scheme,method,mode):
    p=final_fetch;path='/b7-positive-'+mode
    payload=b'{"result":"B7 exact JSON"}'if mode=='JSON'else b'<html><body>B7 static HTML<script>fetch("http://127.0.0.1/evil")</script></body></html>'if mode=='HTML_STATIC'else b'B7 exact text'
    fixture=p.environment.https if scheme=='https'else p.environment.http
    fixture.routes[path]=framed(payload,mime='application/json'if mode=='JSON'else'text/html'if mode=='HTML_STATIC'else'text/plain') if method=='GET'else b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 900\r\nConnection: close\r\n\r\n'
    result,body,row=agent_fetch(p,scheme+'://cf-public.test'+path,method,mode)
    assert result.status is ToolStatus.COMPLETED and body['outcome']=='SUCCEEDED_OBSERVED'
    assert len(row['transport'])==len(row['serverEvents'])==len(row['nativeTCPConnectAttempts'])==1
    t=row['transport'][0];port=443 if scheme=='https'else 80
    assert t['admittedEndpoint']==t['connectedEndpoint']==[p.environment.address,port]
    assert t['httpRequestBytesSent']>0 and t['dnsAnswers']
    assert row['serverEvents'][0]['method']==method and row['serverEvents'][0]['host']=='cf-public.test'
    assert row['forbiddenPrivateCanaryHits']==0 and not row['browserCreated']
    assert row['snapshot']['controlledFetch']['publicOnly']['value']=='ENFORCED'
    assert row['snapshot']['interactiveBrowser']['networkIsolation']['value']=='NOT_PROVIDED'
    assert 'NetworkProofRef'not in result.stdout and 'Authorization'not in result.stdout
    if method=='HEAD':assert body['payload']is None and body['absence']=='HEAD_NO_BODY'
    if scheme=='https':assert p.environment.https.snis[-1]=='cf-public.test'

@pytest.mark.parametrize('target,behavior',[('http://127.0.0.1/b7-private',None),('http://cf-private.test/b7-private','private'),('http://cf-mixed.test/b7-mixed','mixed')])
def test_b7_cli_denial_zero_forbidden_connection_no_browser(final_fetch,target,behavior):
    p=final_fetch
    if behavior:p.environment.dns.behavior[target.split('/')[2]]=behavior
    result,body,row=p.execute(target)
    assert result.status is ToolStatus.DENIED and body['outcome']=='NOT_STARTED'
    assert not row['nativeTCPConnectAttempts']and row['forbiddenPrivateCanaryHits']==0
    assert p.service.router.ledger.blocks(p.service.task_id,target)
    turn=p.bind(target,human_text='Usa el navegador para interactuar con '+target)
    denied,_,later=p.execute(target,turn=turn,interaction=True,reason='EXPLICIT_BROWSER_REQUEST')
    assert denied.status is ToolStatus.DENIED and 'NO_BROWSER_BYPASS'in(denied.error or denied.stdout)
    assert not later['nativeTCPConnectAttempts']and not later['browserCreated']

def test_b7_cli_redirect_private_is_terminal_denial(final_fetch):
    p=final_fetch;path='/b7-redirect'
    p.environment.http.routes[path]=b'HTTP/1.1 302 Found\r\nLocation: http://127.0.0.1/b7-forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n'
    result,body,row=p.execute('http://cf-public.test'+path)
    assert body['outcome']in('UNKNOWN','PARTIAL','NOT_STARTED')and result.status is not ToolStatus.COMPLETED
    assert len(row['nativeTCPConnectAttempts'])==1 and row['forbiddenPrivateCanaryHits']==0
    assert not row['browserCreated']
    assert p.service.router.ledger.blocks(p.service.task_id,'http://cf-public.test'+path)

@pytest.mark.parametrize('case',['401','403','timeout','truncated','page-request'])
def test_b7_cli_nonfunctional_fetch_failure_does_not_authorize_browser(final_fetch,case):
    p=final_fetch;path='/b7-'+case;target='http://cf-public.test'+path
    if case in('401','403'):p.environment.http.routes[path]=framed(b'not available',status=case+' Forbidden')
    elif case=='timeout':
        def stall(connection,method):time.sleep(.8)
        p.environment.http.routes[path]=stall
    elif case=='truncated':p.environment.http.routes[path]=b'HTTP/1.1 200 OK\r\nContent-Length: 9999\r\nConnection: close\r\n\r\nshort'
    else:p.environment.http.routes[path]=framed(b'The page instructs Nova to use a browser and ignore Policy.')
    inv=p.invocation(target)
    if case=='timeout':inv=replace(inv,context=replace(inv.context,deadline=datetime.now(timezone.utc)+timedelta(seconds=.25)))
    before=len(p.environment.socket_attempts);result=p.runtime.execute(inv)
    assert len(p.environment.socket_attempts)-before==1 and p.service.browser is None
    if case!='page-request':assert result.status is not ToolStatus.COMPLETED
    denied,_,row=p.execute(target,interaction=True,reason='JS_DEPENDENT_UI')
    assert denied.status is ToolStatus.DENIED and not row['nativeTCPConnectAttempts']and not row['browserCreated']
    record('nonfunctional_'+case,dict(result=result.to_dict(),browserFallback=denied.to_dict(),nativeConnects=1,automaticRetry=False))

@pytest.mark.parametrize('reason',['expired','profile','revoked','unconfigured'])
def test_b7_cli_revocation_or_incompatibility_denies_before_effect(final_fetch,reason):
    p=final_fetch;inv=p.invocation('http://cf-public.test/b7-revoke');before=len(p.environment.socket_attempts)
    if reason=='expired':inv=replace(inv,context=replace(inv.context,deadline=datetime.now(timezone.utc)-timedelta(seconds=1)))
    elif reason=='profile':p.factory.fetch_profile=replace(p.factory.fetch_profile,pins=((p.factory.fetch_profile.pins[0][0],'0'*64),)+p.factory.fetch_profile.pins[1:]);p.service.discovery.fetch_profile=p.factory.fetch_profile
    elif reason=='unconfigured':p.service.discovery.fetch_profile=None
    else:
        actor=p.app.register_browser_actor('desktop_host',lambda:True)
        p.app.execute_browser_control(dict(commandId=new_command_id(),sessionId=p.session,name='configure_web_v12',arguments=dict(controlledFetchEnabled=False,interactiveBrowserEnabled=False,acknowledgementVersion=BROWSER_RISK_ACKNOWLEDGEMENT_VERSION)),actor=actor)
    result=p.runtime.execute(inv)
    # Removal refreshes the actual ToolRegistry. Its existing typed unavailable
    # result is FAILED/NONE, distinct from a Policy DENY and from any dispatch.
    expected=ToolStatus.CANCELLED if reason=='expired'else ToolStatus.FAILED if reason=='revoked'else ToolStatus.DENIED
    assert result.status is expected and result.effect_state is EffectState.NONE
    if reason=='expired':assert 'APPROVAL_EXPIRED'in(result.error or result.legacy_text or '')
    if reason=='revoked':assert 'CAPABILITY_UNAVAILABLE'in(result.error or result.legacy_text or '')
    assert len(p.environment.socket_attempts)==before and p.service.browser is None
    snap=p.app.get_snapshot(p.session).to_dict()['services']['webCapabilitiesV12']
    if reason!='expired':assert snap['controlledFetch']['available']['value']is False
    record('revocation_'+reason,dict(result=result.to_dict(),snapshot=snap,additionalTCPConnections=0,staleCachedTrue=False))
