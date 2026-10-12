"""Current Windows adapter regression on the observed hosted runtime.

Not B7 certification, no PUBLIC_ONLY/browser-network-isolation claim. The fixed
host navigation seam is called by this closed fixture, not by a model. Missing
SDK/runtime/guard is a failure; these tests never install a browser engine.
"""
from datetime import datetime,timedelta,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import importlib.util
import json
import os

from local_cli.application.cancellation import CancellationController
from local_cli.application.secrets import SecretRedactor
from local_cli.core.active_web import BrowserOutcomeState
from local_cli.core.active_web_lifecycle import BrowserOwner,BrowserLimits
from local_cli.core.contracts import new_session_id,new_turn_id,new_operation_id
from local_cli.infrastructure.active_web.productive_v12 import create_productive_browser

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('ci_existing_native_host_build',ROOT/'native/nova-browser-host/tests/conftest.py')
fixture_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture_module)
host_build=fixture_module.host_build


def test_current_windows_webview2_fixed_observation_guard_and_owned_cleanup(host_build,tmp_path):
    assert os.name=='nt','CURRENT_WINDOWS_NATIVE_CI requires real Windows; never skip.'
    output=Path(os.environ['NOVA_CI_OUTPUT_ROOT']).resolve()
    assert output.is_absolute()and not output.is_relative_to(ROOT)
    body=b'''<html><head><title>Owned CI fixture</title></head><body>
    <p id="ready">Waiting</p><button aria-label="Owned specimen">Specimen</button>
    <script>document.getElementById('ready').textContent='CI fixed observation ready';</script></body></html>'''
    events=[]
    class Fixture(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            events.append(self.path);self.send_response(200);self.send_header('Content-Type','text/html')
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    http=ThreadingHTTPServer(('127.0.0.1',0),Fixture)
    listener=Thread(target=http.serve_forever,daemon=True);listener.start()
    workspace=tmp_path/'workspace';workspace.mkdir()
    owner=BrowserOwner(new_session_id(),str(workspace.resolve()))
    composition=None
    turn=new_turn_id();client=None;receipt=None;health=None;observed=None;started=[]
    def deadline():return datetime.now(timezone.utc)+timedelta(seconds=20)
    try:
        composition=create_productive_browser(owner,dotnet_executable=host_build[0],host_assembly=host_build[1],
            owned_root=tmp_path,redactor=SecretRedactor(),browser_limits=BrowserLimits(90,20,20,15))
        composition.open(turn_id=turn,deadline=deadline())
        client=composition.port._client(composition.session.browser_session_ref)
        target=f'http://127.0.0.1:{http.server_port}/'
        report=composition.navigate_initial(target,turn_id=turn,operation_id=new_operation_id(),policy_revision=1,
            authority_digest='a'*64,expected_epoch=composition.session.browser_context_epoch,
            deadline=deadline(),cancellation=CancellationController(),started=lambda:started.append(True))
        assert report.outcome is BrowserOutcomeState.SUCCEEDED_OBSERVED and started==[True]
        observed=composition.observe(turn_id=turn,deadline=deadline())
        health=composition.health(deadline=deadline())
        assert 'CI fixed observation ready'in observed.visible_text_summary
        assert observed.interactive_elements and all(element.element_ref.startswith('bwe_')for element in observed.interactive_elements)
        assert health['runtime']['sdkVersion']=='1.0.4258.31'
        assert health['runtime']['runtimeVersion']and health['runtime']['architecture']=='X64'
        assert health['networkIsolation']=='NOT_PROVIDED'and health['controlClass']=='HOST_UNISOLATED'
        assert health['guard']['externalProtocolGuard']=='HOST_PRE_EFFECT_DENY'
        assert health['guard']['policy']=='DENY_ALL'and health['guard']['installations']and not health['guard']['auditGap']
        assert '/'in events
    finally:
        try:receipt=composition.close()if composition is not None else None
        finally:
            http.shutdown();http.server_close();listener.join(3)
        cleanup=bool(client and receipt and receipt.context_confirmed and client.cleanup_confirmed and
            client.process.poll()is not None and not client.udf.exists()and not listener.is_alive()and not composition.staging._root.exists())
        # Retain an inert audit receipt as diagnostics; no forensic erasure claim.
        journal=Path(str(client.udf)+'.guard-audit.jsonl')if client else None
        output.mkdir(parents=True,exist_ok=True)
        evidence=dict(schemaVersion=1,scope='CURRENT_WINDOWS_ADAPTER_REGRESSION',nativeCertification=False,
            B7Recertification=False,networkIsolation='NOT_PROVIDED',controlClass='HOST_UNISOLATED',
            sdk='1.0.4258.31',observedRuntime=health['runtime']if health else None,
            guardInstalled=bool(health),fixedObservationReturned=observed is not None,requestPaths=events,
            cleanup='CONFIRMED'if cleanup else'CLEANUP_UNCONFIRMED',listenerClosed=not listener.is_alive(),
            ownedUdfAbsent=bool(client and not client.udf.exists()),
            retainedAuditReceipt=bool(journal and journal.exists()),forensicErasure=False,
            engineDownloadedByTest=False,modelActionAuthorityClaim=False)
        (output/'windows_adapter_smoke.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
        assert cleanup,'Owned smoke runtime resources must close boundedly.'
