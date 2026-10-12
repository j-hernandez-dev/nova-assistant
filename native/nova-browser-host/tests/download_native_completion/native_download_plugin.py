"""Single-run completion of missing native metadata, not product or certification.

Reuses the already-authorized builder/wrappers in an isolated module instance;
only its observer-source location points at this additive diagnostic version.
Old files and evidence stay byte-intact. No request, fixture or timeout changes.
"""
from pathlib import Path
import importlib.util
import json
import os
import struct
import time
import pytest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('_prior_download_diagnosis',HERE.parent/'download_diagnosis/plugin.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
prior.HERE=HERE # test-only observer Compile Include; HOST/product project unchanged
diagnostic_metadata=prior.diagnostic_metadata

def read_native(client):
    raw=Path(str(client.udf)+'.native-live.bin').read_bytes()
    integer=lambda at:struct.unpack_from('<i',raw,at)[0]
    assert integer(0)==0x4e444c36 and integer(4)==1
    assert integer(8)==client.process.pid and integer(12)==os.getpid()
    count=integer(24);assert 0<=count<=256 and integer(28)==0
    rows=[]
    for i in range(count):
        at=256+i*4096;size=integer(at);assert 0<size<=4092
        rows.append(json.loads(raw[at+4:at+4+size].decode()))
    return dict(hostPid=integer(8),ownerPid=integer(12),counterFrequency=struct.unpack_from('<q',raw,16)[0],events=rows,overflow=False)

@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(fixturedef,request):
    outcome=yield
    if fixturedef.argname=='host_build' and outcome.excinfo is None:
        build=outcome.get_result()
        diagnostic=prior._build(build,request.getfixturevalue('tmp_path_factory').mktemp('native-download-build'))
        fixturedef.cached_result=(diagnostic,fixturedef.cached_result[1],None);outcome.force_result(diagnostic)
    if fixturedef.argname=='specimen5' and outcome.excinfo is None:
        prior._specimen=outcome.get_result();prior._report_root=prior._specimen['tmp']
        d=prior._specimen;c=d['port']._sessions[d['session']]
        prior._record('SPECIMEN_READY',sessionRef=d['session'],pageRef=d['page'],hostPid=c.process.pid,stagingState='CREATED_PRIVATE',stagingEntries=len(d['staging']._files))

@pytest.fixture(autouse=True)
def native_observer_required(diagnostic_metadata,specimen5,monkeypatch):
    """Hard pre-body gate. A build/cache error cannot silently use ordinary host."""
    d=specimen5;c=d['port']._sessions[d['session']]
    ready=json.loads(Path(str(c.udf)+'.native-ready.json').read_text())
    assert ready['hostPid']==c.process.pid and ready['ownerPid']==os.getpid()
    assert ready['browserSessionRef']==d['session'] and ready['pageRef']==d['page']
    assert ready['downloadStartingSubscribed'] is True and ready['domainsReady'] is True
    initial=read_native(c)
    assert any(e['kind']=='OBSERVER_READY_BEFORE_CONTENT'for e in initial['events'])
    prior._record('PRE_BODY_NATIVE_OBSERVER_CONFIRMED',hostPid=c.process.pid)
    (d['tmp']/'observer_pre_body.json').write_text(json.dumps(dict(ready=ready,pythonCounterImplementation=time.get_clock_info('monotonic').implementation,
        preBodyNanoseconds=time.monotonic_ns(),rawContentRecorded=False),indent=2),encoding='utf-8')
    from local_cli.infrastructure.active_web.transfer_adapter import TransferHostClient
    original=TransferHostClient.typed_call
    def observed(client,payload,**kwargs):
        result=original(client,payload,**kwargs)
        if payload.get('command')=='transfer_metadata' and any(e['kind']=='DOWNLOAD_DENIED'for e in result['events']):
            prior._record('DOWNLOAD_DENIAL_METADATA_DELIVERED',hostPid=client.process.pid)
        return result
    monkeypatch.setattr(TransferHostClient,'typed_call',observed)
    import threading
    join=threading.Thread.join
    def at_join(thread,timeout=None):
        result=join(thread,timeout)
        if timeout==8:
            start=time.monotonic_ns();native=read_native(c);end=time.monotonic_ns()
            (d['tmp']/'native_at_join8.json').write_text(json.dumps(dict(workerAlive=thread.is_alive(),readerStartNanoseconds=start,
                readerEndNanoseconds=end,native=native,rawContentRecorded=False),indent=2),encoding='utf-8')
        return result
    monkeypatch.setattr(threading.Thread,'join',at_join)
    yield

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item,call):
    outcome=yield;report=outcome.get_result()
    if report.when not in('call','teardown') or prior._report_root is None:return
    prior._record('PYTEST_'+report.when.upper(),outcome=report.outcome);prior._write(report.when)
    d=prior._specimen;c=d['port']._sessions[d['session']]
    native=read_native(c)
    (d['tmp']/('native_'+report.when+'.json')).write_text(json.dumps(native,indent=2),encoding='utf-8')
