"""Separate guard contract/native evidence. No network or Active Web claims."""
from datetime import datetime,timedelta,timezone
import json
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4

import pytest

from local_cli.infrastructure.active_web import guard_ipc as wire
from local_cli.infrastructure.active_web.guard_adapter import GuardWebView2Adapter
from local_cli.infrastructure.active_web.host_ipc_protocol import HostIpcError,opaque
from local_cli.core.security_audit import SecurityAuditRecord

ROOT=Path(__file__).resolve().parents[3]
MODES=('script','click','mailto','frame','popup','secondary','takeover',
       'audit-failure','registration-failure','secondary-failure','lost-guard','unexpected-dispose')

@pytest.fixture(scope='session')
def guard_runner(host_build,tmp_path_factory):
    work=tmp_path_factory.mktemp('guard-runner-build'); feed=work/'empty';feed.mkdir()
    command=[str(host_build[0]),'build',str(Path(__file__).parent/'guard_runner/guard_runner.csproj'),
        '-c','Release','--source',str(feed),'-p:NuGetAudit=false','-p:HostBin='+str(host_build[1].parent),
        '-p:BaseIntermediateOutputPath='+str(work/'obj')+'/', '-p:OutputPath='+str(work/'bin')+'/', '--nologo']
    r=subprocess.run(command,capture_output=True,text=True,timeout=60)
    (work/'build.txt').write_text(r.stdout+r.stderr,encoding='utf-8')
    assert r.returncode==0,r.stdout+r.stderr
    return work/'bin/nova-browser-host-contract-tests.exe'

@pytest.fixture
def registered_canary(guard_runner,tmp_path):
    """Authorized reversible HKCU harness registration, never product startup."""
    import winreg
    scheme='nova-aw8-guard-'+uuid4().hex
    key='Software\\Classes\\'+scheme
    sentinel=tmp_path/'launch-sentinel.txt'
    command=f'"{guard_runner}" --canary "{sentinel}" "%1"'
    changes={'hive':'HKCU','key':key,'values':{'':'URL: Nova benign certification canary','URL Protocol':''},'command':command}
    # UUID leaf must not collide. Never touch a handler belonging to the user.
    with pytest.raises(FileNotFoundError): winreg.OpenKey(winreg.HKEY_CURRENT_USER,key)
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,key,0,winreg.KEY_WRITE) as h:
        for name,value in changes['values'].items():winreg.SetValueEx(h,name,0,winreg.REG_SZ,value)
    for child in ('shell','shell\\open','shell\\open\\command'):
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,key+'\\'+child,0,winreg.KEY_WRITE) as h:
            if child.endswith('command'):winreg.SetValueEx(h,'',0,winreg.REG_SZ,command)
    evidence=dict(registration=changes,scheme=scheme,cleanupConfirmed=False)
    try:
        # Benign positive harness control: Windows must actually resolve and run
        # this registered handler. This deliberate launch is outside browser/
        # guard measurement. Preserve its PID separately; don't call it zero.
        os.startfile(scheme+':positive-control')
        end=time.monotonic()+10
        while not sentinel.exists() and time.monotonic()<end:time.sleep(.025)
        assert sentinel.exists(),'Registered handler positive control not observed'
        evidence['positiveControlHandlerPids']=[int(p) for p in sentinel.read_text().splitlines()]
        sentinel.rename(tmp_path/'positive-control-sentinel.txt')
        evidence['guardMeasurementStartedUtc']=datetime.now(timezone.utc).isoformat()
        yield scheme,sentinel,evidence
    finally:
        evidence['guardMeasurementEndedUtc']=datetime.now(timezone.utc).isoformat()
        evidence['handlerExecutionsDuringGuard']=[int(p) for p in sentinel.read_text().splitlines()] if sentinel.exists() else []
        evidence['sentinelAbsent']=not sentinel.exists()
        # Delete only our exact new leaf, with current contents verified. Unknown
        # changes make cleanup fail rather than deleting arbitrary state.
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key+'\\shell\\open\\command') as h:
            assert winreg.QueryValueEx(h,'')[0]==command
        for child in ('shell\\open\\command','shell\\open','shell',''):
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER,key+('\\'+child if child else ''))
        with pytest.raises(FileNotFoundError):winreg.OpenKey(winreg.HKEY_CURRENT_USER,key)
        evidence['cleanupConfirmed']=True
        (tmp_path/'canary.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')

@pytest.mark.parametrize('mode',MODES)
def test_registered_guard_native_matrix(guard_runner,registered_canary,tmp_path,mode):
    scheme,sentinel,evidence=registered_canary
    s,h=opaque('bws'),opaque('bhi');udf=tmp_path/('nova_wv2_'+s+'_'+h); report=tmp_path/'guard.json'
    command=[str(guard_runner),mode,str(udf),scheme,str(report),s,h]
    r=subprocess.run(command,capture_output=True,text=True,timeout=40)
    (tmp_path/'runner.txt').write_text(r.stdout+r.stderr,encoding='utf-8')
    assert r.returncode==0,r.stdout+r.stderr
    result=json.loads(report.read_text(encoding='utf-8'));m=result['metadata']
    assert result['cleanupConfirmed'] and not udf.exists()
    assert not sentinel.exists(),'HOST EFFECT: registered helper ran during guard window'
    if mode in ('registration-failure','secondary-failure','lost-guard','unexpected-dispose'):
        assert m['externalProtocolGuard']=='UNKNOWN'
        if mode not in ('lost-guard','unexpected-dispose'):assert result['error']=='GUARD_UNAVAILABLE' and result['usable'] is False
        else:assert 'LOST_GUARD_INVALIDATED' in result['stages']
        return
    assert result['stages'].index('CONTROL_CREATED_GUARD_INSTALLED') < result['stages'].index('CONTROLLED_CONTENT_LOADED')
    receipts=m['receipts'];assert len(receipts)==(2 if mode=='secondary' else 1)
    assert all(x['cancel'] is True and x['outcome']=='DENIED_PRE_EFFECT' for x in receipts)
    if mode=='audit-failure':
        assert m['auditGap'] and m['externalProtocolGuard']=='UNKNOWN'
        assert receipts[0]['durable'] is False and receipts[0]['recordId'] is None
        return
    assert m['externalProtocolGuard']=='HOST_PRE_EFFECT_DENY' and not m['auditGap']
    records=[SecurityAuditRecord.from_dict(json.loads(line)) for line in Path(str(udf)+'.guard-audit.jsonl').read_text().splitlines()]
    assert len(records)==len(receipts)
    for a,receipt in zip(records,receipts):
        scope=a.data['observationScope']
        assert a.tool_call_id is None and not {'grantId','approvalId'} & set(a.data)
        assert a.session_id==s and scope['hostInstanceRef']==h and scope['pageRef']==receipt['pageRef']
        assert scope['installationSequence']<scope['eventSequence'] and scope['cancel'] is True
        assert a.record_id==receipt['recordId'] and receipt['durable'] is True
        assert a.data['resource'].endswith(':') and 'synthetic-attempt' not in json.dumps(a.to_dict())
        assert receipt['reason']==('POPUP_DENIED_PRE_EFFECT' if mode=='popup' else 'EXTERNAL_PROTOCOL_GUARD_DENIAL')
        if mode in ('click','takeover','frame'):assert scope['userGesture'] is True,'Must be native gesture, not JS .click()'
    if mode=='secondary':assert len({x['pageRef'] for x in receipts})==2

def deadline():return datetime.now(timezone.utc)+timedelta(seconds=20)

def test_private_v3_same_host_read_only_guard_evidence(host_build,tmp_path):
    a=GuardWebView2Adapter(*host_build,tmp_path);s,p=opaque('bws'),opaque('bwp')
    a.create_context(s,deadline=deadline(),cancellation=None)
    try:
        a.create_page(s,p,deadline=deadline(),cancellation=None)
        m=a.guard_metadata(s,deadline=deadline())
        assert m['externalProtocolGuard']=='HOST_PRE_EFFECT_DENY' and m['policy']=='DENY_ALL'
        assert m['installations'][0]['pageRef']==p and m['receipts']==[]
        assert a.runtime_metadata(s,deadline=deadline())['requiredApiMetadata']['externalProtocolGuardCertified'] is False
        from local_cli.tools import get_default_tools
        assert not any(t.name.startswith('browser_') for t in get_default_tools())
    finally:assert a.close_context(s,deadline=deadline())

@pytest.mark.parametrize('channel',('crash','disconnect'))
def test_private_guard_host_loss_no_retry_no_fallback(host_build,tmp_path,channel):
    a=GuardWebView2Adapter(*host_build,tmp_path);s,p=opaque('bws'),opaque('bwp')
    a.create_context(s,deadline=deadline(),cancellation=None);a.create_page(s,p,deadline=deadline(),cancellation=None)
    c=a._sessions[s];pid=c.process.pid
    if channel=='crash':c.process.kill();c.process.wait(timeout=5)
    else:c.transport.close()
    with pytest.raises(Exception):a.guard_metadata(s,deadline=deadline())
    assert c.process.pid==pid and c.cleanup_confirmed and not c.udf.exists()
    with pytest.raises(Exception):a.page_metadata(s,p,deadline=deadline())

@pytest.mark.parametrize('command',('navigate','eval','remove_guard','allow_external','launch','takeover'))
def test_closed_guard_contract_no_authority(command):
    with pytest.raises(HostIpcError):wire.envelope(opaque('bws'),{'command':command})

@pytest.mark.parametrize('field',('grant','approval','uri','script','selector','origin','allow'))
def test_closed_guard_contract_no_payload_extension(field):
    m=wire.envelope(opaque('bws'),{'command':'guard_metadata'});m['payload'][field]='untrusted'
    with pytest.raises(HostIpcError):wire.encode(m)

def test_guard_source_cancel_first_no_relaunch_and_no_page_bridge():
    source=(ROOT/'native/nova-browser-host/ExternalProtocolGuard.cs').read_text(encoding='utf-8')
    body=source.split('private void Launch(',1)[1].split('{',1)[1].lstrip()
    assert body.startswith('e.Cancel = true;')
    assert 'e.Handled = true;' in source
    for forbidden in ('Process.Start(', 'ShellExecute(', 'GetDeferral(', 'Cancel = false', 'AddHostObjectToScript('):assert forbidden not in source
