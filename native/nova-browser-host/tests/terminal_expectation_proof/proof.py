"""Private scalar proof, not a product API or authority."""
from pathlib import Path
import struct
import subprocess
import os
import pytest
from local_cli.infrastructure.active_web.host_ipc_protocol import HostIpcError
from local_cli.core.active_web_lifecycle import BrowserLifecycleError

HERE=Path(__file__).resolve().parent

def build_proof_host(host_build,work,*,diagnostic=False):
    work.mkdir();target=work/'proof.targets'
    target.write_text('<Project><ItemGroup><Compile Include="'+(HERE/'ContinuityProofSink.cs').as_posix()+'" /></ItemGroup></Project>',encoding='utf-8')
    product=HERE.parents[1]
    project=product/'tests/diagnostic_host/diagnostic.csproj' if diagnostic else product/'nova-browser-host.csproj'
    source=host_build[1].parent.parent/'empty-feed'
    command=[str(host_build[0]),'build',str(project),'-c','Release','--source',str(source),'-p:NuGetAudit=false',
             '-p:UseAppHost=false','-p:HostBin='+str(host_build[1].parent),
             '-p:CustomAfterMicrosoftCommonTargets='+str(target),
             '-p:BaseIntermediateOutputPath='+str(work/'obj')+'/', '-p:OutputPath='+str(work/'bin')+'/', '--nologo']
    result=subprocess.run(command,capture_output=True,text=True,timeout=60)
    (work/'build.txt').write_text(result.stdout+result.stderr,encoding='utf-8')
    assert result.returncode==0,result.stdout+result.stderr
    return host_build[0],work/'bin/nova-browser-host.dll'

def read_proof(d):
    client=d['port']._sessions[d['session']]
    data=Path(str(client.udf)+'.continuity-proof.bin').read_bytes()
    integer=lambda at:struct.unpack_from('<i',data,at)[0]
    long=lambda at:struct.unpack_from('<q',data,at)[0]
    text=lambda at,n:data[at:at+n].split(b'\0',1)[0].decode('utf-8')
    assert integer(0)==0x4e564135 and integer(4)==1
    assert integer(8)==client.process.pid and integer(12)==os.getpid() and integer(164)==0
    count=integer(160);assert 0<=count<=64
    records=[dict(generation=text(256+i*128,32),control=text(288+i*128,64),revision=long(352+i*128),
                  length=integer(360+i*128),terminals=integer(364+i*128),commits=integer(368+i*128),retired=integer(372+i*128)) for i in range(count)]
    return dict(hostPid=integer(8),ownerPid=integer(12),reason=integer(16),failureGeneration=text(20,32),
                failureControl=text(64,64),failureRevision=long(128),terminalReason=integer(136),records=records)

def assert_lost_terminal_denial(d,t):
    from test_webview2_transfers import deadline,capture
    before=read_proof(d)
    retired=[r for r in before['records'] if r['retired'] and r['length']>0]
    # Nonempty current at RetireControl entails actual prior Add/Observe in
    # the pinned monotonic registry, not a fixture-only lifecycle assertion.
    assert retired and all(r['revision']>0 and r['terminals']==0 and r['commits']==0 for r in retired)
    epoch=d['manager'].session(d['owner'],d['session']).browser_context_epoch
    state=d['port'].takeover_state(d['session'],deadline=deadline())
    assert state['humanActive'] and state['humanCompleted'] and not state['humanAborted']
    with pytest.raises(HostIpcError)as failure:
        d['takeover'].finish(d['owner'],t['takeoverRef'],actor=d['human'],authenticated=True)
    assert failure.value.code=='SECRET_BOUNDARY_UNCONFIRMED'
    after=read_proof(d)
    assert after['reason']==13 and after['terminalReason']==-1
    assert any(r['generation']==after['failureGeneration'] and r['control']==after['failureControl'] and
               r['revision']==after['failureRevision'] and r['terminals']==0 and r['commits']==0 for r in retired)
    assert d['manager'].session(d['owner'],d['session']).browser_context_epoch==epoch
    record=d['manager']._sessions[d['session']]
    assert record.takeover_operation==t['operationId']
    with pytest.raises(BrowserLifecycleError):capture(d)
    assert all(page.active_observation_ref is None for page in record.pages.values())
    audit=Path(str(d['port']._sessions[d['session']].udf)+'.guard-audit.jsonl')
    if audit.exists():assert b'test-only-'not in audit.read_bytes()
    return dict(expectedOutcome='DENY_TERMINAL_CONTINUITY_UNCONFIRMED',publicError=failure.value.code,
                internalReason='TERMINAL_CONTINUITY_UNCONFIRMED',knownValueRetained=True,
                observedSensitiveGenerationRetired=True,strongTerminalSourcePresent=False,
                agentResumed=False,freshObservationPublished=False,rawValueRecorded=False)
