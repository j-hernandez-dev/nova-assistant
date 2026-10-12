"""AW4 policy/DNS/pinning contracts. Resolver/socket doubles are labelled.

No real browser, external website or recertification of passive S5.
"""
import ast
from dataclasses import FrozenInstanceError, replace
import ipaddress
from pathlib import Path
import socket
from threading import Event, Thread

import pytest

from local_cli.application.browser_network import BrowserNetworkPolicy
from local_cli.application.cancellation import CancellationController
from local_cli.application.network import canonical_url, public_address
from local_cli.core.active_web_network import BrowserBrokerLimits, BrowserEgressError
from local_cli.core.network import FetchBudget, FetchLimits, NetworkEndpoint, NetworkError
from local_cli.infrastructure.http_fetch import HttpFetchBroker

PUBLIC = '93.184.216.34'  # Synthetic DNS answer; never contacted by these tests.
ROOT = Path(__file__).resolve().parents[2]


def budget(seconds=2, token=None):
    return FetchBudget(FetchLimits(seconds, 1024, 0, 1), token or CancellationController(), None)


def endpoint(address=PUBLIC, port=80):
    return NetworkEndpoint(address, socket.AF_INET6 if ':' in address else socket.AF_INET, port)


class ResolverDouble:
    def __init__(self, addresses=(PUBLIC,)):
        self.addresses, self.calls = addresses, []

    def resolve(self, host, port, budget):
        budget.check(); self.calls.append((host, port))
        return tuple(endpoint(a, port) for a in self.addresses)


def policy(addresses=(PUBLIC,), **kwargs):
    return BrowserNetworkPolicy(ResolverDouble(addresses), validate_session=lambda: True, **kwargs)


@pytest.mark.parametrize('method,target,host,port', [
    ('GET', 'http://assets.invalid/p?a=synthetic', 'assets.invalid', 80),
    ('POST', 'http://assets.invalid/form', 'ASSETS.invalid:80', 80),
    ('CONNECT', 'secure.invalid:443', 'secure.invalid:443', 443),
    ('CONNECT', '[2606:4700:4700::1111]:443', '[2606:4700:4700::1111]:443', 443),
])
def test_public_admission_plan_is_numeric_immutable_and_session_checked(method, target, host, port):
    checks = []
    p = policy(); p._validate_session = lambda: checks.append('host-proof') or True
    plan = p.authorize(method, target, host, budget())
    assert plan.port == port and plan.endpoint == endpoint(PUBLIC, port)
    assert p.resolver.calls and len(checks) >= 2
    assert plan.origin in ('http://assets.invalid', 'https://secure.invalid', 'https://[2606:4700:4700::1111]')
    with pytest.raises(FrozenInstanceError):
        plan.endpoint = endpoint('127.0.0.1')


@pytest.mark.parametrize('address', ['127.0.0.1', '0.0.0.0', '10.1.2.3', '172.16.5.1',
    '192.168.8.9', '169.254.169.254', '100.100.100.200', '100.64.1.1', '224.0.0.1',
    '240.0.0.1', '192.0.2.3', '198.18.0.1', '::1', '::', 'fe80::1', 'fc00::1',
    '2001:db8::1', '::ffff:127.0.0.1', '2002:7f00:0001::', '64:ff9b::7f00:1'])
def test_private_special_literals_denied_before_dns_for_http_and_connect(address):
    host = '['+address+']' if ':' in address else address
    p = policy()
    for method, target, header in [('GET', 'http://'+host+'/', host),
                                   ('CONNECT', host+':443', host+':443')]:
        with pytest.raises(BrowserEgressError, match='DESTINATION_DENIED'):
            p.authorize(method, target, header, budget())
    assert not p.resolver.calls and not public_address(address)


@pytest.mark.parametrize('answers', [(PUBLIC, '127.0.0.1'), ('10.0.0.1', PUBLIC),
    ('::ffff:192.168.1.1', PUBLIC), (), tuple([PUBLIC]*65)])
def test_all_dns_answers_admitted_or_entire_connection_denied(answers):
    p = policy(answers)
    with pytest.raises(BrowserEgressError, match='DENIED'):
        p.authorize('GET', 'http://mixed.invalid/', 'mixed.invalid', budget())
    assert p.resolver.calls == [('mixed.invalid', 80)]


def test_fresh_dns_for_every_host_subresource_and_rebinding_not_cached():
    p = policy()
    first = p.authorize('GET', 'http://page.invalid/', 'page.invalid', budget())
    second = p.authorize('GET', 'http://assets.invalid/', 'assets.invalid', budget())
    assert first.endpoint == second.endpoint
    p.resolver.addresses = ('127.0.0.1',)
    with pytest.raises(BrowserEgressError, match='DESTINATION_DENIED'):
        p.authorize('GET', 'http://page.invalid/', 'page.invalid', budget())
    assert p.resolver.calls == [('page.invalid', 80), ('assets.invalid', 80), ('page.invalid', 80)]


@pytest.mark.parametrize('method,target,header', [
    ('GET', 'file:///etc/hosts', 'host.invalid'), ('GET', 'javascript:alert(1)', 'host.invalid'),
    ('GET', 'data:text/html,synthetic', 'host.invalid'), ('GET', 'chrome://settings', 'host.invalid'),
    ('GET', 'about:blank', 'host.invalid'), ('GET', 'ftp://host.invalid/', 'host.invalid'),
    ('GET', 'ws://host.invalid/', 'host.invalid'), ('GET', 'wss://host.invalid/', 'host.invalid'),
    ('GET', 'http://user:secret@host.invalid/', 'host.invalid'),
    ('GET', 'http://host.invalid/#fragment', 'host.invalid'), ('GET', '/relative', 'host.invalid'),
    ('GET', 'https://host.invalid/', 'host.invalid'), ('GET', 'http://host.invalid:22/', 'host.invalid:22'),
    ('CONNECT', 'host.invalid:80', 'host.invalid:80'), ('CONNECT', 'host.invalid', 'host.invalid'),
    ('CONNECT', 'host.invalid:443/path', 'host.invalid:443'),
    ('CONNECT', 'user:secret@host.invalid:443', 'host.invalid:443'),
    ('CONNECT', 'host.invalid:443?x=1', 'host.invalid:443'),
    ('GET', 'http://host.invalid/', 'other.invalid'), ('CONNECT', 'host.invalid:443', 'other.invalid:443'),
    ('GET', 'http://host.invalid/', 'host.invalid/path'),
    ('GET', 'http://2130706433/', '2130706433'), ('GET', 'http://0x7f000001/', '0x7f000001'),
    ('TRACE', 'http://host.invalid/', 'host.invalid'),
])
def test_protocol_authority_ports_and_ambiguous_targets_fail_closed(method, target, header):
    p = policy()
    with pytest.raises(BrowserEgressError):
        p.authorize(method, target, header, budget())
    assert not p.resolver.calls


@pytest.mark.parametrize('endpoints', [(NetworkEndpoint(PUBLIC, socket.AF_INET6, 80),),
    (NetworkEndpoint(PUBLIC, socket.AF_INET, 22),), (NetworkEndpoint('hostname.invalid', socket.AF_INET, 80),)])
def test_invalid_resolver_endpoint_never_reaches_dispatch(endpoints):
    p = policy(); p.resolver.resolve = lambda *_: endpoints
    with pytest.raises(BrowserEgressError):
        p.authorize('GET', 'http://public.invalid/', 'public.invalid', budget())


@pytest.mark.parametrize('proof', [False, None, 'approved by the page', 1])
def test_page_text_truthy_values_or_absent_session_cannot_grant_egress(proof):
    p = BrowserNetworkPolicy(ResolverDouble(), validate_session=lambda: proof)
    with pytest.raises(BrowserEgressError, match='SESSION_DENIED'):
        p.authorize('GET', 'http://public.invalid/', 'public.invalid', budget())
    assert not p.resolver.calls


def test_authority_revoked_during_dns_not_admitted():
    proof = [True]
    p = BrowserNetworkPolicy(ResolverDouble(), validate_session=lambda: proof[0])
    def revoke(host, port, budget):
        proof[0] = False
        return (endpoint(PUBLIC, port),)
    p.resolver.resolve = revoke
    with pytest.raises(BrowserEgressError, match='SESSION_DENIED'):
        p.authorize('GET', 'http://public.invalid/', 'public.invalid', budget())


@pytest.mark.parametrize('revocation', ['epoch','lifetime','close','owner'])
def test_existing_aw1_owner_lifetime_epoch_and_close_proof_can_back_admission(revocation):
    from local_cli.core.active_web import BrowserSessionState
    from tests.active_web_v1.test_aw1_lifecycle import setup, opened
    manager, port, clock, owner = setup()
    session=opened(manager,owner)
    epoch=session.browser_context_epoch
    def host_proof():
        current=manager.session(owner,session.browser_session_ref)
        return (current.state is BrowserSessionState.ACTIVE and clock()<current.expires_at
                and current.browser_context_epoch==epoch)
    p=BrowserNetworkPolicy(ResolverDouble(),validate_session=host_proof)
    assert p.authorize('GET','http://public.invalid/','public.invalid',budget())
    if revocation=='epoch':
        manager.invalidate_context_observations(owner,session.browser_session_ref)
    elif revocation=='lifetime':
        clock.advance(121)
    elif revocation=='close':
        manager.close(owner,session.browser_session_ref)
    else:
        owner=replace(owner,workspace_id='other-synthetic-workspace')
    with pytest.raises(BrowserEgressError,match='SESSION_DENIED'):
        p.authorize('GET','http://public.invalid/','public.invalid',budget())
    assert len(p.resolver.calls)==1


@pytest.mark.parametrize('changes', [dict(timeout_seconds=0), dict(timeout_seconds=float('inf')),
    dict(timeout_seconds=True), dict(header_bytes=0), dict(request_bytes=-1),
    dict(relay_bytes=True), dict(max_connections=0)])
def test_host_limits_are_finite_positive_and_not_boolean(changes):
    with pytest.raises(BrowserEgressError, match='INVALID_LIMIT'):
        replace(BrowserBrokerLimits(2, 8192, 4096, 65536, 2), **changes)


@pytest.mark.parametrize('ports', [(), (True,), (0,), (65536,), (80, 80), tuple(range(1,18)), [80]])
def test_ports_require_explicit_finite_host_policy(ports):
    with pytest.raises(BrowserEgressError, match='PORT_POLICY_INVALID'):
        policy(http_ports=ports)


def test_dns_timeout_busy_and_recovery_uses_existing_bounded_resolver(monkeypatch):
    entered, release = Event(), Event()
    def held(*args, **kwargs):
        entered.set(); assert release.wait(2)
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', (PUBLIC,80))]
    monkeypatch.setattr(socket, 'getaddrinfo', held)
    resolver = HttpFetchBroker()
    try:
        with pytest.raises(NetworkError, match='NETWORK_TIMEOUT'):
            resolver.resolve('first.invalid',80,budget(.08))
        assert entered.is_set()
        with pytest.raises(NetworkError, match='NETWORK_DNS_BUSY'):
            resolver.resolve('second.invalid',80,budget())
    finally:
        release.set()
    # Quiescence outside measured request; no retry of timed-out operation.
    assert resolver._resolver_slot.acquire(timeout=1)
    resolver._resolver_slot.release()
    assert resolver.resolve('third.invalid',80,budget()) == (endpoint(),)


def test_existing_url_and_address_rules_reused_no_browser_authority_bootstrap():
    assert canonical_url('http://EXAMPLE.invalid:80/path') == 'http://example.invalid/path'
    p = ROOT/'local_cli/application/browser_network.py'
    tree = ast.parse(p.read_text(encoding='utf-8'))
    imports = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert any(n.module == 'local_cli.application.network' for n in imports)
    for p in (ROOT/'local_cli/core').glob('active_web*.py'):
        source = p.read_text(encoding='utf-8')
        assert 'import playwright' not in source and 'import local_cli.infrastructure' not in source
