"""C07 direct producer/provenance contracts and independent native short denial.
Values stay C# host-private; no raw values, DOM or exception data exported.
"""
from pathlib import Path
import subprocess
import pytest

@pytest.fixture(scope='session')
def terminal_ordering_runner(host_build,tmp_path_factory):
    work=tmp_path_factory.mktemp('terminal-ordering');feed=work/'empty';feed.mkdir()
    command=[str(host_build[0]),'build',str(Path(__file__).parent/'terminal_ordering_runner/runner.csproj'),'-c','Release','--source',str(feed),'-p:NuGetAudit=false','-p:HostBin='+str(host_build[1].parent),'-p:BaseIntermediateOutputPath='+str(work/'obj')+'/', '-p:OutputPath='+str(work/'bin')+'/', '--nologo']
    result=subprocess.run(command,capture_output=True,text=True,timeout=60)
    (work/'build.txt').write_text(result.stdout+result.stderr,encoding='utf-8')
    assert result.returncode==0,result.stdout+result.stderr
    return work/'bin/nova-browser-host-contract-tests.exe'

MODES=['growth','late','duplicate','backspace','replacement','paste','clear-rewrite','multiple-controls','old-document','no-snapshot-retire','no-snapshot-checkpoint','stale-snapshot','after-terminal','owner','page','generation','revision-conflict','forged','short-1','short-2','short-3','reason-change','reason-blur','reason-submit','reason-pagehide','reason-checkpoint','zero-revision','expired','retired-stale-known']

@pytest.mark.parametrize('mode',MODES)
def test_terminal_ordering_contract(terminal_ordering_runner,tmp_path,mode):
    result=subprocess.run([str(terminal_ordering_runner),mode,str(tmp_path/'owned-udf')],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'OrderingPassed=true;provenance=true;monotonic=true;rawValueRecorded=false'in result.stdout

@pytest.mark.parametrize('length',[1,2,3])
def test_real_short_terminal_denial(terminal_ordering_runner,tmp_path,length):
    result=subprocess.run([str(terminal_ordering_runner),'native-short-'+str(length),str(tmp_path/'owned-udf')],capture_output=True,text=True,timeout=40)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'NativeShortDenied=true;reason=SHORT_COMMITTED_VALUE;cleanup=true;rawValueRecorded=false'in result.stdout
    assert not(tmp_path/'owned-udf').exists()

def test_real_retired_lineage_without_terminal_source_denies_resume(terminal_ordering_runner,tmp_path):
    root=tmp_path/'owned-udf'
    result=subprocess.run([str(terminal_ordering_runner),'native-retired-lineage',str(root)],capture_output=True,text=True,timeout=40)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'RetiredLineageDenied=true;reason=TERMINAL_CONTINUITY_UNCONFIRMED;notShortCommitted=true;projectionBlocked=true;cleanup=true;rawValueRecorded=false'in result.stdout
    assert not root.exists()

@pytest.mark.parametrize('source',['confirmed-submit','live-checkpoint'])
def test_real_confirmed_terminal_can_resume(terminal_ordering_runner,tmp_path,source):
    root=tmp_path/'owned-udf'
    result=subprocess.run([str(terminal_ordering_runner),'native-'+source+'-resume',str(root)],capture_output=True,text=True,timeout=40)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'ExpectedOutcome=RESUME_CONFIRMED;strongWitness=true;committed=true;freshObservation=true;knownValueAbsent=true;cleanup=true;rawValueRecorded=false'in result.stdout
    assert not root.exists()
