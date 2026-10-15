"""S5 pure contracts/policy/text tests; no socket or native process launches."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from local_cli.application.network import NetworkFetchService, canonical_url, public_address
from local_cli.application.cancellation import CancellationController
from local_cli.core.network import FetchBudget, FetchLimits, HttpHop, NetworkError
from local_cli.network_config import DEFAULT_FETCH_LIMITS


@pytest.mark.parametrize('url', ['file:///x', 'data:text/plain,x', 'ftp://example.com/x',
    'http://user:pass@example.com/', 'http://127.1/', 'http://2130706433/',
    'http://0177.0.0.1/', 'http://0x7f000001/', 'http://example.com\\@localhost/',
    'http://example.com/#x', 'http://example.com/\r\nHeader:x'])
def test_url_denied_without_ambient_scheme_handlers(url):
    with pytest.raises(NetworkError, match='NETWORK_URL_DENIED'):
        canonical_url(url)


@pytest.mark.parametrize('url,expected', [('https://EXAMPLE.com:443', 'https://example.com/'),
    ('http://example.com:80/a?q=x', 'http://example.com/a?q=x'),
    ('http://[2606:4700:4700::1111]/a', 'http://[2606:4700:4700::1111]/a')])
def test_canonical_http_https(url, expected):
    assert canonical_url(url) == expected


@pytest.mark.parametrize('ip', ['127.0.0.1', '0.0.0.0', '10.0.0.1', '172.16.0.1',
    '192.168.0.1', '169.254.169.254', '100.64.0.1', '192.0.2.1', '198.18.0.1',
    '224.0.0.1', '255.255.255.255', '::1', '::', 'fc00::1', 'fd00::1', 'fe80::1',
    'ff02::1', '2001:db8::1', '::ffff:127.0.0.1', '::ffff:10.0.0.1',
    '2002:0a00:0001::1', '64:ff9b::a00:1', '2001:0000:4136:e378:8000:63bf:3fff:fdd2', 'fe80::1%1'])
def test_special_destinations_denied(ip):
    assert not public_address(ip)


@pytest.mark.parametrize('ip', ['8.8.8.8', '1.1.1.1', '2606:4700:4700::1111', '::ffff:8.8.8.8'])
def test_globally_routable_destinations(ip):
    assert public_address(ip)


@pytest.mark.parametrize('field,value', [('timeout_seconds', 0), ('timeout_seconds', float('nan')),
    ('body_bytes', 0), ('body_bytes', True), ('redirects', -1), ('published_chars', 0)])
def test_explicit_limits_are_validated(field, value):
    with pytest.raises(ValueError):
        replace(DEFAULT_FETCH_LIMITS, **{field:value})


def test_authorized_defaults_and_bound_text_including_marker():
    assert DEFAULT_FETCH_LIMITS == FetchLimits(30, 2097152, 5, 50000)
    service = NetworkFetchService(None, DEFAULT_FETCH_LIMITS)
    for maximum in (1, 5, 50, 50000, 100000):
        text, truncated = service._text(HttpHop(200, 'text/plain', None, b'a'*60000), maximum)
        assert truncated and len(text) <= min(maximum, 50000)
    assert service._text(HttpHop(200, 'text/html', None, b'<p>ok</p>'), 50) == ('ok', False)
    assert service._text(HttpHop(200, 'text/plain; charset=unknown_fixture', None, b'ok', True), 50)[1]


def test_total_budget_and_core_deadline_and_cancellation():
    token = CancellationController()
    budget = FetchBudget(DEFAULT_FETCH_LIMITS, token, datetime.now(timezone.utc)-timedelta(seconds=1))
    with pytest.raises(NetworkError, match='NETWORK_TIMEOUT'):
        budget.check()
    budget = FetchBudget(DEFAULT_FETCH_LIMITS, token, None)
    token.request()
    with pytest.raises(NetworkError, match='NETWORK_CANCELLED'):
        budget.remaining()


def test_broker_has_no_insecure_tls_mode():
    import ssl
    from local_cli.infrastructure.http_fetch import HttpFetchBroker
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with pytest.raises(ValueError, match='verified TLS required'):
        HttpFetchBroker(tls_context=context)
