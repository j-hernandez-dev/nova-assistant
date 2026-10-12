"""Prospective revision02 contracts/native synthetic inputs; no LLM/network.

The two separately authorized historical tests retain real human UI input.
These cases record only booleans; values are generated inside the C# runner.
"""
from pathlib import Path
import subprocess
import pytest


@pytest.fixture(scope='session')
def revision02_runner(host_build,tmp_path_factory):
    work=tmp_path_factory.mktemp('revision02-runner');feed=work/'empty';feed.mkdir()
    command=[str(host_build[0]),'build',str(Path(__file__).parent/'secret_revision02_runner/runner.csproj'),'-c','Release','--source',str(feed),'-p:NuGetAudit=false','-p:HostBin='+str(host_build[1].parent),'-p:BaseIntermediateOutputPath='+str(work/'obj')+'/', '-p:OutputPath='+str(work/'bin')+'/', '--nologo']
    r=subprocess.run(command,capture_output=True,text=True,timeout=60)
    (work/'build.txt').write_text(r.stdout+r.stderr,encoding='utf-8')
    assert r.returncode==0,r.stdout+r.stderr
    return work/'bin/nova-browser-host-contract-tests.exe'


@pytest.mark.parametrize('mode',['prefix','shrink','replacement','clear','paste','multiple','dedup','count','total'])
def test_revision02_monotonic_registry_contract(revision02_runner,tmp_path,mode):
    r=subprocess.run([str(revision02_runner),'contract-'+mode,str(tmp_path/'owned-udf')],capture_output=True,text=True,timeout=30)
    assert r.returncode==0,r.stdout+r.stderr
    assert 'ContractPassed=true;monotonic=true;rawValueRecorded=false'in r.stdout


@pytest.mark.parametrize('mode',['prefix','shrink','replacement','clear','paste','multiple','same','cross','history'])
def test_revision02_native_observed_edit_buffers_remain_protected(revision02_runner,tmp_path,mode):
    r=subprocess.run([str(revision02_runner),'native-edit-'+mode,str(tmp_path/'owned-udf')],capture_output=True,text=True,timeout=40)
    assert r.returncode==0,r.stdout+r.stderr
    if mode in ('prefix','same','cross','history'):
        reason='SHORT_COMMITTED_VALUE' if mode=='prefix' else 'TERMINAL_CONTINUITY_UNCONFIRMED'
        assert 'ExpectedOutcome=DENY;reason='+reason+';knownRetained=true;noResume=true;projectionBlocked=true'in r.stdout
        assert 'pageDataProtected=true;controlPlaneUnchanged=true;closedSerializerValid=true;cleanup=true;rawValueRecorded=false'in r.stdout
    else:
        assert 'NativePassed=true;pageDataProtected=true;controlPlaneUnchanged=true;closedSerializerValid=true;cleanup=true'in r.stdout
    assert not (tmp_path/'owned-udf').exists()


@pytest.mark.parametrize('case',range(6),ids=lambda i:'opaque-case-'+str(i))
def test_revision02_native_page_leaf_redaction_preserves_ipc_schema(revision02_runner,tmp_path,case):
    r=subprocess.run([str(revision02_runner),'native-schema-'+str(case),str(tmp_path/'owned-udf')],capture_output=True,text=True,timeout=40)
    assert r.returncode==0,r.stdout+r.stderr
    if case in (4,5):
        assert 'ExpectedOutcome=DENY;reason=SHORT_COMMITTED_VALUE;knownRetained=true;noResume=true;projectionBlocked=true'in r.stdout
    assert 'pageDataProtected=true;controlPlaneUnchanged=true;closedSerializerValid=true;cleanup=true'in r.stdout
