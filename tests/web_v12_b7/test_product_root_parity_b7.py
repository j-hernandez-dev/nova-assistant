"""B7 actual bootstrap-root and metadata parity; no browser-network claim.

Inference and unrelated Memory/Knowledge factories are isolated test inputs.
V1.2 discovery uses the frozen installed WebV12Factory, not a discovery double.
Default-off root tests are product contracts, not the native action E2E corpus.
"""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timedelta,timezone
import ast
import json
import shutil
import subprocess

import pytest

from local_cli.application.events import EventBufferConfig
from local_cli.application.providers import ProviderManager
from local_cli.application.rag import RAGService
from local_cli.application.session import AgentSessionCoordinator
from local_cli.application.tool_runtime import ToolRuntime
from local_cli.application.browser_actions import BrowserPolicyEngine
from local_cli.application.web_product_v12 import WebProductV12
from local_cli.bootstrap_cli import create_cli_application
from local_cli.bootstrap_server import create_server_application
from local_cli.bootstrap_web_v12 import WebV12Factory,CANDIDATE
from local_cli.config import Config
from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit
from local_cli.interfaces.cli_application import CliApplicationClient
from local_cli.interfaces.jsonl_application import JsonlApplicationAdapter
from local_cli.core.web_capabilities_v12 import BROWSER_RISK_ACKNOWLEDGEMENT_VERSION
from local_cli.core.contracts import new_command_id
from tests.test_nova_core_phase4_session import ScriptedProvider

ROOT=Path(__file__).resolve().parents[2]


@pytest.fixture
def actual_roots(tmp_path,monkeypatch):
    import local_cli.bootstrap_cli as cli_root
    import local_cli.bootstrap_server as server_root
    stores=[]
    def audit(workspace):
        store=JsonlSecurityAudit(tmp_path/f'audit-{len(stores)}',workspace=workspace)
        stores.append(store)
        return store
    for module in (cli_root,server_root):
        monkeypatch.setattr(module,'create_security_audit',audit)
        monkeypatch.setattr(module,'memory_factory',lambda *args,**kwargs:None)
        monkeypatch.setattr(module,'knowledge_factory',lambda *args,**kwargs:None)
    workspace=tmp_path/'workspace';workspace.mkdir()
    config=Config();config.state_dir=str(tmp_path/'owned-state');config.model='b7-scripted'
    provider_cli=ScriptedProvider(['root response'])
    manager_cli=ProviderManager(provider_cli,config.model)
    cli=create_cli_application(config=config,provider_manager=manager_cli,tools=[],workspace=workspace,
        base_messages=[{'role':'system','content':'B7 root contract.'}],persistence=None,
        rag_service=RAGService(None),write=lambda _:None,read=lambda _:'')
    frames=[];provider_server=ScriptedProvider(['root response'])
    server=SimpleNamespace(_cwd=workspace,_config=config,_provider=provider_server,
        _provider_manager=ProviderManager(provider_server,config.model),_tools=[],
        _messages=[{'role':'system','content':'B7 root contract.'}],_skills_loader=None,
        _tool_cache=None,_token_tracker=None,_conversation_store=None,_rag_service=RAGService(None),
        _sub_agent_runner=None,_auxiliary_services=None,_environment={},_approval_host_key='3c'*32,
        _sync_provider_projection=lambda:None)
    create_server_application(server,send=frames.append)
    yield dict(cli=cli,server=server,jsonl=server._app_adapter,frames=frames,workspace=workspace)
    cli.close();server._app_adapter.close()
    for store in stores:store.close()


def assert_same_composition(application):
    assert type(application)is AgentSessionCoordinator
    assert type(application._web_v12_factory)is WebV12Factory
    assert type(application._web_v12)is WebProductV12
    runtime=application._session.tool_runtime
    assert type(runtime)is ToolRuntime
    assert type(runtime.policy)is BrowserPolicyEngine
    assert runtime._web_v12 is application._web_v12
    assert runtime._approval_gate is application._session.approval_gate
    assert runtime._issuer is application._web_v12.runtime._issuer
    assert application._web_v12.browser is None
    assert application._web_v12_factory.browser_profile.evidence_profile.startswith('IB_B6_')
    assert CANDIDATE.is_file()


def test_actual_cli_server_and_desktop_backend_roots_share_composition_classes(actual_roots):
    cli=actual_roots['cli'];jsonl=actual_roots['jsonl'];server=actual_roots['server']
    assert type(cli)is CliApplicationClient
    assert type(jsonl)is JsonlApplicationAdapter
    assert jsonl.application is server._application
    for app in (cli.application,jsonl.application):assert_same_composition(app)
    # Separate processes/sessions have their own owners; the composition is shared.
    assert cli.session_id!=jsonl.session_id
    assert cli.application._web_v12.owner.agent_session_id==cli.session_id
    assert jsonl.application._web_v12.owner.agent_session_id==jsonl.session_id


def test_actual_roots_default_off_without_native_start_or_operation_authority(actual_roots):
    expected=None
    for client in (actual_roots['cli'],actual_roots['jsonl']):
        app=client.application;snapshot=app.get_snapshot(client.session_id).to_dict()
        capabilities=snapshot['services']['webCapabilitiesV12']
        assert capabilities['controlledFetch']['available']['value']is False
        assert capabilities['interactiveBrowser']['available']['value']is False
        assert capabilities['controlledFetch']['unavailableReason']=='FEATURE_DISABLED'
        assert capabilities['interactiveBrowser']['unavailableReason']=='FEATURE_DISABLED'
        assert capabilities['interactiveBrowser']['networkIsolation']['value']=='NOT_PROVIDED'
        assert capabilities['interactiveBrowser']['controlClass']['value']=='HOST_UNISOLATED'
        assert snapshot['services']['activeWeb']['capabilities']['available']['value']is not True
        assert not app._session.tool_runtime._issuer._issued
        assert not app._session.tool_runtime.registry.names
        assert not app._session.approval_gate.pending()
        assert app._web_v12.browser is None
        expected=expected or capabilities
        assert capabilities==expected


def test_actual_jsonl_root_projects_same_application_snapshot_and_denies_unsigned_enable(actual_roots):
    jsonl=actual_roots['jsonl'];frames=actual_roots['frames'];app=jsonl.application
    jsonl.handle(dict(type='get_snapshot',id='b7-root-snapshot',sessionId=jsonl.session_id))
    assert frames[-1]['data']==app.get_snapshot(jsonl.session_id).to_dict()
    command=dict(commandId=new_command_id(),sessionId=jsonl.session_id,name='configure_web_v12',arguments=dict(
        controlledFetchEnabled=True,interactiveBrowserEnabled=True,
        acknowledgementVersion=BROWSER_RISK_ACKNOWLEDGEMENT_VERSION))
    jsonl.handle(dict(type='browser_control',id='b7-denied',command=command,hostBrowserProof='0'*64,
        certified=True,available=True,riskAcknowledged=True))
    assert frames[-1]['type']=='error'and frames[-1]['code']=='BROWSER_HUMAN_CONTROL_DENIED'
    assert app._web_v12_factory.config.controlled_fetch_enabled is False
    assert app._web_v12_factory.config.interactive_browser_enabled is False
    assert app._web_v12.browser is None


def test_actual_root_snapshots_project_through_desktop_application_client(actual_roots,tmp_path):
    # No Electron GUI/native-dialog E2E inference: exact backend/client wire parity.
    node=shutil.which('node');assert node,'B7 Desktop contract parity needs installed Node.'
    folder=tmp_path/'desktop-root-parity';folder.mkdir()
    assert not folder.resolve().is_relative_to(ROOT)
    input_path=folder/'root_snapshots.json'
    snapshots=[client.application.get_snapshot(client.session_id).to_dict()
        for client in (actual_roots['cli'],actual_roots['jsonl'])]
    input_path.write_text(json.dumps(snapshots,ensure_ascii=False),encoding='utf-8')
    script=folder/'project.cjs'
    loader=ROOT/'desktop/tests/register_typescript.cjs'
    client=ROOT/'desktop/electron/application_client.ts'
    source='''const fs=require('node:fs'),assert=require('node:assert/strict');
require(process.argv[2]);const {DesktopApplicationClient}=require(process.argv[3]);
const snapshots=JSON.parse(fs.readFileSync(process.argv[4],'utf8'));const results=[];
for(const snapshot of snapshots){const sent=[];const client=new DesktopApplicationClient(f=>sent.push(f),()=>{});
client.receive({type:'ready',sessionId:snapshot.sessionId,tools:[]});
client.receive({type:'snapshot',id:sent.at(-1).id,data:snapshot});
assert.deepEqual(client.view.webCapabilitiesV12,snapshot.services.webCapabilitiesV12);
assert.deepEqual(client.view.webV12,snapshot.services.webV12);
assert.equal(client.view.webCapabilitiesV12.interactiveBrowser.networkIsolation.value,'NOT_PROVIDED');
assert.equal(sent.filter(f=>f.type==='application_command'||f.type==='browser_control').length,0);
results.push({sessionId:snapshot.sessionId,projection:'PASS',automaticEffects:0});}
console.log(JSON.stringify({scope:'ACTUAL_BOOTSTRAP_APPLICATION_DESKTOP_CLIENT_WIRE_PARITY',
guiEndToEnd:false,nativeCertification:false,results}));'''
    script.write_text(source,encoding='utf-8')
    result=subprocess.run([node,str(script),str(loader),str(client),str(input_path)],cwd=ROOT/'desktop',
        capture_output=True,text=True,timeout=30,check=False)
    assert result.returncode==0,result.stderr
    report=json.loads(result.stdout)
    assert len(report['results'])==2 and report['guiEndToEnd']is False
    (folder/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


def test_desktop_launch_uses_jsonl_backend_and_preserves_host_control_boundary():
    source=(ROOT/'desktop/electron/main.ts').read_text(encoding='utf-8')
    assert "spawn(pythonCmd, ['-m', 'local_cli', '--server']"in source
    assert "data.type === 'browser_control'"in source
    assert "env.NOVA_APPROVAL_HOST_KEY = approvalHostKey"in source
    assert "new DesktopApplicationClient(sendToPython"in source
    for root in ('local_cli/bootstrap_cli.py','local_cli/bootstrap_server.py'):
        tree=ast.parse((ROOT/root).read_text(encoding='utf-8'))
        calls=[node for node in ast.walk(tree)if isinstance(node,ast.Call)and
            isinstance(node.func,ast.Name)and node.func.id=='AgentSessionCoordinator']
        assert len(calls)==1
        binding=next(item.value for item in calls[0].keywords if item.arg=='web_v12_factory')
        assert isinstance(binding,ast.Call)and isinstance(binding.func,ast.Name)and binding.func.id=='web_v12_factory'


def test_active_web_core_legacy_claim_is_not_inferred_from_v12_availability():
    snapshot=(ROOT/'local_cli/core/web_capabilities_v12.py').read_text(encoding='utf-8')
    assert 'ACTIVE_WEB_CORE'not in snapshot
    assert 'networkIsolation=known(\'NOT_PROVIDED\')'in snapshot
    assert 'public_only'in snapshot
    current=json.loads((ROOT/'docs/active_web_v1_2/v12_b6_snapshot_productive_integration/manifest.json').read_text(encoding='utf-8'))
    # Preserve B6's historical stage; a future B7 overlay must never edit it.
    assert current['ACTIVE_WEB_CORE']=='NOT_READY'
    assert current['ACTIVE_WEB_V1_2_FINAL']=='NOT_CERTIFIED'
    assert current['RELEASE_APPROVED']is False
