"""Prerequisite component contracts; NOT the final AW8 E2E campaign."""
from datetime import datetime,timedelta,timezone

import pytest

from local_cli.core.contracts import BrowserCapabilitySnapshot,Observation,CapabilityStatus
from local_cli.core.active_web_lifecycle import BrowserLifecycleError,BrowserLifecycleErrorCode
from local_cli.application.cancellation import CancellationController
from local_cli.infrastructure.active_web.playwright_adapter import CHROMIUM_ARGS
from local_cli.infrastructure.active_web import productive_probe as probe


class ProbePortDouble:
    # SDK double only. No fake endpoint resolver or fake native certification.
    def __init__(self,factory,*,headful):
        self.factory,self.headful,self.brokers=factory,headful,[]
    def create_context(self,session,**kwargs):
        from threading import Event
        live=Event();live.set()
        self.brokers.append(self.factory(session,live))
    def create_page(self,*args,**kwargs):pass
    def capabilities(self,*args,**kwargs):
        # Deliberate unsafe upstream claim: the complete probe must not merely
        # trust a coarse boolean. Partial proof must force UNKNOWN.
        return BrowserCapabilitySnapshot(available=Observation.known(True),
            public_only=Observation.known(True),network_broker=Observation.known(True),
            engine=Observation.known('PLAYWRIGHT_CHROMIUM'),engine_version=Observation.known('SDK-double'),
            browser_version=Observation.known('engine-double'),control_class=Observation.known('HOST_UNISOLATED'),
            platform=Observation.known('contract-double'),max_pages=Observation.known(3))
    def inspect_control_environment(self,*args,**kwargs):
        return dict(fixedArguments=list(CHROMIUM_ARGS),sdkDouble=True)
    def navigate(self,*args,**kwargs):
        raise BrowserLifecycleError(BrowserLifecycleErrorCode.PORT)
    def shutdown(self,**kwargs):
        return all(b.close(timeout_seconds=1).confirmed for b in self.brokers)


def test_productive_probe_never_promotes_partial_proof_to_availability(monkeypatch):
    monkeypatch.setattr(probe,'PlaywrightBrowserAdapter',ProbePortDouble)
    result=probe.probe_productive_browser()
    assert result.capabilities.available.status is CapabilityStatus.UNKNOWN
    assert result.capabilities.public_only.status is CapabilityStatus.UNKNOWN
    assert result.evidence['exclusiveEgress']=='NOT_DEMONSTRATED'
    assert result.evidence['unprovenObligations']
    assert result.evidence['directFallback']['hostPositiveControl'] is True
    assert result.evidence['directFallback']['browserConnections']==0
    assert result.evidence['directFallback']['result']=='PASS'
    assert len(result.evidence['negativeTargets'])==8
    assert all(r['result']=='UNKNOWN' for r in result.evidence['negativeTargets'])


def test_productive_probe_uses_real_admission_not_fixture_substitution(monkeypatch):
    seen=[]
    class Capture(ProbePortDouble):
        def create_context(self,*args,**kwargs):
            super().create_context(*args,**kwargs);seen.extend(self.brokers)
    monkeypatch.setattr(probe,'PlaywrightBrowserAdapter',Capture)
    result=probe.probe_productive_browser()
    assert result.evidence['endpointSubstitution'] is False
    assert type(seen[0].admission) is probe.BrowserNetworkPolicy
    assert type(seen[0].admission.resolver) is probe.HttpFetchBroker
    assert seen[0].admission.http_ports==(80,)
    assert seen[0].admission.connect_ports==(443,)


def test_productive_probe_failure_stays_fail_closed(monkeypatch):
    class Failure(ProbePortDouble):
        def create_page(self,*args,**kwargs):raise RuntimeError('private backend details')
    monkeypatch.setattr(probe,'PlaywrightBrowserAdapter',Failure)
    result=probe.probe_productive_browser()
    assert result.capabilities.available.value is False
    assert result.capabilities.public_only.status is CapabilityStatus.UNKNOWN
    assert result.evidence['probeError']=='PRODUCTIVE_PROBE_FAILED'
    assert 'private backend details' not in str(result.evidence)


def test_productive_probe_cleanup_failure_discards_prior_claim(monkeypatch):
    class Unconfirmed(ProbePortDouble):
        def shutdown(self,**kwargs):super().shutdown(**kwargs);return False
    monkeypatch.setattr(probe,'PlaywrightBrowserAdapter',Unconfirmed)
    result=probe.probe_productive_browser()
    assert result.capabilities.available.value is False
    assert result.evidence['cleanupConfirmed'] is False


@pytest.mark.parametrize('timeout',[0,-1,121,float('inf'),float('nan'),True,'40'])
def test_productive_probe_limits_do_not_start_engine(timeout,monkeypatch):
    calls=[]
    monkeypatch.setattr(probe,'PlaywrightBrowserAdapter',lambda *a,**k:calls.append(k))
    with pytest.raises(ValueError):probe.probe_productive_browser(timeout_seconds=timeout)
    assert not calls


def test_dns_proxy_hardening_is_process_local_not_presence_certification():
    assert '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1' in CHROMIUM_ARGS
    assert '--proxy-bypass-list=<-loopback>' in CHROMIUM_ARGS
    assert '--disable-quic' in CHROMIUM_ARGS
    assert not any('direct://' in a or 'ignore-certificate-errors' in a for a in CHROMIUM_ARGS)


def test_fixed_control_probe_accepts_no_caller_code_or_selector():
    import inspect
    from local_cli.infrastructure.active_web.playwright_adapter import PlaywrightBrowserAdapter
    assert list(inspect.signature(PlaywrightBrowserAdapter.inspect_control_environment).parameters)==[
        'self','session','page','deadline']


def test_probe_host_reduction_denies_public_background_before_dns():
    from local_cli.application.browser_network import BrowserNetworkPolicy
    from local_cli.core.network import FetchBudget,FetchLimits
    from local_cli.core.active_web_network import BrowserEgressError
    class NoDns:
        def resolve(self,*args):raise AssertionError('must deny before DNS')
    policy=BrowserNetworkPolicy(NoDns(),validate_session=lambda:True,allowed_hosts=('127.0.0.1',))
    budget=FetchBudget(FetchLimits(2,4096,0,1),CancellationController(),None)
    with pytest.raises(BrowserEgressError) as error:
        policy.authorize('CONNECT','background.invalid:443','background.invalid:443',budget)
    assert error.value.code=='BROWSER_EGRESS_SCOPE_DENIED'
    with pytest.raises(BrowserEgressError) as error:
        policy.authorize('GET','http://127.0.0.1/','127.0.0.1',budget)
    assert error.value.code=='BROWSER_EGRESS_DESTINATION_DENIED'


def test_empty_probe_host_scope_is_deny_all_not_unrestricted():
    from local_cli.application.browser_network import BrowserNetworkPolicy
    from local_cli.core.network import FetchBudget,FetchLimits
    from local_cli.core.active_web_network import BrowserEgressError
    policy=BrowserNetworkPolicy(object(),validate_session=lambda:True,allowed_hosts=())
    with pytest.raises(BrowserEgressError) as error:
        policy.authorize('GET','http://127.0.0.1/','127.0.0.1',FetchBudget(FetchLimits(2,4096,0,1),CancellationController(),None))
    assert error.value.code=='BROWSER_EGRESS_SCOPE_DENIED'


def test_native_productive_probe_negative_public_only_without_availability_override():
    result=probe.probe_productive_browser(headful=False)
    assert result.evidence['cleanupConfirmed'] is True
    assert result.capabilities.engine.value=='PLAYWRIGHT_CHROMIUM'
    assert result.capabilities.network_broker.value is True
    assert result.capabilities.public_only.status is CapabilityStatus.UNKNOWN
    assert result.capabilities.available.status is CapabilityStatus.UNKNOWN
    assert not any(r['upstreamConnected'] for r in result.evidence['brokerRecords'])
    assert result.evidence['brokerRecordsDropped']==0
    assert result.evidence['endpointSubstitution'] is False
    assert result.evidence['finalAw8Campaign'] is False
    assert result.evidence['modelInference']==0
    assert result.evidence['composition']['pageEnvironment']['rtc']=='undefined'
    assert result.evidence['unprovenObligations']
    assert result.evidence['directFallback']['hostPositiveControl'] is True
    assert result.evidence['directFallback']['browserConnections']==0
    assert result.evidence['directFallback']['result']=='PASS'
