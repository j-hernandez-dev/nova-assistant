"""Separate direct registry contracts and native channel-fault enforcement."""
from pathlib import Path
import subprocess
import pytest


@pytest.fixture(scope='session')
def sensitive_runner(host_build,tmp_path_factory):
    work=tmp_path_factory.mktemp('sensitive-runner');feed=work/'empty';feed.mkdir()
    cmd=[str(host_build[0]),'build',str(Path(__file__).parent/'sensitive_runner/runner.csproj'),'-c','Release','--source',str(feed),'-p:NuGetAudit=false','-p:HostBin='+str(host_build[1].parent),'-p:BaseIntermediateOutputPath='+str(work/'obj')+'/', '-p:OutputPath='+str(work/'bin')+'/', '--nologo']
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
    (work/'build.txt').write_text(r.stdout+r.stderr,encoding='utf-8')
    assert r.returncode==0,r.stdout+r.stderr
    return work/'bin/nova-browser-host-contract-tests.exe'


@pytest.mark.parametrize('mode',['survive','pending','replaced','url','escaped-url','dispose','isolation','length','count','pending-bound','total','lifetime','unavailable','no-eviction'])
def test_sensitive_registry_contract(sensitive_runner,tmp_path,mode):
    r=subprocess.run([str(sensitive_runner),mode,str(tmp_path/'private-udf')],capture_output=True,text=True,timeout=30)
    assert r.returncode==0,r.stdout+r.stderr
    assert mode+':PASS'in r.stdout


@pytest.mark.parametrize('mode',['native-unavailable','native-channel-loss','native-instrumentation-loss','native-registry-failure'])
def test_native_sensitive_tracking_fault_closes_boundary(sensitive_runner,tmp_path,mode):
    root=tmp_path/'private-udf'
    r=subprocess.run([str(sensitive_runner),mode,str(root)],capture_output=True,text=True,timeout=40)
    (tmp_path/'safe_fault_receipt.txt').write_text(r.stdout,encoding='utf-8')
    assert r.returncode==0,r.stdout+r.stderr
    assert 'resumeBlocked=true;observationBlocked=true;cleanup=true'in r.stdout
    assert not root.exists()


def test_native_registry_ownership_ends_with_real_session(sensitive_runner,tmp_path):
    root=tmp_path/'private-udf'
    r=subprocess.run([str(sensitive_runner),'native-session-lifecycle',str(root)],capture_output=True,text=True,timeout=40)
    assert r.returncode==0,r.stdout+r.stderr
    assert 'registryDisposed=true;newSessionIndependent=true;cleanup=true'in r.stdout
    assert not root.exists()and not Path(str(root)+'-next').exists()


def test_native_navigation_diagnostic_has_no_unhandled_capture(sensitive_runner,tmp_path):
    r=subprocess.run([str(sensitive_runner),'native-navigation-diagnosis',str(tmp_path/'private-udf')],capture_output=True,text=True,timeout=40)
    assert r.returncode==0,r.stdout+r.stderr
    assert 'knownValueAbsent=true'in r.stdout


def test_native_sensitive_redaction_preserves_closed_ipc_discriminator(sensitive_runner,tmp_path):
    r=subprocess.run([str(sensitive_runner),'native-structural-collision',str(tmp_path/'private-udf')],capture_output=True,text=True,timeout=40)
    assert r.returncode==0,r.stdout+r.stderr
    assert 'StructuralDiscriminatorChanged=false'in r.stdout
