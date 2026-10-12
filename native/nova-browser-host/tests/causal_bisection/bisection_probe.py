"""Bounded B1 -> B2 -> optional B3. External copies only; no baseline rerun."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, os, shutil, subprocess
from xml.sax.saxutils import escape

HERE=Path(__file__).resolve().parent
PRODUCT=HERE.parents[1]
DOTNET=Path("C:/Program Files/dotnet/dotnet.exe")
BARE="function(){this.click();return true;}"
spec=importlib.util.spec_from_file_location("_frozen_p1_bisection",HERE.parent/"product_context_pair/paired_probe.py")
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def change(text,old,new):return prior.change(text,old,new)
def build(context,label,p1_build,sdk_feed):
    work=context/"build";work.mkdir(parents=True,exist_ok=False)
    feed=work/"feed";feed.mkdir()
    shutil.copyfile(sdk_feed/"microsoft.web.webview2.1.0.4258.31.nupkg",feed/"microsoft.web.webview2.1.0.4258.31.nupkg")
    expected={"WebView2Runtime.cs":"16915c923d8031a174d5f45adfeb8464db9e5432dc5976d703cb4cd154bc7ccf","ObservationRuntime.cs":"34c0f09484647db7b52abbf9e167ef0fa080125c218826f3f1db05ec44db5fd5","TransferRuntime.cs":"047779b3755666b48996e8bb043e6246c6769d8e4daa0c0729367fae9f9975ec"}
    for name,digest in expected.items():assert sha(p1_build/name)==digest,"P1 copy drift"
    native=(p1_build/"WebView2Runtime.cs").read_text()
    dom=(p1_build/"ObservationRuntime.cs").read_text()
    transfer=(p1_build/"TransferRuntime.cs").read_text()
    # Common safe endpoint. Native subscription remains in place; only its
    # post-DownloadStarting body is replaced. No staging/completion invocation.
    start=transfer.index("    private void DownloadStarting(")
    end=transfer.index("    public async Task<object> Download(",start)
    transfer=transfer[:start]+"""    private void DownloadStarting(object? sender,CoreWebView2DownloadStartingEventArgs e)
    {
        e.Cancel=true;e.Handled=true;
    }
"""+transfer[end:]
    # Explicit defaults keep warnings-as-errors intact after the diagnostic
    # callback removes all post-event assignments. No pre-event behavior change.
    transfer=change(transfer,'public CoreWebView2DownloadOperation? Operation;','public CoreWebView2DownloadOperation? Operation=null;')
    transfer=change(transfer,'public bool Consumed;','public bool Consumed=false;')
    surfaces=["COMMON_POST_EVENT_DOWNLOAD_CALLBACK_DENY_ONLY"]
    if label in ("B1","B2-A"):
        old='var r=await Call(p.Value.B.ObjectId,ObservationScripts.Perform,[new{value=new{expected=p.Value.B.Meta,action="CLICK",payload="",destination=(string?)null}}]);'
        transfer=change(transfer,old,'var r=await Call(p.Value.B.ObjectId,"'+BARE+'",[]);')
        transfer=change(transfer,'if(r.TryGetProperty("stale",out _))return DownloadReport(true,"FAILED_NO_EFFECT_CONFIRMED");','if(r.ValueKind==JsonValueKind.Object&&r.TryGetProperty("stale",out _))return DownloadReport(true,"FAILED_NO_EFFECT_CONFIRMED");')
        surfaces+=["F3_BARE_ACTIVATION_OVER_SAME_OBJECT","BOOLEAN_RETURN_ADAPTATION_ONLY"]
    if label=="B1":
        a=transfer.index('        view.AddWebResourceRequestedFilter("https://nova-local.invalid/*"')
        b=transfer.index("        view.SaveFileSecurityCheckStarting",a)
        transfer=transfer[:a]+"        BisectionProvider.Attach(view);\n"+transfer[b:]
        surfaces+=["F4_F5_MICROPROBE_A_STATIC_URI_PROVIDER"]
    files={"WebView2Runtime.cs":native,"ObservationRuntime.cs":dom,"TransferRuntime.cs":transfer}
    if label in ("B2-B","B3"):
        native=change(native,'if(maxTransferBytes>0)await observationRuntime.InstallSensitiveTracking();','// Diagnostic F2: no product sensitive-tracking script/receivers installed.')
        native=change(native,'            controller.CoreWebView2.ProcessFailed += (_, _) => failed = true;','            // Diagnostic F2: ProcessFailed subscription omitted.')
        a=dom.index("        view.NavigationStarting+=")
        b=dom.index("    public void ConfigureLocal(",a)
        dom=dom[:a]+"    }\n"+dom[b:]
        transfer=change(transfer,'        view.SaveFileSecurityCheckStarting+=(_,e)=>TransferEvent(new{kind="FILE_SECURITY_CHECK",extension=secrets.AuditSafe(e.FileExtension),defaultPolicy=!e.SuppressDefaultPolicy,cancelled=e.CancelSave});','        // Diagnostic F2: SaveFileSecurityCheckStarting subscription omitted.')
        guard=(PRODUCT/"ExternalProtocolGuard.cs").read_text()
        guard=change(guard,'            view.LaunchingExternalUriScheme += Launch;','            // Diagnostic F2: controlled fixed page only; no external launch handler installed.')
        guard=change(guard,'            view.NewWindowRequested += Popup;','            // Diagnostic F2: popup handler not installed.')
        files={"WebView2Runtime.cs":native,"ObservationRuntime.cs":dom,"TransferRuntime.cs":transfer,"ExternalProtocolGuard.cs":guard}
        surfaces+=["F2_PRE_DOWNLOAD_HANDLER_AND_SENSITIVE_INSTRUMENTATION_OMISSION"]
    if label=="B3":surfaces+=["F1_SIMPLE_SHORT_NEW_UDF_PATH_IN_HARNESS"]
    observer=(HERE.parent/"product_context_pair/ContextObserver.cs").read_text()
    old='Record("DOWNLOAD_STARTING_OBSERVED",new{e.Cancel,e.Handled,operationCreated=e.DownloadOperation is not null});eventSignal!.Set();'
    observer=change(observer,old,'var operation=e.DownloadOperation;e.Cancel=true;e.Handled=true;\n            Record("DOWNLOAD_STARTING_OBSERVED",new{e.Cancel,e.Handled,operationCreated=operation is not null});eventSignal!.Set();')
    observer=observer.replace("// Product handler owns Cancel/Handled. This observer never changes them.","// Diagnostic endpoint: observe then cancel; never evaluate completion.")
    observer=change(observer,'if(function!=ObservationScripts.Perform&&function!=ObservationScripts.Meta', 'if(function!="'+BARE+'"&&function!=ObservationScripts.Perform&&function!=ObservationScripts.Meta')
    observer=change(observer,'Record(function==ObservationScripts.Perform?"PRE_ACTIVATION_PERFORM":"TARGET_CALL",','Record(function==ObservationScripts.Perform||function=="'+BARE+'"?"PRE_ACTIVATION_PERFORM":"TARGET_CALL",')
    files["ContextObserver.cs"]=observer
    for name,data in files.items():(work/name).write_text(data)
    extra=[HERE/"BisectionProvider.cs"] if label=="B1" else []
    includes=[*[work/n for n in files],*extra]
    removed=[n for n in files if n!="ContextObserver.cs"]
    target=work/"observer.targets"
    target.write_text('<Project><ItemGroup><Compile Remove="'+';'.join(removed)+'" />'+''.join('<Compile Include="'+escape(str(p).replace('\\','/'))+'" />'for p in includes)+'</ItemGroup></Project>')
    command=[str(DOTNET),"build",str(PRODUCT/"nova-browser-host.csproj"),"-c","Release","--source",str(feed),"-p:NuGetAudit=false","-p:UseAppHost=false","-p:CustomAfterMicrosoftCommonTargets="+str(target),"-p:BaseIntermediateOutputPath="+str(work/"obj")+"/","-p:OutputPath="+str(work/"bin")+"/","--nologo"]
    env=dict(os.environ,DOTNET_CLI_TELEMETRY_OPTOUT="1",DOTNET_NOLOGO="1",DOTNET_CLI_HOME=str(work/"cli"),NUGET_PACKAGES=str(work/"packages"),MSBuildEnableWorkloadResolver="false")
    r=subprocess.run(command,capture_output=True,text=True,timeout=60,env=env);(work/"build.txt").write_text(r.stdout+r.stderr)
    assert r.returncode==0,r.stdout+r.stderr
    freeze=dict(label=label,surfaces=surfaces,originalP1Copies=expected,generated={n:sha(work/n)for n in files},newHarness={str(p):sha(p)for p in(HERE/"bisection_probe.py",HERE/"BisectionProvider.cs")},DLL=sha(work/"bin/nova-browser-host.dll"),SDK=sha(work/"bin/Microsoft.Web.WebView2.Core.dll"),productProgram=sha(PRODUCT/"Program.cs"),productModified=False,readyBeforeExecution=True)
    (work/"freeze.json").write_text(json.dumps(freeze,indent=2))
    print(json.dumps(dict(stage="BUILD_ONLY",label=label,DLL=freeze["DLL"],effectiveExecutions=0)))

def run(context,label,fixture,short_udf=None):
    if short_udf is not None:
        assert label=="B3" and short_udf.is_absolute() and not short_udf.exists()
    from local_cli.infrastructure.active_web.transfer_adapter import TransferHostClient
    original_start=TransferHostClient.start
    def diagnostic_start(client,*args,**kwargs):
        if short_udf is not None:client.udf=short_udf
        return original_start(client,*args,**kwargs)
    TransferHostClient.start=diagnostic_start
    try:return prior.run(context,"P1",fixture,129)
    finally:TransferHostClient.start=original_start

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("command",choices=("build","run"));p.add_argument("context");p.add_argument("--label",choices=("B1","B2-A","B2-B","B3"),required=True);p.add_argument("--p1-build");p.add_argument("--sdk-feed");p.add_argument("--fixture");p.add_argument("--short-udf")
    a=p.parse_args();context=Path(a.context).resolve()
    if a.command=="build":build(context,a.label,Path(a.p1_build),Path(a.sdk_feed))
    else:raise SystemExit(run(context,a.label,Path(a.fixture),Path(a.short_udf).resolve()if a.short_udf else None))
