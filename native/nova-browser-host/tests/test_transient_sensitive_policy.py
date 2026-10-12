"""Prospective bounded transient policy; native synthetic input, not LLM/DLP."""
from pathlib import Path
import subprocess
import pytest


@pytest.fixture(scope='session')
def transient_policy_runner(host_build,tmp_path_factory):
    work=tmp_path_factory.mktemp('transient-policy-runner');feed=work/'empty';feed.mkdir()
    command=[str(host_build[0]),'build',str(Path(__file__).parent/'transient_policy_runner/runner.csproj'),'-c','Release','--source',str(feed),'-p:NuGetAudit=false','-p:HostBin='+str(host_build[1].parent),'-p:BaseIntermediateOutputPath='+str(work/'obj')+'/', '-p:OutputPath='+str(work/'bin')+'/', '--nologo']
    r=subprocess.run(command,capture_output=True,text=True,timeout=60)
    (work/'build.txt').write_text(r.stdout+r.stderr,encoding='utf-8')
    assert r.returncode==0,r.stdout+r.stderr
    return work/'bin/nova-browser-host-contract-tests.exe'


@pytest.mark.parametrize('mode',['transient-short','transient-long','committed-long','committed-short-1','committed-short-2','committed-short-3','promotion','terminal-retire','terminal-checkpoint','history-clear','short-retire-denied','short-checkpoint-denied','no-eviction','lifecycle'])
def test_bounded_transient_policy_contract(transient_policy_runner,tmp_path,mode):
    r=subprocess.run([str(transient_policy_runner),'contract-'+mode,str(tmp_path/'owned-udf')],capture_output=True,text=True,timeout=30)
    assert r.returncode==0,r.stdout+r.stderr
    assert 'ContractPassed=true;monotonic=true;rawValueRecorded=false'in r.stdout


@pytest.mark.parametrize('mode',['short-preserved','short-exact','transient-long','committed-long','committed-short','navigation','cross','history','submit','schema'])
def test_bounded_transient_policy_native(transient_policy_runner,tmp_path,mode):
    r=subprocess.run([str(transient_policy_runner),'native-'+mode,str(tmp_path/'owned-udf')],capture_output=True,text=True,timeout=40)
    assert r.returncode==0,r.stdout+r.stderr
    assert 'NativePassed=true;pageDataProtected=true;controlPlaneUnchanged=true;closedSerializerValid=true;cleanup=true;rawValueRecorded=false'in r.stdout
    assert not (tmp_path/'owned-udf').exists()

