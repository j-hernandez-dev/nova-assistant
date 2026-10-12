"""Native Chromium channels with explicit synthetic network topology.

This is prerequisite characterization, not AW8 certification. Public fixture
DNS is simulated; admitted sockets are mapped ONLY to owned local endpoints.
No loopback authority is certified. No public website/LLM/global OS change.
"""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import json
import socket
from pathlib import Path
from threading import Event, Thread

from local_cli.application.browser_network import BrowserNetworkPolicy
from local_cli.application.cancellation import CancellationController
from local_cli.core.active_web import new_browser_session_ref,new_browser_page_ref
from local_cli.core.active_web_network import BrowserEgressError, BrowserBrokerLimits
from local_cli.core.active_web_lifecycle import BrowserLifecycleError
from local_cli.infrastructure.active_web.egress_broker import BrowserEgressBroker
from local_cli.infrastructure.active_web.playwright_adapter import PlaywrightBrowserAdapter,CHROMIUM_ARGS
from tests.active_web_v1.test_aw4_proxy import upstream
from tests.active_web_v1.test_aw4_network import ResolverDouble,endpoint
from tests.active_web_v1.test_aw8_productive_composition import VerifiedBackendDouble,application,invocation


def end():return datetime.now(timezone.utc)+timedelta(seconds=15)


class ControlledTopology:
    def __init__(self,servers,live):
        self.servers=servers;self.resolver=ResolverDouble()
        ports=tuple(dict.fromkeys(s.server_port for s in servers.values()))
        self.base=BrowserNetworkPolicy(self.resolver,validate_session=live.is_set,
            http_ports=tuple(dict.fromkeys((*ports,80))),connect_ports=tuple(dict.fromkeys((*ports,443))),
            allowed_hosts=(*tuple(servers),'127.0.0.1','::1'))
        self.http_ports=self.base.http_ports
    def validate_current(self):self.base.validate_current()
    def authorize(self,method,target,host,budget):
        plan=self.base.authorize(method,target,host,budget)
        server=self.servers[plan.host]
        if plan.port!=server.server_port:raise BrowserEgressError('BROWSER_EGRESS_PORT_POLICY_INVALID')
        return replace(plan,endpoint=endpoint('127.0.0.1',server.server_port))


def serve(handler):
    if handler.path=='/redirect':
        handler.send_response(302);handler.send_header('Location','/');handler.send_header('Content-Length','0');handler.end_headers();return
    if handler.path=='/':
        body=('''<!doctype html><title>Revision02 controlled source</title>
        <h1>Native channel fixture 824</h1><img src="/asset">
        <script>
        globalThis.probe={secure:isSecureContext,rtc:typeof RTCPeerConnection,
          transport:typeof WebTransport,ws:'ATTEMPTED',wss:'ATTEMPTED',sw:'ATTEMPTED'};
        try { let ws=new WebSocket('ws://localhost:PORT/ws');ws.onopen=()=>probe.ws='OPEN';ws.onclose=()=>probe.ws='CLOSED';ws.onerror=()=>probe.ws='ERROR'; } catch {probe.ws='DENIED';}
        try { let ws=new WebSocket('wss://localhost:PORT/wss');ws.onopen=()=>probe.wss='OPEN';ws.onclose=()=>probe.wss='CLOSED';ws.onerror=()=>probe.wss='ERROR'; } catch {probe.wss='DENIED';}
        if(navigator.serviceWorker) navigator.serviceWorker.register('/worker.js')
          .then(()=>probe.sw='REGISTERED').catch(()=>probe.sw='DENIED');
        setTimeout(()=>{document.querySelector('h1').textContent+=' '+JSON.stringify(probe);},250);
        </script>'''.replace('PORT',str(handler.server.server_port))).encode()
    elif handler.path=='/worker.js': body=b"self.addEventListener('fetch',()=>{});"
    else: body=b'synthetic asset'
    handler.send_response(200);handler.send_header('Content-Type','text/html' if handler.path=='/' else 'application/javascript')
    handler.send_header('Content-Length',str(len(body)));handler.end_headers();handler.wfile.write(body)


def test_native_revision02_productive_root_and_controlled_http_channels(tmp_path):
    with upstream(handler=serve) as http,upstream(handler=serve) as second,upstream(tls=True) as https:
        brokers=[]
        def factory(session,live):
            broker=BrowserEgressBroker(ControlledTopology({'localhost':http,'server.test':http,'other.test':second,'tls.test':https},live),
                limits=BrowserBrokerLimits(4,32768,65536,1048576,16))
            brokers.append(broker);return broker
        # Same shipping engine flags/context/channel controls, real engine.
        # Snapshot deliberately synthetic, never fed to native discovery.
        backend=VerifiedBackendDouble();backend.port=PlaywrightBrowserAdapter(factory,headful=True)
        port=backend.port
        app,_,_=application(tmp_path,backend)
        token=CancellationController();report=dict(schemaVersion=1,
            purpose='AW8 revision02 prerequisite characterization',topology='SIMULATED_PUBLIC_DNS_TO_OWNED_LOOPBACK',
            snapshot='VERIFIED_SYNTHETIC_WIRING_ONLY',finalAw8Campaign=False,modelInference=0,
            fixedArguments=list(CHROMIUM_ARGS),hostIsolation=False)
        try:
            inv=invocation(app,'browser_open',{'url':f'http://localhost:{http.server_port}/redirect'})
            app._active_web.actions.bind_turn(inv.context.turn_id,'Open the browser for the controlled source.')
            result=app._session.tool_runtime.execute(inv)
            assert result.status.value=='completed',result
            req=app._active_web.actions._plans[inv.operation_id].request
            session,page=req.browser_session_ref,req.page_ref
            environment=port.inspect_control_environment(session,page,deadline=end())
            assert environment['pageEnvironment']['secureContext'] is True
            assert environment['pageEnvironment']['rtc']=='undefined'
            assert environment['pageEnvironment']['webTransport']=='undefined'
            def inspect():
                async def read():
                    ctx,p=port._page(session,page)
                    await p.engine.wait_for_function('globalThis.probe && probe.ws !== "ATTEMPTED" && probe.wss !== "ATTEMPTED"',timeout=3000)
                    return dict(page=await p.engine.evaluate('globalThis.probe'),serviceWorkers=len(ctx.context.service_workers))
                return read()
            channels=port._call(inspect,end())
            report.update(environment=environment,channels=channels)
            assert channels['page']['ws']!='OPEN' and channels['page']['wss']!='OPEN'
            assert channels['serviceWorkers']==0 and channels['page']['sw']!='REGISTERED'
            assert not any(hit[1] in ('/ws','/wss','/worker.js') for hit in http.hits)
            assert any(hit[1]=='/redirect' for hit in http.hits) and any(hit[1]=='/asset' for hit in http.hits)
            port.navigate(session,page,f'http://other.test:{second.server_port}/',deadline=end(),cancellation=token)
            assert second.hits
            tls_error=None
            try:port.navigate(session,page,f'https://tls.test:{https.server_port}/',deadline=end(),cancellation=token)
            except BrowserLifecycleError as exc:tls_error=exc.code.value
            # CONNECT is real; a self-signed TLS fixture is NOT claimed to be
            # browser-trusted HTTPS. No --ignore-certificate-errors workaround.
            tls_records=[r for r in brokers[0].records()[0] if r['method']=='CONNECT' and r['upstreamConnected']]
            assert tls_records
            assert '--disable-quic' in CHROMIUM_ARGS
            assert '--force-webrtc-ip-handling-policy=disable_non_proxied_udp' in CHROMIUM_ARGS
            assert all(c[0]=='localhost' or c[0]=='server.test' or c[0]=='other.test' or c[0]=='tls.test'
                for c in brokers[0].admission.resolver.calls)
            report.update(productiveToolRuntime=True,environment=environment,channels=channels,
                httpHits=[h[1] for h in http.hits],secondOriginHits=[h[1] for h in second.hits],
                tls=dict(connectBrokered=True,trustedPage='NOT_DEMONSTRATED',error=tls_error),
                publicOnly='UNKNOWN',available='UNKNOWN',
                nativeSocketExclusivity='NOT_DEMONSTRATED',
                nativeUdpDnsBackground='NOT_DEMONSTRATED',
                pageOriginatedSchemePrevention='NOT_DEMONSTRATED')
            report['brokerRecords']=list(brokers[0].records()[0])
        finally:
            app.close_browser()
            assert port.shutdown(deadline=end())
            report['cleanupConfirmed']=True
            # Test artifacts ONLY, outside workspace via external --basetemp.
            (tmp_path/'native_channels.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
