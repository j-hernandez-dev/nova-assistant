"""Four-case diagnosis only; never loaded by product or ordinary tests.

Separate diagnostic build adds read-only, scalar native branch observers to
external copies of two pinned source files. Product sources stay byte-intact.
No altered condition/assignment/return, timeout, fixture, request or authority.
"""
from pathlib import Path
import functools
import hashlib
import json
import subprocess
import threading
import time
from xml.sax.saxutils import escape
import pytest

HERE=Path(__file__).resolve().parent
HOST=HERE.parents[1]
ROOT=HOST.parents[1]
_records=[]
_counts={}
_specimen=None
_report_root=None

def _record(kind,**metadata):
    if len(_records)<256:
        _records.append(dict(sequence=len(_records)+1,nanoseconds=time.monotonic_ns(),kind=kind,metadata=metadata))

def _edit(text,before,after):
    assert text.count(before)==1,'Diagnostic anchor must identify exactly one unchanged branch'
    return text.replace(before,after)

def _build(host_build,work):
    work.mkdir(exist_ok=True)
    source=(HOST/'TransferRuntime.cs').read_text(encoding='utf-8')
    originals={'TransferRuntime.cs':source}
    anchors=[
        ('e.Response=view.Environment.CreateWebResourceResponse(stream,exists?200:404,exists?"OK":"Not Found","Content-Type: "+mime+"\\r\\nContent-Length: "+data.Length+"\\r\\nCache-Control: no-store\\r\\n");',
         'DownloadTrace.Resource(name,exists?200:404,data.Length);'),
        ('e.ResultFilePath=path;e.Cancel=false;',
         'DownloadTrace.Record("PRIVATE_DOWNLOAD_DESTINATION_ASSIGNED",new{targetChars=path.Length,parentExists=Directory.Exists(Path.GetDirectoryName(path)),targetExists=File.Exists(path)});'),
        ('void Check()\n            {',
         'DownloadTrace.State(op,"DOWNLOAD_CHECK_NATIVE_STATE");'),
        ('download=new DownloadSlot(uri,"wvd_"+Guid.NewGuid().ToString("N"),maxBytes,deadline);',
         'DownloadTrace.Record("DOWNLOAD_SLOT_CREATED",new{download.Token,remainingMilliseconds=deadline-DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()});'),
        ('var op=await download.Done.Task.WaitAsync(TimeSpan.FromMilliseconds(Math.Max(1,deadline-DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()-250)));',
         'DownloadTrace.State(op,"NATIVE_COMPLETION_CONFIRMED");'),
        ('using var file=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.Read);\n                Protocol.Need(file.Length==op.BytesReceived',
         'DownloadTrace.Record("PRIVATE_DOWNLOAD_FILE_OPENED");'),
    ]
    # The final anchor needs its observer before the unchanged continuation.
    for before,statement in anchors:
        if before.startswith('using var file='):
            after=before.replace('\n                Protocol.Need', '\n                '+statement+'\n                Protocol.Need')
        else:after=before+'\n                '+statement
        source=_edit(source,before,after)
    source=_edit(source,'catch(Exception error)\n            {',
                 'catch(Exception error)\n            {\n                DownloadTrace.Record("DOWNLOAD_CATCH",new{errorType=error.GetType().Name,hresult=error.HResult});\n                DownloadTrace.State(download.Operation,"DOWNLOAD_CATCH_NATIVE_STATE");')
    source=_edit(source,'finally {download?.Operation?.Cancel();download=null;busy=false;}',
                 'finally {DownloadTrace.State(download?.Operation,"DOWNLOAD_FINALLY_BEFORE_CANCEL");download?.Operation?.Cancel();download=null;busy=false;}')
    source=_edit(source,'public void StopTransfers(){download?.Operation?.Cancel();Invalidate(false);}',
                 'public void StopTransfers(){DownloadTrace.State(download?.Operation,"CLEANUP_STOP_TRANSFERS");download?.Operation?.Cancel();Invalidate(false);}')
    (work/'TransferRuntime.cs').write_text(source,encoding='utf-8')
    runtime=(HOST/'WebView2Runtime.cs').read_text(encoding='utf-8');originals['WebView2Runtime.cs']=runtime
    runtime=_edit(runtime,'if(localContentRoot is not null)observationRuntime.ConfigureLocal(localContentRoot,"nova-local.invalid");',
                  'if(localContentRoot is not null){await DownloadTrace.Attach(controller.CoreWebView2,udf,page);observationRuntime.ConfigureLocal(localContentRoot,"nova-local.invalid");}')
    runtime=_edit(runtime,'await OnUi(() =>\n        {\n            if (environment is not null) ObserveProcesses();',
                  'await OnUi(() =>\n        {\n            DownloadTrace.Record("BROWSER_CLEANUP_BEGIN");\n            if (environment is not null) ObserveProcesses();')
    runtime=_edit(runtime,'Protocol.Need(!Directory.Exists(udf), "CLEANUP_UNCONFIRMED");\n        return new { kind = "session_close", closed = true, cleanupConfirmed = true };',
                  'Protocol.Need(!Directory.Exists(udf), "CLEANUP_UNCONFIRMED");\n        DownloadTrace.Record("BROWSER_CLEANUP_CONFIRMED");DownloadTrace.Flush();\n        return new { kind = "session_close", closed = true, cleanupConfirmed = true };')
    (work/'WebView2Runtime.cs').write_text(runtime,encoding='utf-8')
    target=work/'diagnostic.targets'
    target.write_text('<Project><ItemGroup><Compile Remove="TransferRuntime.cs;WebView2Runtime.cs" />'+
                      ''.join('<Compile Include="'+escape(str(p).replace('\\','/'))+'" />' for p in (work/'TransferRuntime.cs',work/'WebView2Runtime.cs',HERE/'DownloadTrace.cs'))+
                      '</ItemGroup></Project>',encoding='utf-8')
    command=[str(host_build[0]),'build',str(HOST/'nova-browser-host.csproj'),'-c','Release','--source',str(host_build[1].parent.parent/'empty-feed'),
             '-p:NuGetAudit=false','-p:UseAppHost=false','-p:CustomAfterMicrosoftCommonTargets='+str(target),
             '-p:BaseIntermediateOutputPath='+str(work/'obj')+'/', '-p:OutputPath='+str(work/'bin')+'/', '--nologo']
    r=subprocess.run(command,capture_output=True,text=True,timeout=60)
    (work/'build.txt').write_text(r.stdout+r.stderr,encoding='utf-8')
    assert r.returncode==0,r.stdout+r.stderr
    pins=dict(originalSources={n:hashlib.sha256((HOST/n).read_bytes()).hexdigest() for n in originals},
              normalizedSourceHashes={n:hashlib.sha256(s.encode()).hexdigest() for n,s in originals.items()},
              generatedSources={n:hashlib.sha256((work/n).read_bytes()).hexdigest() for n in originals},
              productSourcesModified=False,conditionsReturnsAssignmentsChanged=False,observersOnly=True)
    (work/'instrumentation.json').write_text(json.dumps(pins,indent=2),encoding='utf-8')
    return host_build[0],work/'bin/nova-browser-host.dll'

@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(fixturedef,request):
    global _specimen,_report_root
    outcome=yield
    if fixturedef.argname=='host_build' and outcome.excinfo is None:
        build=outcome.get_result()
        diagnostic=_build(build,request.getfixturevalue('tmp_path_factory').mktemp('download-diagnostic-build'))
        fixturedef.cached_result=(diagnostic,fixturedef.cached_result[1],None)
        outcome.force_result(diagnostic)
    if fixturedef.argname=='specimen5' and outcome.excinfo is None:
        _specimen=outcome.get_result();_report_root=_specimen['tmp']
        c=_specimen['port']._sessions[_specimen['session']]
        _record('SPECIMEN_READY',sessionRef=_specimen['session'],pageRef=_specimen['page'],hostPid=c.process.pid,
                stagingState='CREATED_PRIVATE',stagingEntries=len(_specimen['staging']._files))

@pytest.fixture(autouse=True)
def diagnostic_metadata(monkeypatch):
    global _specimen,_report_root
    from local_cli.infrastructure.active_web.transfer_adapter import WebView2TransferAdapter,TransferHostClient
    from local_cli.infrastructure.active_web.download_staging import BrowserDownloadStaging
    from local_cli.application.browser_transfers import BrowserTransferService
    from local_cli.application.tool_runtime import ToolRuntime
    from local_cli.application.interactions import ApprovalGate
    _records.clear()
    _counts.clear();_specimen=None;_report_root=None
    def wrap(cls,name,kind,selector=lambda args,kwargs:{}):
        original=getattr(cls,name)
        @functools.wraps(original)
        def observed(*args,**kwargs):
            metadata=selector(args,kwargs)
            if kind=='IPC_TASK' and metadata['command']=='transfer_metadata':
                _counts['existingTransferMetadataPolls']=_counts.get('existingTransferMetadataPolls',0)+1
                return original(*args,**kwargs)
            _record(kind+'_ENTER',**metadata)
            try:
                result=original(*args,**kwargs)
                extra={}
                if hasattr(result,'outcome'):extra.update(outcome=result.outcome.value,effectState=result.effect_state.value)
                if hasattr(result,'status'):extra['toolStatus']=result.status.value
                if isinstance(result,dict) and result.get('kind')=='download':extra.update(nativeOutcome=result['outcome'],nativeStarted=result['started'])
                if isinstance(result,dict) and 'downloadRef'in result:extra.update(downloadRef=result['downloadRef'],stagingState=result['status'])
                _record(kind+'_RETURN',**metadata,**extra);return result
            except BaseException as e:
                _record(kind+'_EXCEPTION',**metadata,errorType=type(e).__name__);raise
        monkeypatch.setattr(cls,name,observed)
    wrap(WebView2TransferAdapter,'dispatch','ADAPTER_DISPATCH',lambda a,k:dict(action=a[1].action_kind.value,operationId=a[1].operation_id))
    wrap(TransferHostClient,'typed_call','IPC_TASK',lambda a,k:dict(command=a[1].get('command'),operationId=k.get('operation_id')))
    wrap(BrowserTransferService,'prepare','TRANSFER_PREPARE',lambda a,k:dict(action=a[2].action_kind.value,operationId=a[2].operation_id))
    wrap(BrowserDownloadStaging,'stage','STAGING_FINALIZATION',lambda a,k:dict(size=len(a[2])))
    wrap(ToolRuntime,'execute','TOOL_RUNTIME',lambda a,k:dict(operationId=a[1].operation_id))
    wrap(ApprovalGate,'resolve','APPROVAL_RESOLVE',lambda a,k:dict(approved=k.get('approved')))
    original_join=threading.Thread.join
    def join(thread,timeout=None):
        _record('THREAD_JOIN_ENTER',taskId=thread.ident,timeout=timeout,alive=thread.is_alive())
        result=original_join(thread,timeout)
        _record('THREAD_JOIN_RETURN',taskId=thread.ident,timeout=timeout,alive=thread.is_alive());return result
    monkeypatch.setattr(threading.Thread,'join',join)
    original_hook=threading.excepthook
    def exception(args):
        _record('WORKER_EXCEPTION',taskId=args.thread.ident,errorType=args.exc_type.__name__);original_hook(args)
    monkeypatch.setattr(threading,'excepthook',exception)
    yield

def _write(phase):
    if _report_root is None:return
    d=_specimen;c=d['port']._sessions[d['session']]
    data=dict(schemaVersion=1,phase=phase,events=list(_records),counters=dict(_counts),hostPid=c.process.pid,
              processExited=c.process.poll()is not None,udfExists=c.udf.exists(),cleanupConfirmed=c.cleanup_confirmed,
              stagingState='PRESENT' if d['staging']._root.exists() else 'REMOVED',stagingEntries=len(d['staging']._files),rawContentRecorded=False)
    (_report_root/('python_'+phase+'.json')).write_text(json.dumps(data,indent=2),encoding='utf-8')

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item,call):
    outcome=yield;report=outcome.get_result()
    if report.when in('call','teardown'):
        _record('PYTEST_'+report.when.upper(),outcome=report.outcome)
        _write(report.when)
