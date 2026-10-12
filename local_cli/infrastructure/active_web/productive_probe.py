"""Bounded native prerequisite probe. Never a tool, grant or availability override.

Uses the shipping adapter, admission and broker, with no fixture endpoint
substitution. Negative probes are numeric private targets (no public sites).
No installer, personal profile, global firewall or browser configuration changes.
Incomplete engine-wide evidence deliberately cannot activate browser tools.
"""
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, replace
import socket
from threading import Event, Lock, Thread

from local_cli.application.browser_network import BrowserNetworkPolicy
from local_cli.application.cancellation import CancellationController
from local_cli.core.active_web import new_browser_session_ref, new_browser_page_ref
from local_cli.core.active_web_lifecycle import BrowserLifecycleError
from local_cli.core.active_web_network import BrowserBrokerLimits
from local_cli.core.contracts import BrowserCapabilitySnapshot, Observation
from local_cli.infrastructure.active_web.egress_broker import BrowserEgressBroker
from local_cli.infrastructure.active_web.playwright_adapter import PlaywrightBrowserAdapter
from local_cli.infrastructure.http_fetch import HttpFetchBroker


# All are denied by PUBLIC_ONLY; no DNS or third-party dependency. Each uses a
# normally admitted finite port so a PORT_DENIED alone is insufficient proof.
NEGATIVE_TARGETS = (
    ('http-loopback-v4', 'http://127.0.0.1/'),
    ('http-loopback-v6', 'http://[::1]/'),
    ('http-private', 'http://10.0.0.1/'),
    ('http-link-local', 'http://169.254.1.1/'),
    ('http-metadata', 'http://169.254.169.254/'),
    ('https-loopback', 'https://127.0.0.1/'),
    ('https-private', 'https://10.0.0.1/'),
    ('https-metadata', 'https://169.254.169.254/'),
)


@dataclass(frozen=True)
class ProductiveBrowserProbe:
    capabilities: BrowserCapabilitySnapshot
    evidence: dict


class _DirectCanary:
    """Probe-owned TCP listener, not a resolver/admission replacement.

    Accepts/closes only; never serves remote content or echoes caller data.
    Keeps listening through engine cleanup so late direct connects count too.
    """
    def __init__(self):
        self.socket=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.socket.bind(('127.0.0.1',0));self.socket.listen(8);self.socket.settimeout(.05)
        self.port=self.socket.getsockname()[1]
        self.stop,self.observed=Event(),Event()
        self.lock=Lock();self.connections=0
        def accept():
            while not self.stop.is_set():
                try:client,_=self.socket.accept()
                except socket.timeout:continue
                except OSError:return
                with self.lock:self.connections+=1
                client.close();self.observed.set()
        self.thread=Thread(target=accept,name='nova-probe-direct-canary',daemon=True)
        self.thread.start()
        with socket.create_connection(('127.0.0.1',self.port),timeout=1):pass
        if not self.observed.wait(1):
            self.close();raise ValueError('PROBE_CANARY_NOT_OBSERVABLE')
        self.baseline=self.connections
    def close(self):
        self.stop.set();self.socket.close();self.thread.join(1)
        return not self.thread.is_alive()


def probe_productive_browser(*, timeout_seconds=40, headful=True, backend=None):
    """Explicit host discovery; never called from a model or browser page.

    No boolean argument can assert publicOnly/available. The current report
    cannot prove redirects/subresources/DNS/UDP/schemes engine-wide. Returning
    UNKNOWN is mandatory until those separate obligations are demonstrated.
    """
    if (type(timeout_seconds) not in (int, float) or
            not 0 < timeout_seconds <= 120 or type(headful) is not bool):
        raise ValueError('INVALID_PRODUCTIVE_BROWSER_PROBE_LIMIT')
    deadline=datetime.now(timezone.utc)+timedelta(seconds=timeout_seconds)
    brokers=[]
    if backend is None:
        from local_cli.infrastructure.active_web.productive_backend import ProductiveBrowserBackend
        backend=ProductiveBrowserBackend()
    def factory(session, live):
        # Same productive backend/broker/engine configuration. Probe's finite
        # host scope is a reduction, not a substitute PUBLIC_ONLY authority.
        broker=backend.broker(session,live,
            allowed_hosts=('127.0.0.1','::1','10.0.0.1','169.254.1.1','169.254.169.254'))
        brokers.append(broker)
        return broker
    port=None
    canary=None
    snapshot=BrowserCapabilitySnapshot(control_class=Observation.known('HOST_UNISOLATED'))
    evidence=dict(schemaVersion=1,purpose='AW8 prerequisite remediation',
        productiveAdapter='PlaywrightBrowserAdapter',productiveAdmission='BrowserNetworkPolicy',
        productiveBroker='BrowserEgressBroker',endpointSubstitution=False,
        finalAw8Campaign=False,modelInference=0,negativeTargets=[],
        exclusiveEgress='NOT_DEMONSTRATED',availabilityOverride=False)
    try:
        port=PlaywrightBrowserAdapter(factory,headful=headful)
        session,page=new_browser_session_ref(),new_browser_page_ref()
        cancellation=CancellationController()
        port.create_context(session,deadline=deadline,cancellation=cancellation)
        port.create_page(session,page,deadline=deadline,cancellation=cancellation)
        snapshot=port.capabilities(session,deadline=deadline)
        evidence['composition']=port.inspect_control_environment(session,page,deadline=deadline)
        for name,url in NEGATIVE_TARGETS:
            before=len(brokers[0].records()[0])
            error=None
            attempt_deadline=min(deadline,datetime.now(timezone.utc)+timedelta(seconds=4))
            try:port.navigate(session,page,url,deadline=attempt_deadline,cancellation=cancellation)
            except BrowserLifecycleError as exc:error=exc.code.value
            records=brokers[0].records()[0][before:]
            # HTTP 403 can be an ordinary successful page load; its body is NOT
            # evidence of action success. Inspect host broker evidence instead.
            deny=any(r['errorCode']=='BROWSER_EGRESS_DESTINATION_DENIED' for r in records)
            connected=any(r['upstreamConnected'] for r in records)
            evidence['negativeTargets'].append(dict(id=name,transportError=error,
                brokerDestinationDenied=deny,upstreamConnected=connected,
                result='PASS' if deny and not connected else 'UNKNOWN'))
        evidence['unprovenObligations']=[
            'positive admitted HTTP/HTTPS composition and redirects/subresources',
            'fresh browser command-line/engine-wide DNS mediation evidence',
            'WS/WSS and service-worker negative engine probes in secure context',
            'QUIC/direct UDP/WebRTC engine-wide negative evidence',
            'proxy failure with direct UDP canary and non-loopback direct TCP coverage',
            'internal/file/javascript/data/custom scheme negative engine evidence',
            'complete native exclusive proof for unrestricted productive PUBLIC_ONLY scope',
        ]
        # Explicit diagnostic fault, not an auto-fallback, retry or product
        # mode. Listener is observed reachable by the host before browser IO.
        canary=_DirectCanary()
        evidence['brokerFaultCleanupConfirmed']=brokers[0].close(timeout_seconds=1).confirmed
        attempts=[]
        for scheme in ('http','https'):
            failed=False
            try:port.navigate(session,page,scheme+'://127.0.0.1:'+str(canary.port)+'/',
                deadline=min(deadline,datetime.now(timezone.utc)+timedelta(seconds=4)),cancellation=cancellation)
            except BrowserLifecycleError:failed=True
            attempts.append(dict(scheme=scheme,transportFailed=failed))
        evidence['directFallback']=dict(hostPositiveControl=canary.baseline>=1,
            brokerStopped=True,attempts=attempts,scope='owned loopback TCP HTTP/HTTPS canary only')
    except Exception as exc:
        # Fixed classification only: never publish arbitrary backend messages,
        # profiles, proxy credentials or page bodies as diagnostics.
        evidence['probeError']=('BROWSER_PORT_FAILURE' if isinstance(exc,BrowserLifecycleError)
                                else 'PRODUCTIVE_PROBE_FAILED')
    finally:
        cleanup=False
        if port is not None:
            try:cleanup=port.shutdown(deadline=datetime.now(timezone.utc)+timedelta(seconds=10))
            except Exception:evidence['cleanupError']='BROWSER_CLEANUP_UNCONFIRMED'
        evidence['cleanupConfirmed']=cleanup
        evidence['brokerRecords']=[dict(r) for b in brokers for r in b.records()[0]]
        evidence['brokerRecordsDropped']=sum(b.records()[1] for b in brokers)
        evidence['probeHostScope']='numeric negative canaries only; tighter than general PUBLIC_ONLY'
        evidence['noUpstreamConnections']=not any(r['upstreamConnected'] for r in evidence['brokerRecords'])
        if canary is not None:
            observed=canary.connections-canary.baseline
            canary_cleanup=canary.close()
            evidence.setdefault('directFallback',{}).update(browserConnections=observed,
                canaryCleanupConfirmed=canary_cleanup,
                result=('PASS' if not observed and canary_cleanup and cleanup and
                    all(a['transportFailed'] for a in evidence.get('directFallback',{}).get('attempts',[]))
                    and len(evidence.get('directFallback',{}).get('attempts',[]))==2 else 'FAIL'))
        # An incomplete or failed probe never publishes an earlier success.
        if evidence.get('probeError') or not cleanup:
            snapshot=BrowserCapabilitySnapshot(network_broker=Observation.known(False),
                available=Observation.known(False),control_class=Observation.known('HOST_UNISOLATED'))
    evidence['capabilities']=snapshot.to_dict()
    if not evidence.get('probeError') and cleanup:
        # Individual socket/page checks cannot certify the unproven surfaces.
        snapshot=replace(snapshot,
            public_only=Observation.unknown('exclusive productive egress obligations incomplete'),
            available=Observation.unknown('exclusive productive egress obligations incomplete'))
        evidence['capabilities']=snapshot.to_dict()
    return ProductiveBrowserProbe(snapshot,evidence)
