"""B2 seam/authority extensions; no doubles counted as native certificate evidence."""
from dataclasses import replace
import socket
import ssl

import pytest

from local_cli.core.controlled_fetch import (
    ControlledFetchError,ControlledFetchErrorCode as Error,ControlledFetchOutcome as Outcome,
    ControlledFetchOutcomeLedger,ControlledFetchTransportEvidence,ControlledFetchTransportFailure,
)
from local_cli.infrastructure.controlled_fetch_transport import RealControlledFetchTransport
from tests.active_web_v1_2.conftest import make_fetch as fixture_make_fetch


@pytest.fixture
def host(tmp_path):return fixture_make_fetch.__wrapped__(tmp_path)()


def test_raw_ip_hostname_and_clone_cannot_pass_real_port_guard(host,monkeypatch):
    # True host ledger, no registered plan at all; must fail before socket creation.
    monkeypatch.setattr(socket,'socket',lambda *_a,**_k:pytest.fail('socket before admitted plan'))
    port=RealControlledFetchTransport(validate_plan=host.service.transport_guard)
    for fake in ('127.0.0.1','cf-public.test',{'ip':'1.1.1.1','capabilityId':'CONTROLLED_FETCH_V1_2'}):
        with pytest.raises(ControlledFetchError):port.validate(fake)
        with pytest.raises(ControlledFetchError):port.dispatch(fake,object())


@pytest.mark.parametrize('check,mode',[(False,ssl.CERT_REQUIRED),(False,ssl.CERT_NONE)])
def test_insecure_tls_context_never_constructs_candidate(check,mode):
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT);ctx.check_hostname=check;ctx.verify_mode=mode
    with pytest.raises(ControlledFetchError) as error:RealControlledFetchTransport(validate_plan=lambda *_:None,tls_context=ctx)
    assert error.value.code is Error.TLS


def test_zero_http_bytes_is_not_a_free_boolean_proof(host):
    ledger=ControlledFetchOutcomeLedger();ledger.started();ledger.dispatch()
    with pytest.raises(ControlledFetchError):ledger.finish(Outcome.FAILED_NO_EFFECT_CONFIRMED,no_effect_evidence=True)
    with pytest.raises(ControlledFetchError):ledger.finish(Outcome.FAILED_NO_EFFECT_CONFIRMED,no_effect_evidence={'sent':0})
    ledger.finish(Outcome.UNKNOWN)


def test_transport_failure_after_real_entry_does_not_replay_host_grant(host):
    # No socket: contract double, intentionally labelled separate from native evidence.
    host.port.hops=[ConnectionResetError('private raw detail')]
    result=host.service.execute(host.request,host.context,host.grant)
    assert result.outcome is Outcome.UNKNOWN and len(host.port.calls)==1
    with pytest.raises(ControlledFetchError):host.service.execute(host.request,host.context,host.grant)


def test_b2_additions_do_not_activate_productive_snapshot():
    from local_cli.core.controlled_fetch import controlled_fetch_capabilities
    cap=controlled_fetch_capabilities()
    assert all(cap[k]['status']=='UNKNOWN' for k in ('available','networkEgressControl','publicOnly'))
    assert all(cap[k]['value'] is False for k in ('POST','auth','binaryDownload'))
