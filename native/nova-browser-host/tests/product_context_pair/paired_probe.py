"""Maximum P1/P2, same real Nova host project/program with read-only observer.
No Policy/Approval/ToolRuntime/staging. No changed primitive, headers or timeout.
"""
from pathlib import Path
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
import shutil
import struct
import subprocess
import threading
import time
from xml.sax.saxutils import escape

HERE=Path(__file__).resolve().parent
HOST=HERE.parents[1]
DOTNET=Path('C:/Program Files/dotnet/dotnet.exe')

def change(text,anchor,replacement):
    assert text.count(anchor)==1,'Exactly one pinned source anchor required'
    return text.replace(anchor,replacement)

def build(root,sdk_feed):
    work=root/'build';work.mkdir();feed=work/'feed';feed.mkdir()
    shutil.copyfile(Path(sdk_feed)/'microsoft.web.webview2.1.0.4258.31.nupkg',feed/'microsoft.web.webview2.1.0.4258.31.nupkg')
    native=(HOST/'WebView2Runtime.cs').read_text()
    native=change(native,'environment = await factory.Environment(udf, options);','ContextObserver.EnvironmentOptions(options);\n            environment = await factory.Environment(udf, options);')
    native=change(native,'if(maxTransferBytes>0)await observationRuntime.InstallSensitiveTracking();','ContextObserver.Attach(controller.CoreWebView2,udf,page);ContextObserver.Controller(controller);\n            if(maxTransferBytes>0)await observationRuntime.InstallSensitiveTracking();')
    dom=(HOST/'ObservationRuntime.cs').read_text()
    dom=change(dom,'using var doc=JsonDocument.Parse(json);return doc.RootElement.Clone();','using var doc=JsonDocument.Parse(json);var value=doc.RootElement.Clone();ContextObserver.CdpReply(method,parameters,value);return value;')
    dom=change(dom,'var r=await Cdp("Runtime.callFunctionOn",','ContextObserver.Call(id,function,arguments);\n        var r=await Cdp("Runtime.callFunctionOn",')
    transfer=(HOST/'TransferRuntime.cs').read_text()
    transfer=change(transfer,'var u=new Uri(e.Request.Uri);','ContextObserver.ResourceStart(e.Request.Uri);\n            var u=new Uri(e.Request.Uri);')
    anchor='e.Response=view.Environment.CreateWebResourceResponse(stream,exists?200:404,exists?"OK":"Not Found","Content-Type: "+mime+"\\r\\nContent-Length: "+data.Length+"\\r\\nCache-Control: no-store\\r\\n");'
    transfer=change(transfer,anchor,anchor+'\n            ContextObserver.ResourceDone(name,exists?200:404,data.Length);')
    transfer=change(transfer,'string uri=(await Call(p.Value.B.ObjectId,"function(){return this.href;}" )).GetString()!;',
                    'ContextObserver.Target(p.Value.B.ObjectId,p.Value.B.Meta);\n            string uri=(await Call(p.Value.B.ObjectId,"function(){return this.href;}" )).GetString()!;')
    files={'WebView2Runtime.cs':native,'ObservationRuntime.cs':dom,'TransferRuntime.cs':transfer}
    for name,data in files.items():(work/name).write_text(data)
    target=work/'observer.targets'
    target.write_text('<Project><ItemGroup><Compile Remove="'+';'.join(files)+'" />'+''.join('<Compile Include="'+escape(str(p).replace('\\','/'))+'" />'for p in (*[work/n for n in files],HERE/'ContextObserver.cs'))+'</ItemGroup></Project>')
    command=[str(DOTNET),'build',str(HOST/'nova-browser-host.csproj'),'-c','Release','--source',str(feed),'-p:NuGetAudit=false','-p:UseAppHost=false',
             '-p:CustomAfterMicrosoftCommonTargets='+str(target),'-p:BaseIntermediateOutputPath='+str(work/'obj')+'/', '-p:OutputPath='+str(work/'bin')+'/', '--nologo']
    env=dict(os.environ,DOTNET_CLI_TELEMETRY_OPTOUT='1',DOTNET_NOLOGO='1',DOTNET_CLI_HOME=str(work/'cli'),NUGET_PACKAGES=str(work/'packages'),MSBuildEnableWorkloadResolver='false')
    r=subprocess.run(command,capture_output=True,text=True,timeout=60,env=env)
    (work/'build.txt').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stdout+r.stderr
    (work/'sources.json').write_text(json.dumps(dict(original={n:hashlib.sha256((HOST/n).read_bytes()).hexdigest()for n in files},generated={n:hashlib.sha256((work/n).read_bytes()).hexdigest()for n in files},noProductSourceModified=True,realProductProgramUsed=True),indent=2))

def rows(client):
    data=Path(str(client.udf)+'.context.bin').read_bytes()
    integer=lambda at:struct.unpack_from('<i',data,at)[0]
    assert integer(0)==0x50435438 and integer(4)==1 and integer(8)==client.process.pid and integer(12)==os.getpid() and integer(24)==0
    count=integer(20);assert 0<=count<=256
    result=[]
    for i in range(count):
        at=128+i*4096;size=integer(at);assert 0<size<=4092
        result.append(json.loads(data[at+4:at+4+size]))
    return result

def run(root,mode,fixture,managed_length):
    from local_cli.infrastructure.active_web.transfer_adapter import TransferHostClient
    from local_cli.infrastructure.active_web.host_ipc_protocol import opaque
    case=root/mode;case.mkdir();content=case/'content';content.mkdir()
    shutil.copyfile(fixture,content/'index.html')
    for name in ('payload.txt','download.txt'):(content/name).write_bytes(b'Local approved download cobalt-631.')
    base=case/'managed';suffix='m'*(managed_length-len(str(base))-1);assert suffix
    managed=base/suffix;managed.mkdir(parents=True);assert len(str(managed))==managed_length
    class Client(TransferHostClient):local_content_root=content;max_transfer_bytes=4096
    client=Client(DOTNET,root/'build/bin/nova-browser-host.dll',opaque('bws'),managed)
    page=opaque('bwp');outcome='PROBE_ERROR';worker=None;code=None;start=None;event_handle=None
    try:
        client.start();client.typed_call(dict(command='session_create'),page=None,timeout_ms=5000)
        client.typed_call(dict(command='page_create'),page=page,timeout_ms=5000)
        ready=json.loads(Path(str(client.udf)+'.context-ready.json').read_text())
        assert ready['hostPid']==client.process.pid and ready['ownerPid']==os.getpid() and ready['pageRef']==page and ready['observerActive']
        client.typed_call(dict(command='navigate_local',path='index.html'),page=page,timeout_ms=5000)
        capture=client.typed_call(dict(command='capture',maxElements=24,maxText=1800,maxField=128),page=page,timeout_ms=5000)
        targets=[e for e in capture['elements']if e['name']=='Approved specimen download'and 'DOWNLOAD'in e['capabilities']];assert len(targets)==1
        binding=targets[0]['binding'];proof=client.typed_call(dict(command='resolve',binding=binding),page=page,timeout_ms=5000);assert proof['found']
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenEventW.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.LPCWSTR];kernel.OpenEventW.restype=wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];kernel.WaitForSingleObject.restype=wintypes.DWORD
        kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
        event_handle=kernel.OpenEventW(0x00100000,False,ready['signal']);assert event_handle
        result={}
        def execute():
            try:client.typed_call(dict(command='download',binding=binding,maxBytes=4096),page=page,timeout_ms=25000,started=lambda:None)
            except Exception as e:result['errorType']=type(e).__name__
        worker=threading.Thread(target=execute);start=time.monotonic_ns();worker.start()
        native_wait=kernel.WaitForSingleObject(event_handle,25000);assert native_wait in(0,258)
        captured=rows(client);outcome='PASS'if any(e['kind']=='DOWNLOAD_STARTING_OBSERVED'for e in captured)else'FAIL'
        assert any(e['kind']=='PRE_ACTIVATION_PERFORM'for e in captured),'Product click must actually be dispatched'
        (case/'context_preboundary.json').write_text(json.dumps(dict(mode=mode,outcome=outcome,hostPid=client.process.pid,requestStartNanoseconds=start,observerReady=ready,events=captured,
            target=targets[0],fixtureSha256=hashlib.sha256((content/'index.html').read_bytes()).hexdigest(),managedRootChars=managed_length,udfChars=len(str(client.udf))),indent=2))
        # No result/staging/completion diagnosis. Ordinary teardown only.
        if worker.is_alive():client.transport.close()
        worker.join(5)
    except Exception as e:
        code=type(e).__name__
    finally:
        if event_handle:kernel.CloseHandle(event_handle)
        client._cleanup()
        if worker and worker.is_alive():worker.join(5)
        report=dict(mode=mode,outcome=outcome,errorType=code,caseExecutions=1,productModified=False,primitiveModified=False,
                    cleanupConfirmed=client.cleanup_confirmed,postDownloadStartingInvestigated=False)
        (case/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
    return 0 if code is None else 2

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('build','run'));p.add_argument('root');p.add_argument('--mode',choices=('P1','P2'));p.add_argument('--fixture');p.add_argument('--managed-length',type=int);p.add_argument('--sdk-feed')
    a=p.parse_args();root=Path(a.root).resolve();root.mkdir(exist_ok=True)
    if a.command=='build':build(root,a.sdk_feed)
    else:raise SystemExit(run(root,a.mode,Path(a.fixture),a.managed_length))
