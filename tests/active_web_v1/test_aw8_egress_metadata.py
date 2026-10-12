"""Static adapter metadata contracts, not exclusive-egress host evidence."""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import sys

import pytest

from local_cli.core.contracts import BrowserCapabilitySnapshot, Observation, CapabilityStatus
from local_cli.infrastructure.active_web import playwright_adapter as adapter
from local_cli.infrastructure.active_web.productive_backend import capability_from_probe, EGRESS_OBLIGATIONS
from local_cli.application.active_web_service import usable as usable_browser_capability


def metadata(monkeypatch,headful=True,network=True):
    port=object.__new__(adapter.PlaywrightBrowserAdapter)
    port._headful=headful
    context=SimpleNamespace(engine_version='synthetic-sdk',browser_version='synthetic-engine',broker=object())
    port._context=lambda _:context
    port._call=lambda factory,deadline:asyncio.run(factory())
    monkeypatch.setattr(adapter,'probe_browser_broker',lambda *a,**kw:BrowserCapabilitySnapshot(
        network_broker=Observation.known(network)))
    return port.capabilities('synthetic-session',deadline=datetime.now(timezone.utc)+timedelta(seconds=2))


@pytest.mark.parametrize('field,expected',(
    ('manual_takeover',True),('upload',True),('download',True),
    ('persistent_session',False),('platform',sys.platform),('max_pages',3),('screenshot',False)))
def test_static_metadata_is_known_without_network_claim(monkeypatch,field,expected):
    cap=metadata(monkeypatch)
    assert getattr(cap,field).status is CapabilityStatus.KNOWN
    assert getattr(cap,field).value==expected
    assert cap.public_only.status is CapabilityStatus.UNKNOWN
    assert cap.available.status is CapabilityStatus.UNKNOWN
    assert not usable_browser_capability(cap)


def test_headless_cannot_claim_manual_takeover_or_open_product_gate(monkeypatch):
    cap=metadata(monkeypatch,headful=False)
    assert cap.manual_takeover==Observation.known(False)
    gated=capability_from_probe(cap,{name:'PASS' for name in EGRESS_OBLIGATIONS})
    assert gated.available.value is not True
    assert not usable_browser_capability(gated)


def test_failed_broker_static_metadata_does_not_enable_tools(monkeypatch):
    cap=metadata(monkeypatch,network=False)
    gated=capability_from_probe(cap,{name:'PASS' for name in EGRESS_OBLIGATIONS})
    assert gated.network_broker==Observation.known(False)
    assert gated.available.value is not True
    assert not usable_browser_capability(gated)


def test_external_escape_unknown_blocks_gate_despite_all_other_checks(monkeypatch):
    cap=metadata(monkeypatch)
    checks={name:'PASS' for name in EGRESS_OBLIGATIONS}
    checks['pageOriginatedSchemes']='UNKNOWN'
    gated=capability_from_probe(cap,checks)
    assert gated.available.status is CapabilityStatus.UNKNOWN
    assert gated.public_only.status is CapabilityStatus.UNKNOWN
    assert not usable_browser_capability(gated)


def test_external_escape_failed_blocks_gate_despite_all_other_checks(monkeypatch):
    cap=metadata(monkeypatch)
    checks={name:'PASS' for name in EGRESS_OBLIGATIONS}
    checks['pageOriginatedSchemes']='FAIL'
    gated=capability_from_probe(cap,checks)
    assert gated.available==Observation.known(False)
    assert gated.public_only==Observation.known(False)
    assert not usable_browser_capability(gated)
