"""Shared CLI/JSONL/Desktop product composition, disabled until human opt-in.

The frozen B6 candidate manifest is a trusted installation artifact, never a
frontend/model capability declaration. Missing/incompatible artifacts fail closed.
"""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import ssl
from threading import RLock

from local_cli.application.web_product_v12 import WebProductV12
from local_cli.application.browser_actions import BrowserPolicyEngine
from local_cli.core.contracts import new_turn_id
from local_cli.core.controlled_fetch import ControlledFetchLimits
from local_cli.core.web_capabilities_v12 import CF, IB, WebUnavailableReason as R
from local_cli.infrastructure.web_discovery_v12 import FileIdentityProfile, HostProbeResult, WebV12Discovery, WebV12FeatureConfiguration
from local_cli.infrastructure.controlled_fetch_transport import RealControlledFetchTransport
from local_cli.infrastructure.http_fetch import HttpFetchBroker
from local_cli.infrastructure.active_web.productive_v12 import create_productive_browser, ProductiveWebView2Adapter

ROOT=Path(__file__).resolve().parents[1]
CANDIDATE=ROOT/'docs/active_web_v1_2/v12_b7_final_e2e/product_candidate.json'
POLICY_FAMILY='PolicyEngineV2/1'
CF_COMPONENTS=('ToolRuntime','PolicyEngineV2','GrantIssuer','DurableReceipt','RealControlledFetchTransport','S5Admission')
IB_COMPONENTS=('ToolRuntime','PolicyEngineV2','GrantIssuer','ApprovalGate','PrivateHostV6','ExternalProtocolGuard','B4Actions','B5Transfers','B5Takeover','B5Secrets')
FETCH_CONFIG=dict(methods=['GET','HEAD'],modes=['TEXT','HTML_STATIC','JSON'],limits=ControlledFetchLimits().to_dict(),
    httpVersion='1.1',automaticRetry=False,cookieJar=False,browserSessionImport=False,ambientProxy=False)
BROWSER_CONFIG=dict(protocolVersion=6,adapter='WEBVIEW2',networkIsolation='NOT_PROVIDED',controlClass='HOST_UNISOLATED',
    externalProtocol='DENY_ALL',maxPages=3,maxActionsPerTurn=25,maxNavigationsPerTurn=10,formSubmit=False)
def config_digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def fetch_runtime():return tuple(sorted(dict(python=platform.python_version(),openssl=ssl.OPENSSL_VERSION,
    architecture=platform.machine(),os=platform.system()).items()))


class WebV12Factory:
    productive=True
    def __init__(self,state_dir,*,fetch_profile=None,browser_profile=None,browser_builder=None,
                 resolver=None,tls_context=None,transport_observer=None,repo_root=ROOT,candidate_path=CANDIDATE):
        self.state_dir=Path(state_dir);self.repo_root=Path(repo_root)
        self.fetch_profile,self.browser_profile=fetch_profile,browser_profile
        self.browser_builder=browser_builder;self.resolver=resolver or HttpFetchBroker()
        self.tls_context=tls_context;self.transport_observer=transport_observer
        self.config=WebV12FeatureConfiguration();self._lock=RLock();self._load_error=None
        if fetch_profile is None and browser_profile is None:
            try:self._load_candidate(Path(candidate_path))
            except Exception:self._load_error='EVIDENCE_NOT_CONFIGURED'

    def _load_candidate(self,path):
        data=json.loads(path.read_text(encoding='utf-8'))
        if type(data)is not dict or set(data)!={'schema','fetch','browser','dotnetExecutable','hostAssembly'} or data['schema']!='WEB_V12_B6_CANDIDATE_1':raise ValueError('INVALID_PRODUCT_CANDIDATE')
        def profile(v):
            if type(v)is not dict or set(v)!={'capabilityId','evidenceProfile','pins','runtime','configurationDigest','policyRevisionFamily','schemaVersion','protocolVersion','requiredComponents'}:raise ValueError('INVALID_PRODUCT_CANDIDATE')
            return FileIdentityProfile(v['capabilityId'],v['evidenceProfile'],tuple(tuple(p)for p in v['pins']),tuple(tuple(p)for p in v['runtime']),
                v['configurationDigest'],v['policyRevisionFamily'],v['schemaVersion'],v['protocolVersion'],tuple(v['requiredComponents']))
        self.fetch_profile=profile(data['fetch']);self.browser_profile=profile(data['browser'])
        dotnet=Path(data['dotnetExecutable']);assembly=Path(data['hostAssembly'])
        if not assembly.is_absolute():assembly=self.repo_root/assembly
        # Binary and executable must be included in the trusted pinned identity.
        pins=dict(self.browser_profile.pins)
        if str(dotnet)not in pins or not any((self.repo_root/Path(k)if not Path(k).is_absolute()else Path(k))==assembly for k in pins):raise ValueError('UNPINNED_HOST_BINARY')
        self.browser_builder=lambda owner,redactor:create_productive_browser(owner,dotnet_executable=dotnet,
            host_assembly=assembly,owned_root=self._owned_root(),redactor=redactor)

    def _owned_root(self):
        # Staging is owned, outside the UDF; no historical profile maintenance.
        root=self.state_dir/'web_v12';root.mkdir(parents=True,exist_ok=True);return root.resolve()

    def configure(self,fetch,browser,ack):
        with self._lock:self.config=WebV12FeatureConfiguration(fetch,browser,ack)

    def __call__(self,owner,redactor,publish):
        slot={};journal_lock=RLock();records=[0]
        def record(value):
            data=value.to_dict()if hasattr(value,'to_dict')else value
            body=json.dumps(redactor.value(data),ensure_ascii=False,separators=(',',':')).encode()+b'\n'
            with journal_lock:
                if records[0]>=256 or len(body)>131072:raise ValueError('WEB_RECEIPT_LIMIT')
                path=self._owned_root()/(owner.agent_session_id+'.receipts.jsonl')
                with path.open('ab')as stream:stream.write(body);stream.flush();os.fsync(stream.fileno())
                records[0]+=1
        def components():
            service=slot['service'];rt=service.runtime
            return not service._closed and rt is not None and rt._issuer is not None and rt._security_audit is not None and isinstance(rt.policy,BrowserPolicyEngine)
        def fetch_probe():
            okay=components()and type(self.resolver)is HttpFetchBroker or components()and self.resolver is not None
            transport=RealControlledFetchTransport(validate_plan=lambda p,phase:None,tls_context=self.tls_context)
            return HostProbeResult(fetch_runtime(),config_digest(FETCH_CONFIG),POLICY_FAMILY,1,'HTTP11_GET_HEAD_1',
                CF_COMPONENTS if okay and type(transport)is RealControlledFetchTransport else (),None if okay else R.COMPOSITION_INCOMPLETE)
        def browser_probe():
            service=slot['service']
            if not components()or service.runtime._approval_gate is None:return HostProbeResult((),config_digest(BROWSER_CONFIG),POLICY_FAMILY,1,'6',(),R.COMPOSITION_INCOMPLETE)
            if self.browser_builder is None:return HostProbeResult((),config_digest(BROWSER_CONFIG),POLICY_FAMILY,1,'6',(),R.BROWSER_HOST_UNAVAILABLE)
            browser=service.ensure_browser()
            if browser.session is None:browser.open(turn_id=new_turn_id(),deadline=datetime.now(timezone.utc)+timedelta(seconds=15))
            health=browser.health(deadline=datetime.now(timezone.utc)+timedelta(seconds=5));meta=health['runtime']
            runtime=tuple(sorted((k,str(meta[k]))for k in ('engine','sdkVersion','runtimeVersion','architecture')))
            valid=(type(browser.port)is ProductiveWebView2Adapter and browser.actions is service.runtime._browser_actions and
                service.runtime.policy.actions is browser.actions and browser.actions.transfers is browser.transfers and
                browser.actions.takeovers is browser.takeovers and browser.port.client_type.wire is __import__(
                    'local_cli.infrastructure.active_web.productive_ipc_v12',fromlist=['envelope']))
            return HostProbeResult(runtime,config_digest(BROWSER_CONFIG),POLICY_FAMILY,1,'6',IB_COMPONENTS if valid else (),
                None if valid else R.COMPOSITION_INCOMPLETE)
        discovery=WebV12Discovery(self.repo_root,fetch_profile=self.fetch_profile,browser_profile=self.browser_profile,
            fetch_probe=fetch_probe,browser_probe=browser_probe,configuration=lambda:self.config)
        service=WebProductV12(owner,discovery=discovery,configure=self.configure,browser_builder=self.browser_builder,
            resolver=self.resolver,record=record,redactor=redactor,tls_context=self.tls_context,transport_observer=self.transport_observer)
        slot['service']=service;return service


def web_v12_factory(state_dir):return WebV12Factory(state_dir)
