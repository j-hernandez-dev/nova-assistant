"""Portable AW5 contracts without requiring/importing an installed engine."""
import asyncio
import builtins
from datetime import datetime, timedelta, timezone
import subprocess
import sys

import pytest

from local_cli.application.cancellation import CancellationController
from local_cli.core.active_web import new_browser_session_ref
from local_cli.core.active_web_lifecycle import BrowserLifecycleError, BrowserLifecycleErrorCode as Code
from local_cli.infrastructure.active_web.playwright_adapter import (
    PlaywrightBrowserAdapter, CHROMIUM_ARGS, _url, _fingerprint,
)


def end(seconds=3):return datetime.now(timezone.utc)+timedelta(seconds=seconds)


@pytest.mark.parametrize('bad',['file:///secret','javascript:alert(1)','data:text/html,a',
    'chrome://settings','about:blank','ws://site.test','https://user:secret@site.test/',
    'http://site.test/#secret','http://2130706433/'])
def test_agent_targets_fail_closed_before_worker_or_engine(bad):
    with pytest.raises(BrowserLifecycleError) as error:_url(bad)
    assert error.value.code is Code.INVALID and 'secret' not in str(error.value)


@pytest.mark.parametrize('url',['http://site.test/a','https://site.test:443/a?x=1'])
def test_valid_http_targets_are_not_authority_or_dns(url):
    assert _url(url).startswith(('http://','https://'))


def test_optional_module_import_never_imports_engine_or_installer():
    result=subprocess.run([sys.executable,'-B','-c',
        "import sys;import local_cli.infrastructure.active_web.playwright_adapter;assert 'playwright' not in sys.modules"],
        capture_output=True,text=True,timeout=5)
    assert result.returncode==0,result.stderr


def test_missing_optional_dependency_is_typed_before_broker_start(monkeypatch):
    original=builtins.__import__;calls=[]
    def missing(name,*args,**kwargs):
        if name.startswith('playwright'):raise ImportError('private backend detail')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',missing)
    p=PlaywrightBrowserAdapter(lambda *args:calls.append(args))
    try:
        with pytest.raises(BrowserLifecycleError) as error:
            p.create_context(new_browser_session_ref(),deadline=end(),cancellation=CancellationController())
        assert error.value.code is Code.PORT and 'private' not in str(error.value)
        assert calls==[]
    finally:assert p.shutdown(deadline=end())


@pytest.mark.parametrize('cancelled',[False,True])
def test_expired_or_cancelled_call_never_schedules_side_effect(cancelled):
    calls=[];p=PlaywrightBrowserAdapter(lambda *args:calls.append(args));token=CancellationController()
    if cancelled:token.request()
    try:
        with pytest.raises(BrowserLifecycleError) as error:
            p.create_context(new_browser_session_ref(),deadline=end(2 if cancelled else -1),cancellation=token)
        assert error.value.code is (Code.CANCELLED if cancelled else Code.DEADLINE)
        assert not calls
    finally:assert p.shutdown(deadline=end())


def test_worker_timeout_discards_late_result_without_retry():
    p=PlaywrightBrowserAdapter(lambda *args:None);attempts=[]
    async def work():
        attempts.append(1)
        await asyncio.sleep(5)
        return 'late'
    try:
        with pytest.raises(BrowserLifecycleError) as error:p._call(work,end(.05))
        assert error.value.code is Code.DEADLINE and attempts==[1]
        # Barrier on same worker demonstrates recovery after task cancellation.
        async def barrier():return 'fresh'
        assert p._call(barrier,end())=='fresh' and attempts==[1]
    finally:assert p.shutdown(deadline=end())


def test_launch_contract_fixed_flags_no_personal_or_desktop_profile():
    assert '--proxy-bypass-list=<-loopback>' in CHROMIUM_ARGS
    assert '--disable-quic' in CHROMIUM_ARGS
    assert all('user-data-dir' not in flag and 'remote-debugging-port' not in flag for flag in CHROMIUM_ARGS)
    assert _fingerprint({'href':'https://a.test','role':'link'})!=_fingerprint({'href':'https://b.test','role':'link'})
    assert _fingerprint({'b':2,'a':1})==_fingerprint({'a':1,'b':2})
    # Configuration contracts are not proof of browser-exclusive egress.


def test_proxy_challenge_before_dns_connect_and_authenticated_request():
    from tests.active_web_v1.test_aw4_proxy import upstream,FixtureAdmission,broker,connect,read_all,exchange
    with upstream() as server,broker(FixtureAdmission(server)) as b:
        with connect(b) as client:
            target=f'http://server.test:{server.server_port}/'
            client.sendall(f'GET {target} HTTP/1.1\r\nHost: server.test:{server.server_port}\r\n\r\n'.encode())
            denied=read_all(client)
        assert denied.startswith(b'HTTP/1.1 407 Proxy Authentication Required\r\n')
        assert b'Proxy-Authenticate: Basic realm="Nova Active Web"\r\n' in denied
        assert b'BROWSER_EGRESS_CHANNEL_DENIED' in denied and server.hits==[] and server.connections==0
        assert b'200' in exchange(b,target)
        assert len(server.hits)==1


@pytest.mark.parametrize('headful',[None,1,'true'])
def test_adapter_configuration_rejects_truthy_non_boolean(headful):
    with pytest.raises(BrowserLifecycleError):PlaywrightBrowserAdapter(lambda *a:None,headful=headful)
