using System.Reflection;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;
using NovaBrowserHost;

// Test-only host producer; sensitive values never leave this process.
if(args.Length!=2)return 1;
string mode=args[0],root=args[1];
SensitiveBoundaryFailureReason? firstReason=null;
SensitiveBoundaryFailureDiagnostics.HarnessObserver=f=>firstReason??=f.Reason;
try
{
    if(mode is "native-confirmed-submit-resume" or "native-live-checkpoint-resume")
    {
        // Additive positive paths. No change to any historical HTML/driver.
        string content=Path.Combine(Path.GetDirectoryName(root)!,"local");Directory.CreateDirectory(content);
        File.WriteAllText(Path.Combine(content,"index.html"),"<!doctype html><form id=f><input type=password id=p></form><span id=out></span><script>f.addEventListener('submit',e=>e.preventDefault())</script>");
        using var engine=new WebView2Runtime(root,"bhi_"+Guid.NewGuid().ToString("N"),localContentRoot:content,maxTransferBytes:4096);
        string page="bwp_"+Guid.NewGuid().ToString("N"),sensitive=Guid.NewGuid().ToString("N");
        SensitiveTerminalReason? witnessed=null;
        SensitiveTerminalDiagnostics.HarnessObserver=e=>{if(e.Kind==SensitiveTerminalDiagnosticKind.COMMIT_ACCEPTED)witnessed=e.Reason;};
        try
        {
            await engine.CreateSession();await engine.CreatePage(page);await engine.NavigateLocal(page,"index.html");await engine.BeginTakeover(page);
            var registry=Access.Registry(engine);
            await Access.Ui(engine,async()=>{await Access.View(engine,page).ExecuteScriptAsync("(()=>{p.value="+JsonSerializer.Serialize(sensitive)+";p.dispatchEvent(new Event('input',{bubbles:true}));out.textContent=p.value;})()");return true;});
            await Access.WaitState(engine,()=>Access.Controls(registry).Any(s=>s.SensitiveObserved&&s.Active&&s.Current==sensitive));
            if(Committed(registry,sensitive)||witnessed is not null)return 51;
            if(mode=="native-confirmed-submit-resume")
            {
                await Access.Ui(engine,async()=>{await Access.View(engine,page).ExecuteScriptAsync("f.requestSubmit()");return true;});
                await Access.WaitState(engine,()=>Committed(registry,sensitive)&&witnessed==SensitiveTerminalReason.SUBMIT);
            }
            await Access.Ui(engine,()=>{Access.Button(engine).PerformClick();return Task.FromResult(true);});
            await engine.EndTakeover();
            var state=JsonSerializer.SerializeToElement(await engine.TakeoverState());
            var observation=JsonSerializer.SerializeToElement(await engine.Capture(page,24,1800,128));
            if(!Committed(registry,sensitive)||firstReason is not null||state.GetProperty("humanActive").GetBoolean()||state.GetProperty("contextEpoch").GetInt64()!=1)return 52;
            if(mode=="native-live-checkpoint-resume"&&witnessed!=SensitiveTerminalReason.CHECKPOINT)return 53;
            if(observation.GetProperty("kind").GetString()!="capture"||JsonSerializer.Serialize(observation).Contains(sensitive,StringComparison.Ordinal)||!observation.GetProperty("text").GetString()!.Contains("[INPUT_REDACTED]"))return 54;
            await engine.CloseSession(15000);if(Directory.Exists(root)||!Denied(registry.Require))return 55;
            Console.WriteLine("ExpectedOutcome=RESUME_CONFIRMED;strongWitness=true;committed=true;freshObservation=true;knownValueAbsent=true;cleanup=true;rawValueRecorded=false");return 0;
        }
        finally{if(Directory.Exists(root))await engine.CloseSession(15000);}
    }
    if(mode is "native-retired-lineage" or "native-late-terminal")
    {
        string content=Path.Combine(Path.GetDirectoryName(root)!,"local");Directory.CreateDirectory(content);
        File.WriteAllText(Path.Combine(content,"index.html"),"<!doctype html><input type=password id=p>");
        File.WriteAllText(Path.Combine(content,"other.html"),"<!doctype html><title>Controlled</title>");
        using var engine=new WebView2Runtime(root,"bhi_"+Guid.NewGuid().ToString("N"),localContentRoot:content,maxTransferBytes:4096);
        string page="bwp_"+Guid.NewGuid().ToString("N"),sensitive=Guid.NewGuid().ToString("N");
        try
        {
            await engine.CreateSession();await engine.CreatePage(page);await engine.NavigateLocal(page,"index.html");await engine.BeginTakeover(page);
            var registry=Access.Registry(engine);
            await Access.Ui(engine,async()=>{await Access.View(engine,page).ExecuteScriptAsync("(()=>{p.value="+JsonSerializer.Serialize(sensitive)+";p.dispatchEvent(new Event('input',{bubbles:true}));})()");return true;});
            await Access.WaitState(engine,()=>Access.Controls(registry).Any(s=>s.SensitiveObserved&&s.Active&&s.Current==sensitive));
            await Access.Ui(engine,async()=>{await Access.View(engine,page).ExecuteScriptAsync("location.href='other.html'");return true;});
            await Access.WaitState(engine,()=>Access.Controls(registry).Any(s=>s.TerminalContinuityUnconfirmed&&!s.Active&&s.Current==sensitive));
            bool knownTransient=!Committed(registry,sensitive)&&registry.Redact(sensitive)=="[INPUT_REDACTED]";
            bool lateRejected=false;
            if(mode=="native-late-terminal")
            {
                await Access.Ui(engine,()=>{
                    var controls=(Dictionary<SensitiveControlIdentity,SensitiveControlState>)typeof(SensitiveValueRegistry).GetField("controls",BindingFlags.NonPublic|BindingFlags.Instance)!.GetValue(registry)!;
                    var retired=controls.First(k=>!k.Value.Active&&k.Value.Current==sensitive);
                    try{lateRejected=registry.ConfirmTerminal(retired.Key,retired.Value.Revision+1,sensitive,SensitiveTerminalReason.CHECKPOINT) is null;}
                    catch(IpcFailure failure){lateRejected=failure.Code=="SECRET_BOUNDARY_UNCONFIRMED";}
                    return Task.FromResult(true);
                });
                if(!lateRejected||Committed(registry,sensitive))return 61;
            }
            await Access.Ui(engine,()=>{Access.Button(engine).PerformClick();return Task.FromResult(true);});
            bool denied=false;try{await engine.EndTakeover();}catch(IpcFailure e){denied=e.Code=="SECRET_BOUNDARY_UNCONFIRMED";}
            bool projectionBlocked=false;try{await engine.Capture(page,24,1800,128);}catch(IpcFailure){projectionBlocked=true;}
            if(!knownTransient||!denied||!projectionBlocked||mode=="native-retired-lineage"&&firstReason!=SensitiveBoundaryFailureReason.TERMINAL_CONTINUITY_UNCONFIRMED)return 41;
            await engine.CloseSession(15000);if(Directory.Exists(root))return 42;
            if(mode=="native-late-terminal")Console.WriteLine("LateTerminalRejected=true;realRetiredDocument=true;commit=false;resume=false;projectionBlocked=true;rawValueRecorded=false");
            Console.WriteLine("RetiredLineageDenied=true;reason=TERMINAL_CONTINUITY_UNCONFIRMED;notShortCommitted=true;projectionBlocked=true;cleanup=true;rawValueRecorded=false");return 0;
        }
        finally{if(Directory.Exists(root))await engine.CloseSession(15000);}
    }
    if(mode.StartsWith("native-short-",StringComparison.Ordinal))
    {
        string content=Path.Combine(Path.GetDirectoryName(root)!,"local");Directory.CreateDirectory(content);
        File.WriteAllText(Path.Combine(content,"index.html"),"<!doctype html><input type=password id=p>");
        using var engine=new WebView2Runtime(root,"bhi_"+Guid.NewGuid().ToString("N"),localContentRoot:content,maxTransferBytes:4096);
        string page="bwp_"+Guid.NewGuid().ToString("N");
        try
        {
            await engine.CreateSession();await engine.CreatePage(page);await engine.NavigateLocal(page,"index.html");await engine.BeginTakeover(page);
            string nativeValue=new('u',int.Parse(mode[^1..]));
            await Access.Ui(engine,async()=>{await Access.View(engine,page).ExecuteScriptAsync("(()=>{const p=document.getElementById('p');p.value="+JsonSerializer.Serialize(nativeValue)+";p.dispatchEvent(new Event('change',{bubbles:true}));})()");return true;});
            await Access.Ui(engine,()=>{Access.Button(engine).PerformClick();return Task.FromResult(true);});
            bool denied=false;try{await engine.EndTakeover();}catch(IpcFailure e){denied=e.Code=="SECRET_BOUNDARY_UNCONFIRMED";}
            if(!denied||firstReason!=SensitiveBoundaryFailureReason.SHORT_COMMITTED_VALUE)return 31;
            await engine.CloseSession(15000);if(Directory.Exists(root))return 32;
            Console.WriteLine("NativeShortDenied=true;reason=SHORT_COMMITTED_VALUE;cleanup=true;rawValueRecorded=false");return 0;
        }
        finally{if(Directory.Exists(root))await engine.CloseSession(15000);}
    }
    using var r=new SensitiveValueRegistry();string pageId="page-a",generation=Guid.NewGuid().ToString("N"),value=Guid.NewGuid().ToString("N")+"-terminal!";
    r.RegisterDocument(pageId,generation);var id=r.Identity(pageId,generation,"control-a");
    SensitiveTerminalSnapshot Terminal(long rev,string v,SensitiveTerminalReason reason=SensitiveTerminalReason.CHECKPOINT)=>r.ConfirmTerminal(id,rev,v,reason)??throw new Exception("NO_PROOF");
    switch(mode)
    {
        case "growth":case "late":case "duplicate":
            for(int i=1;i<=value.Length;i++)r.Observe(id,i,value[..i]);
            var full=Terminal(value.Length,value);r.Observe(id,1,value[..1]);
            if(mode=="duplicate")r.Observe(id,2,value[..2]);r.Commit(full);
            if(!Committed(r,value)||r.Redact(value[..1])!="[INPUT_REDACTED]")return 2;break;
        case "backspace":
            r.Observe(id,1,value);r.Observe(id,2,value[..2]);if(!Denied(()=>r.Commit(Terminal(2,value[..2])))||firstReason!=SensitiveBoundaryFailureReason.SHORT_COMMITTED_VALUE)return 3;break;
        case "replacement":case "paste":case "clear-rewrite":
            r.Observe(id,1,value);string next="replacement-"+value;
            if(mode=="clear-rewrite")r.Observe(id,2,"");
            r.Commit(Terminal(3,next));if(!Committed(r,next)||r.Redact(value)!="[INPUT_REDACTED]")return 4;break;
        case "multiple-controls":
            r.Observe(id,1,value);var sibling=r.Identity(pageId,generation,"control-b");r.Observe(sibling,1,"sibling-"+value);
            r.Commit(Terminal(1,value));if(Committed(r,"sibling-"+value)||!Committed(r,value))return 5;break;
        case "old-document":
            r.ObserveInput(id,1,value,SensitiveInputSignal.PAGEHIDE);var old=Terminal(1,value,SensitiveTerminalReason.CHECKPOINT);r.RetireDocument(pageId,generation);
            string newer=Guid.NewGuid().ToString("N");r.RegisterDocument(pageId,newer);var other=r.Identity(pageId,newer,"control-a");r.Observe(other,1,"new-"+value);
            if(r.Observe(id,2,value[..1])||!Denied(()=>r.Commit(old)))return 6;break;
        case "no-snapshot-retire":
            r.Observe(id,1,value);r.RetireDocument(pageId,generation);if(Committed(r,value)||r.Redact(value)!="[INPUT_REDACTED]")return 7;break;
        case "no-snapshot-checkpoint":
            r.Observe(id,1,value);if(!Denied(()=>r.RequireCheckpointCoverage(pageId,generation,[]))||Committed(r,value)||firstReason==SensitiveBoundaryFailureReason.SHORT_COMMITTED_VALUE)return 8;break;
        case "stale-snapshot":case "after-terminal":
            r.Observe(id,1,value);var prior=Terminal(1,value);r.Observe(id,2,"new-"+value);
            if(!Denied(()=>r.Commit(prior))||Committed(r,value))return 9;break;
        case "owner":case "page":case "generation":
            var wrong=id with{Owner=mode=="owner"?"other":id.Owner,Page=mode=="page"?"other":id.Page,Generation=mode=="generation"?"other":id.Generation};
            if(!Denied(()=>r.Observe(wrong,1,value)))return 10;break;
        case "revision-conflict":
            r.Observe(id,1,value);if(!Denied(()=>r.Observe(id,1,"other-"+value)))return 11;break;
        case "forged":
            r.Observe(id,1,value);Terminal(1,value);if(!Denied(()=>r.Commit(new(id,1,value,SensitiveTerminalReason.CHECKPOINT))))return 12;break;
        case "short-1":case "short-2":case "short-3":
            string shortValue=new('u',int.Parse(mode[^1..]));r.Observe(id,1,shortValue);if(!Denied(()=>r.Commit(Terminal(1,shortValue)))||firstReason!=SensitiveBoundaryFailureReason.SHORT_COMMITTED_VALUE)return 13;break;
        case "reason-change":case "reason-blur":case "reason-pagehide":
            r.Observe(id,1,value);r.ObserveInput(id,2,value,Enum.Parse<SensitiveInputSignal>(mode[7..].ToUpperInvariant()));
            var weakState=((Dictionary<SensitiveControlIdentity,SensitiveControlState>)typeof(SensitiveValueRegistry).GetField("controls",BindingFlags.NonPublic|BindingFlags.Instance)!.GetValue(r)!)[id];
            if(Committed(r,value)||weakState.Terminal is not null||weakState.Committed is not null||weakState.Revision!=2||weakState.Current!=value||r.Redact(value)!="[INPUT_REDACTED]")return 14;break;
        case "reason-submit":case "reason-checkpoint":
            var reason=Enum.Parse<SensitiveTerminalReason>(mode[7..].ToUpperInvariant());r.Observe(id,1,value);r.Commit(Terminal(1,value,reason));if(!Committed(r,value))return 14;break;
        case "zero-revision":
            if(!Denied(()=>r.Observe(id,0,value)))return 15;break;
        case "expired":
            TimeSpan elapsed=TimeSpan.Zero;using(var timed=new SensitiveValueRegistry(()=>elapsed)){timed.Activate();elapsed=SensitiveValueRegistry.MaxLifetime+TimeSpan.FromSeconds(1);if(!Denied(timed.Require))return 16;}break;
        case "retired-stale-known":
            r.Observe(id,1,value);r.RetireDocument(pageId,generation);r.Observe(id,2,"late-"+value);if(r.Redact("late-"+value)!="[INPUT_REDACTED]"||Committed(r,"late-"+value))return 17;break;
        default:return 20;
    }
    Console.WriteLine("OrderingPassed=true;provenance=true;monotonic=true;rawValueRecorded=false");return 0;
}
catch(Exception e){Console.WriteLine("FailureCode="+(e is IpcFailure ipc?ipc.Code:"UNCLASSIFIED")+";rawValueRecorded=false");return 99;}
static bool Denied(Action work){try{work();return false;}catch(IpcFailure e){return e.Code=="SECRET_BOUNDARY_UNCONFIRMED";}}
static bool Committed(SensitiveValueRegistry r,string value)=>((Dictionary<string,SensitiveValueRegistry.ValueClass>)typeof(SensitiveValueRegistry).GetField("values",BindingFlags.NonPublic|BindingFlags.Instance)!.GetValue(r)!).TryGetValue(value,out var state)&&state==SensitiveValueRegistry.ValueClass.COMMITTED;
static class Access
{
    private const BindingFlags Flags=BindingFlags.NonPublic|BindingFlags.Instance;
    internal static CoreWebView2 View(WebView2Runtime e,string page)=>((Dictionary<string,CoreWebView2Controller>)typeof(WebView2Runtime).GetField("pages",Flags)!.GetValue(e)!)[page].CoreWebView2;
    internal static Button Button(WebView2Runtime e)=>(Button)typeof(WebView2Runtime).GetField("returnControl",Flags)!.GetValue(e)!;
    internal static SensitiveValueRegistry Registry(WebView2Runtime e)=>(SensitiveValueRegistry)typeof(WebView2Runtime).GetField("secrets",Flags)!.GetValue(e)!;
    internal static IEnumerable<SensitiveControlState> Controls(SensitiveValueRegistry r)=>((Dictionary<SensitiveControlIdentity,SensitiveControlState>)typeof(SensitiveValueRegistry).GetField("controls",Flags)!.GetValue(r)!).Values;
    internal static async Task WaitState(WebView2Runtime e,Func<bool> condition)
    {
        var deadline=DateTime.UtcNow.AddSeconds(2);
        while(DateTime.UtcNow<deadline){if(await Ui(e,()=>Task.FromResult(condition())))return;await Task.Delay(10);}
        throw new Exception("CONTROL_STATE_NOT_OBSERVED");
    }
    internal static Task<T> Ui<T>(WebView2Runtime e,Func<Task<T>> work)=>(Task<T>)typeof(WebView2Runtime).GetMethod("OnUi",Flags)!.MakeGenericMethod(typeof(T)).Invoke(e,[work])!;
}
