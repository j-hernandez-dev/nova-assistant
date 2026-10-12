"""One authorized B3 after namespace preflight. No C# or product edits."""
from pathlib import Path
import argparse, ctypes, hashlib, importlib.util, json, os, shutil

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("_unchanged_causal_bisection",HERE/"bisection_probe.py")
original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def prepare(context,b2):
    work=context/"build";work.mkdir(parents=True,exist_ok=False)
    shutil.copytree(b2/"build/bin",work/"bin")
    names=("WebView2Runtime.cs","ObservationRuntime.cs","TransferRuntime.cs","ExternalProtocolGuard.cs","ContextObserver.cs")
    for name in names:shutil.copyfile(b2/"build"/name,work/name)
    freeze=dict(CSharpCopies={n:sha(work/n)for n in names},B2Copies={n:sha(b2/"build"/n)for n in names},
                diagnosticDll=sha(work/"bin/nova-browser-host.dll"),B2Dll=sha(b2/"build/bin/nova-browser-host.dll"),
                sdkDll=sha(work/"bin/Microsoft.Web.WebView2.Core.dll"),harness=sha(Path(__file__)),CSharpModified=False,buildPerformed=False)
    assert freeze["CSharpCopies"]==freeze["B2Copies"]and freeze["diagnosticDll"]==freeze["B2Dll"]
    (context/"freeze_before_execution.json").write_text(json.dumps(freeze,indent=2))
    print(json.dumps(dict(stage="PREPARED_ONLY",CSharpEqual=True,DllEqual=True,effectiveExecutions=0)))

def run(context,parent,fixture):
    from local_cli.infrastructure.active_web.transfer_adapter import TransferHostClient
    from local_cli.infrastructure.active_web.host_ipc_protocol import ref
    from local_cli.infrastructure.active_web.webview2_adapter import _reparse
    assert parent.is_absolute()and parent.is_dir()and not parent.is_symlink()and not _reparse(parent)
    assert not list(parent.iterdir()),"New private parent must start empty"
    original_start=TransferHostClient.start
    original_typed=TransferHostClient.typed_call
    gates=dict(ownershipValidation=False,pipeCreated=False,runtimeConstructed=False,engineCreated=False,controlCreated=False,contentLoaded=False)
    call_rows=[];udf_meta={};effective=0
    def owned_start(client,*args,**kwargs):
        ref(client.session,"bws");ref(client.instance,"bhi")
        expected="nova_wv2_"+client.session+"_"+client.instance
        previous=client.udf;client.udf=parent/expected
        assert client.udf.is_absolute()and client.udf.name==expected and not client.udf.exists()
        # Writability proof before the host/engine/content. Delete-on-close,
        # using Win32 through ctypes avoids retaining any input/download bytes.
        marker=parent/("write-"+os.urandom(8).hex())
        kernel=ctypes.WinDLL("kernel32",use_last_error=True)
        kernel.CreateFileW.argtypes=[ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p]
        kernel.CreateFileW.restype=ctypes.c_void_p
        kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle.restype=ctypes.c_int
        handle=kernel.CreateFileW(str(marker),0x40000000,0,None,1,0x04000080,None)
        assert handle not in(None,ctypes.c_void_p(-1).value),"Private parent not writable"
        assert kernel.CloseHandle(handle)and not marker.exists()
        assert not client.udf.exists()and not list(parent.iterdir())
        udf_meta.update(schemaVersion=1,session=client.session,instance=client.instance,normalProductIds=True,
                        udfPath=str(client.udf),udfPathLength=len(str(client.udf)),udfBasename=expected,udfBasenameLength=len(expected),
                        oldUdfPathLength=len(str(previous)),shortParent=str(parent),parentLength=len(str(parent)),
                        parentExists=True,parentWritable=True,parentEmptyBeforeHost=True,udfFreshAbsentBeforeHost=True,
                        udfOutsideLongNamespace=True,hostBasenameContractMatched=True,validationChanged=False)
        (context/"b3_valid_udf.json").write_text(json.dumps(udf_meta,indent=2))
        result=original_start(client,*args,**kwargs)
        assert result["kind"]=="handshake"and result["hostInstanceRef"]==client.instance
        gates.update(ownershipValidation=True,pipeCreated=True,runtimeConstructed=True)
        # Runtime construction precedes handshake in unchanged LifecycleServer.
        call_rows.append(dict(phase="ORIGINAL_HOST_HANDSHAKE",success=True,hostPid=client.process.pid))
        return result
    def gated_call(client,payload,*args,**kwargs):
        nonlocal effective
        command=payload["command"]
        if command=="download":
            assert all(gates.values()),"Do not dispatch without validated ownership/pipe/runtime/engine/content"
            assert effective==0,"Exactly one authorized B3 activation"
            effective+=1
            call_rows.append(dict(phase="B3_EFFECTIVE_ACTIVATION",success=True,allPreconditionsConfirmed=True))
        result=original_typed(client,payload,*args,**kwargs)
        if command=="session_create":
            assert result["kind"]=="session_create";gates["engineCreated"]=True
            call_rows.append(dict(phase="ORIGINAL_SESSION_CREATE",success=True))
        elif command=="page_create":
            assert result["kind"]=="page_create";gates["controlCreated"]=True
            call_rows.append(dict(phase="ORIGINAL_PAGE_CREATE",success=True))
        elif command=="navigate_local":
            assert result["kind"]=="navigate_local";gates["contentLoaded"]=True
            call_rows.append(dict(phase="ORIGINAL_CONTENT_NAVIGATION_COMPLETED",success=True))
        return result
    TransferHostClient.start=owned_start;TransferHostClient.typed_call=gated_call
    try:return original.run(context,"B3",fixture,short_udf=None)
    finally:
        TransferHostClient.start=original_start;TransferHostClient.typed_call=original_typed
        (context/"b3_execution_gates.json").write_text(json.dumps(dict(gates=gates,callPhases=call_rows,effectiveNativeExecutions=effective),indent=2))

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("command",choices=("prepare","run"));p.add_argument("context");p.add_argument("--b2");p.add_argument("--parent");p.add_argument("--fixture")
    a=p.parse_args();context=Path(a.context).resolve()
    if a.command=="prepare":prepare(context,Path(a.b2).resolve())
    else:raise SystemExit(run(context,Path(a.parent).resolve(),Path(a.fixture)))
