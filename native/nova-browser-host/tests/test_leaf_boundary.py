"""Private bounded leaf contract and real WebView2 projection, not DLP/LLM."""
from pathlib import Path
import subprocess
import pytest

@pytest.fixture(scope='session')
def leaf_boundary_runner(host_build,tmp_path_factory):
    work=tmp_path_factory.mktemp('leaf-boundary');feed=work/'empty';feed.mkdir()
    command=[str(host_build[0]),'build',str(Path(__file__).parent/'leaf_boundary_runner/runner.csproj'),'-c','Release','--source',str(feed),'-p:NuGetAudit=false','-p:HostBin='+str(host_build[1].parent),'-p:BaseIntermediateOutputPath='+str(work/'obj')+'/', '-p:OutputPath='+str(work/'bin')+'/', '--nologo']
    result=subprocess.run(command,capture_output=True,text=True,timeout=60)
    (work/'build.txt').write_text(result.stdout+result.stderr,encoding='utf-8')
    assert result.returncode==0,result.stdout+result.stderr
    return work/'bin/nova-browser-host-contract-tests.exe'

@pytest.mark.parametrize('mode',['short-exact','short-substring','two-leaves','host-separator','title','label','dialog','state','long-transient','long-committed','leaf-count-bound','leaf-length-bound','aggregate-bound','private-schema','unknown-leaf-kind'])
def test_leaf_boundary_contract(leaf_boundary_runner,tmp_path,mode):
    result=subprocess.run([str(leaf_boundary_runner),mode,str(tmp_path/'owned-udf')],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'LeafPassed=true;boundariesPreserved=true;rawValueRecorded=false'in result.stdout

@pytest.mark.parametrize('mode',['native-text','native-title','native-label','native-label-fragments','native-joins','native-example'])
def test_leaf_boundary_native(leaf_boundary_runner,tmp_path,mode):
    result=subprocess.run([str(leaf_boundary_runner),mode,str(tmp_path/'owned-udf')],capture_output=True,text=True,timeout=40)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'NativeLeafPassed=true;publicSchemaUnchanged=true;cleanup=true;rawValueRecorded=false'in result.stdout
    assert not(tmp_path/'owned-udf').exists()
