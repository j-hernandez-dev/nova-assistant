"""One engine/broker configuration for discovery and productive runtime.

An installed engine or the fixed Chromium flags are NOT exclusive-egress
proof. Until engine-wide host observation is complete, no availability claim
can be issued. No external evidence file/boolean can bypass this discovery.
"""
from datetime import datetime, timezone
from importlib.metadata import version, PackageNotFoundError
from dataclasses import replace
import os
from threading import RLock

from local_cli.application.browser_network import BrowserNetworkPolicy
from local_cli.core.active_web_network import BrowserBrokerLimits
from local_cli.core.contracts import BrowserCapabilitySnapshot, Observation, CapabilityStatus
from local_cli.infrastructure.active_web.egress_broker import BrowserEgressBroker
from local_cli.infrastructure.active_web.playwright_adapter import PlaywrightBrowserAdapter, CHROMIUM_ARGS
from local_cli.infrastructure.active_web.productive_probe import ProductiveBrowserProbe, probe_productive_browser
from local_cli.infrastructure.http_fetch import HttpFetchBroker


EGRESS_OBLIGATIONS = ('http', 'https', 'redirects', 'subresources', 'newOrigins',
    'privateDestinationsDenied',
    'brokerDns', 'noDirectDns', 'webSocketsDisabled', 'serviceWorkersDisabled',
    'webRtcDisabled', 'quicUdpDisabled', 'proxyBypassDisabled', 'schemes',
    'pageOriginatedSchemes', 'noDirectTcp', 'noDirectUdp', 'noBackgroundBypass',
    'brokerFailureNoFallback', 'cleanup')


def capability_from_probe(metadata, checks):
    """One complete gate, used by discovery; not a flag or wire override.

    Inputs are host observations. Tests may supply a clearly labelled synthetic
    report, but runtime/config/serialized proof cannot supply these inputs.
    Missing checks are UNKNOWN, never vacuous PASS.
    """
    if (not isinstance(metadata, BrowserCapabilitySnapshot) or not isinstance(checks, dict) or
        set(checks)-set(EGRESS_OBLIGATIONS) or any(v not in ('PASS','FAIL','UNKNOWN') for v in checks.values())):
        raise ValueError('INVALID_BROWSER_PROBE_EVIDENCE')
    failed = (any(v == 'FAIL' for v in checks.values()) or
        metadata.available.status is CapabilityStatus.KNOWN and metadata.available.value is False)
    complete = all(checks.get(k) == 'PASS' for k in EGRESS_OBLIGATIONS)
    profile = all(getattr(metadata, k).status is CapabilityStatus.KNOWN and getattr(metadata, k).value is True
        for k in ('network_broker', 'headful', 'manual_takeover', 'upload', 'download'))
    profile &= (metadata.engine.value == 'PLAYWRIGHT_CHROMIUM' and
        metadata.control_class.value == 'HOST_UNISOLATED' and
        metadata.persistent_session.status is CapabilityStatus.KNOWN and metadata.persistent_session.value is False and
        all(getattr(metadata,k).status is CapabilityStatus.KNOWN and bool(getattr(metadata,k).value)
            for k in ('engine','engine_version','browser_version','control_class','platform','max_pages')))
    if complete and profile and not failed:
        return replace(metadata, public_only=Observation.known(True), available=Observation.known(True))
    reason='native exclusive-egress proof failed' if failed else 'native exclusive-egress proof incomplete'
    return replace(metadata, public_only=Observation.known(False) if failed else Observation.unknown(reason),
        available=Observation.known(False) if failed else Observation.unknown(reason))


class ProductiveBrowserBackend:
    _discovery_lock = RLock()
    _closed_proofs = {}
    def __init__(self):
        self._proof = None
        self._port = None

    def broker(self, session, live, *, allowed_hosts=None):
        return BrowserEgressBroker(BrowserNetworkPolicy(HttpFetchBroker(), validate_session=live.is_set,
            allowed_hosts=allowed_hosts),
            limits=BrowserBrokerLimits(15, 32768, 65536, 8*1024*1024, 16))

    def runtime(self):
        if self._proof is None or self._proof.capabilities.available.value is not True:
            raise ValueError('BROWSER_CAPABILITY_UNAVAILABLE')
        if self._port is None: self._port = PlaywrightBrowserAdapter(self.broker, headful=True)
        return self._port

    def discover(self):
        # Both roots consume THIS native probe, not a saved diagnostic claim.
        # Only CLOSED proofs can be coalesced/cached. A usable proof must always
        # be fresh; installed SDK/engine/config presence never supplies success.
        try: sdk = Observation.known(version('playwright'))
        except PackageNotFoundError: sdk = Observation.unknown('optional Playwright dependency unavailable')
        key=(sdk.value,os.environ.get('PLAYWRIGHT_BROWSERS_PATH'),CHROMIUM_ARGS)
        with self._discovery_lock:
            proof=self._closed_proofs.get(key)
            if proof is None:
                native=probe_productive_browser(timeout_seconds=25,headful=True,backend=self)
                checks={name:'UNKNOWN' for name in EGRESS_OBLIGATIONS}
                checks['cleanup']='PASS' if native.evidence.get('cleanupConfirmed') else 'FAIL'
                if all(r['result']=='PASS' for r in native.evidence.get('negativeTargets',())) and len(
                    native.evidence.get('negativeTargets',()))==8:
                    checks['privateDestinationsDenied']='PASS'
                cap=capability_from_probe(native.capabilities,checks)
                proof=ProductiveBrowserProbe(cap,dict(native.evidence,component='ProductiveBrowserBackend',
                    capturedAt=datetime.now(timezone.utc).isoformat(),checks=checks,
                    engineLaunches=1,closedProofOnlyCache=True,authorityOverride=False,
                    unavailablePrerequisites=['native Chromium/children TCP/UDP/DNS/background exhaustive observation',
                        'full positive HTTP/HTTPS topology and all page-originated scheme pre-effect guards']))
                if proof.capabilities.available.value is not True:self._closed_proofs[key]=proof
            self._proof=proof
        return self._proof
