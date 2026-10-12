"""B6 test-only frozen candidate/owned cleanup supplement to the B5 write guard."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import pytest
from v12_b4.conftest import native

ROOT=Path(__file__).resolve().parents[4]
clients=[]

def pytest_configure(config):
    from local_cli.infrastructure.active_web.webview2_adapter import WebView2HostClient
    original=WebView2HostClient.__init__
    def owned(self,*args,**kwargs):
        original(self,*args,**kwargs);clients.append(self)
    WebView2HostClient.__init__=owned

@pytest.hookimpl(tryfirst=True)
def pytest_fixture_setup(fixturedef,request):
    if fixturedef.argname=='runner' and fixturedef.func.__module__.endswith('test_baseline'):
        dest=fixturedef.func.__globals__['EVIDENCE']
        assert not dest.is_relative_to(ROOT)
        target=dest/'guard_runner'
        if not target.exists():
            source=ROOT/'docs/active_web_v1_2/v12_b3_interactive_browser_baseline/guard_runner'
            target.mkdir(parents=True)
            for name in ('guard_runner.csproj','Program.cs'):shutil.copyfile(source/name,target/name)
    if fixturedef.argname!='host_build' or not os.environ.get('NOVA_B6_FROZEN_CANDIDATE'):return None
    data=json.loads(Path(os.environ['NOVA_B6_FROZEN_CANDIDATE']).read_text(encoding='utf-8'))
    dll=ROOT/data['hostAssembly'];dotnet=Path(data['dotnetExecutable'])
    expected=dict(data['browser']['pins'])
    assert hashlib.sha256(dll.read_bytes()).hexdigest()==expected[data['hostAssembly']]
    assert hashlib.sha256(dotnet.read_bytes()).hexdigest()==expected[str(dotnet)]
    result=(dotnet,dll);fixturedef.cached_result=(result,fixturedef.cache_key(request),None)
    return result

@pytest.hookimpl(trylast=True)
def pytest_runtest_setup(item):
    # The historical shield already redirected the helper's EVIDENCE before
    # fixture setup. Copy only immutable runner source into its new owned temp.
    for name,module in tuple(sys.modules.items()):
        if module is None or not name.endswith('test_baseline'):continue
        dest=vars(module).get('EVIDENCE')
        if isinstance(dest,Path)and not dest.is_relative_to(ROOT):
            target=dest/'guard_runner'
            if not target.exists():
                source=ROOT/'docs/active_web_v1_2/v12_b3_interactive_browser_baseline/guard_runner'
                target.mkdir(parents=True)
                for name in ('guard_runner.csproj','Program.cs'):shutil.copyfile(source/name,target/name)

@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session,exitstatus):
    out=Path(os.environ['NOVA_B5_TEST_OUTPUT']);rows=[]
    for client in clients:
        if not hasattr(client,'udf'):continue
        exited=client.process is None or client.process.poll()is not None
        confirmed=client.cleanup_confirmed and exited and not client.udf.exists()
        row=dict(session=client.session,instance=client.instance,udf=str(client.udf),
            hostPid=client.process.pid if client.process else None,cleanup='CONFIRMED'if confirmed else'CLEANUP_UNCONFIRMED')
        journal=Path(str(client.udf)+'.guard-audit.jsonl')
        if journal.exists()and confirmed and not journal.is_symlink():
            saved=out/'owned_journals'/journal.name;saved.parent.mkdir(parents=True,exist_ok=True)
            saved.write_bytes(journal.read_bytes());row['journalSha256']=hashlib.sha256(saved.read_bytes()).hexdigest()
            journal.unlink();row['journalRemoved']=not journal.exists()
        rows.append(row)
    (out/'owned_cleanup.json').write_text(json.dumps(dict(scope='B6_NEW_PYTHON_HOST_INSTANCES_ONLY',instances=rows,
        historicalResourcesTouched=False,exitStatus=exitstatus),indent=2)+'\n',encoding='utf-8')
