"""WEBVIEW2_ADAPTER_CONTRACT_TEST. Doubles prove error/wiring, not an engine."""
from datetime import datetime, timedelta, timezone
import json
import ast
from pathlib import Path
import subprocess

import pytest

from local_cli.infrastructure.active_web import webview2_ipc as wire
from local_cli.infrastructure.active_web import webview2_adapter as adapter
from local_cli.infrastructure.active_web.host_ipc_protocol import HostIpcError, IpcCode, opaque, decode as v1decode
from local_cli.infrastructure.active_web.browser_host import HostState


def deadline(): return datetime.now(timezone.utc)+timedelta(seconds=20)


@pytest.mark.parametrize('command', wire.COMMANDS)
def test_closed_v2_serialization(command):
    m=wire.envelope(opaque('bws'),{'command':command},page=opaque('bwp') if command in wire.PAGE_COMMANDS else None)
    assert wire.decode(wire.encode(m)[4:]) == m
    with pytest.raises(HostIpcError) as e: v1decode(wire.encode(m)[4:])
    assert e.value.code is IpcCode.PROTOCOL_MISMATCH


@pytest.mark.parametrize('field', ['approval','grant','password','cookies','script','selector','uri','authority'])
def test_no_authority_or_future_payload(field):
    m=wire.envelope(opaque('bws'),{'command':'session_create'})
    m['payload'][field]='synthetic'
    with pytest.raises(HostIpcError): wire.encode(m)


@pytest.mark.parametrize('command', ['navigate','eval','ExternalProtocolGuard','browser_open','install_runtime'])
def test_unimplemented_fail_closed(command):
    with pytest.raises(HostIpcError): wire.envelope(opaque('bws'),{'command':command})


@pytest.mark.parametrize('code', list(wire.EngineCode))
def test_adapter_typed_fault_no_retry(monkeypatch, tmp_path, code):
    calls=[]
    class Client:
        state=HostState.READY
        def __init__(self,*args): pass
        def start(self,**kwargs): calls.append('start')
        def call(self,*args,**kwargs): calls.append('call'); raise wire.EngineIpcError(code)
    monkeypatch.setattr(adapter,'WebView2HostClient',Client)
    a=adapter.WebView2BrowserAdapter('trusted','trusted',tmp_path)
    with pytest.raises(adapter.WebView2PortError) as e: a.create_context(opaque('bws'),deadline=deadline(),cancellation=None)
    assert e.value.engine_code is code and calls==['start','call']


def test_cleanup_unconfirmed_is_not_close_success(tmp_path):
    a=adapter.WebView2BrowserAdapter('trusted','trusted',tmp_path); session=opaque('bws')
    class Client:
        state=HostState.CLEANUP_UNCONFIRMED
        cleanup_confirmed=False
        def _cleanup(self): pass
    a._sessions[session]=Client()
    with pytest.raises(adapter.WebView2PortError) as e: a.close_context(session,deadline=deadline())
    assert e.value.engine_code is IpcCode.CLEANUP_UNCONFIRMED


def test_delete_on_close_cleanup_race_is_idempotent(monkeypatch,tmp_path):
    c=adapter.WebView2HostClient('trusted','trusted',opaque('bws'),tmp_path)
    c.udf.mkdir();(c.udf/'.nova-owner').write_text(c.instance,encoding='utf-8')
    lock=c.udf/'delete-on-close';lock.write_text('synthetic',encoding='utf-8')
    original=Path.lstat
    def race(path,*args,**kwargs):
        if path==lock:lock.unlink()
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'lstat',race)
    # Exercises only owned-tree deletion, not a fabricated process-exit proof.
    c._remove_udf();assert not c.udf.exists()


def test_python_310_path_api_and_syntax_compatibility(monkeypatch,tmp_path):
    monkeypatch.delattr(Path,'is_junction')
    c=adapter.WebView2HostClient('trusted','trusted',opaque('bws'),tmp_path)
    assert c.state is HostState.NOT_STARTED
    for module in (adapter,wire):
        ast.parse(Path(module.__file__).read_text(encoding='utf-8'),feature_version=(3,10))
    # API/syntax contract, not a claim that Python 3.10 executed this native run.


def test_engine_is_not_productive_capability_or_default_tool():
    from local_cli.tools import get_default_tools
    tools=get_default_tools()
    assert not any(t.name.startswith('browser_') for t in tools)
    source=Path(adapter.__file__).read_text(encoding='utf-8')
    assert 'Playwright' not in source.replace('No Playwright fallback','')
    assert 'available = True' not in source and 'available=True' not in source
    for method in ('navigate','observe','act','upload','download','takeover'):
        with pytest.raises(adapter.WebView2PortError) as e:
            getattr(adapter.WebView2BrowserAdapter('trusted','trusted','trusted'),method)()
        assert e.value.engine_code is wire.EngineCode.NOT_SUPPORTED_IN_CURRENT_BLOCK


@pytest.fixture(scope='session')
def engine_contract_runner(host_build, tmp_path_factory):
    work=tmp_path_factory.mktemp('engine-contract-build'); feed=work/'empty';feed.mkdir()
    command=[str(host_build[0]),'build',str(Path(__file__).parent/'engine_contracts/contract_runner.csproj'),
             '-c','Release','--source',str(feed),'-p:NuGetAudit=false','-p:UseAppHost=false',
             '-p:HostBin='+str(host_build[1].parent),'-p:BaseIntermediateOutputPath='+str(work/'obj')+'/',
             '-p:OutputPath='+str(work/'bin')+'/', '--nologo']
    r=subprocess.run(command,capture_output=True,text=True,timeout=60)
    (work/'build.txt').write_text(r.stdout+r.stderr,encoding='utf-8')
    assert r.returncode==0,r.stdout+r.stderr
    return host_build[0],work/'bin/nova-browser-host-contract-tests.dll'


@pytest.mark.parametrize('mode', ['version','absent','incompatible','environment','controller'])
def test_csharp_fault_mapping(mode, engine_contract_runner, tmp_path):
    r=subprocess.run([str(p) for p in engine_contract_runner]+[mode,str(tmp_path/'private-udf')],
                     capture_output=True,text=True,timeout=30)
    (tmp_path/'contract.txt').write_text(r.stdout+r.stderr,encoding='utf-8')
    assert r.returncode==0,r.stdout+r.stderr
    assert ':PASS' in r.stdout and not (tmp_path/'private-udf').exists()
