"""Host-fixed terminal primitives, real WebView2. No model FORM_SUBMIT tool."""
from pathlib import Path
import subprocess
import pytest
from .conftest import record

@pytest.fixture(scope='session')
def terminal5(host_build,tmp_path_factory):
    work=tmp_path_factory.mktemp('b5-terminal');feed=work/'empty';feed.mkdir()
    r=subprocess.run([str(host_build[0]),'build',str(Path(__file__).parent/'terminal_runner/runner.csproj'),
        '-c','Release','--source',str(feed),'-p:NuGetAudit=false','-p:HostBin='+str(host_build[1].parent),
        '-p:BaseIntermediateOutputPath='+str(work/'obj')+'/', '-p:OutputPath='+str(work/'bin')+'/', '--nologo'],
        capture_output=True,text=True,timeout=60)
    (work/'build.log').write_text(r.stdout+r.stderr,encoding='utf-8');assert r.returncode==0,r.stdout+r.stderr
    return work/'bin/nova-browser-host-contract-tests.exe'

@pytest.mark.parametrize('mode',['native-confirmed-submit-resume','native-live-checkpoint-resume',
    'native-short-1','native-short-2','native-short-3','native-retired-lineage','native-late-terminal'])
def test_real_terminal_sources_short_retired_and_late(terminal5,tmp_path,mode):
    root=tmp_path/'owned-udf'
    r=subprocess.run([str(terminal5),mode,str(root)],capture_output=True,text=True,timeout=40)
    assert r.returncode==0,r.stdout+r.stderr
    assert 'rawValueRecorded=false' in r.stdout and not root.exists()
    if mode=='native-late-terminal':assert 'LateTerminalRejected=true;realRetiredDocument=true;commit=false;resume=false' in r.stdout
    record(mode,dict(exitCode=0,receipt=r.stdout.strip(),cleanupConfirmed=True,
        source='Existing fixed native terminal harness + additive late-event case; not model JS/FORM_SUBMIT'))
