using System.Reflection;
using Microsoft.Web.WebView2.Core;
using NovaBrowserHost;

// Certification executable; NOT a product option/IPC command/page bridge.
if(args.Length!=2)return 1;
string mode=args[0],root=args[1];
if(!mode.StartsWith("native-",StringComparison.Ordinal))
{
    using var r=new SensitiveValueRegistry();string value="harness-"+Guid.NewGuid().ToString("N");
    switch(mode)
    {
        case "survive":r.Input("page:world:node",value,false);r.Retire("page:world:");r.Checkpoint();if(r.Redact("prefix "+value).Contains(value))return 2;break;
        case "pending":r.Input("1",value,false);if(r.Redact(value).Contains(value))return 2;break;
        case "replaced":r.Input("1",value,false);r.Input("1","different-"+value,false);r.Checkpoint();if(r.Redact(value).Contains(value))return 2;break;
        case "url":r.Input("1",value,false);if(r.PublicUrl("https://local.invalid/"+value+"?token="+value+"#"+value).Contains(value))return 2;break;
        case "escaped-url":value+=" /+";r.Input("1",value,false);if(r.PublicUrl("https://local.invalid/"+Uri.EscapeDataString(value)).Contains(Uri.EscapeDataString(value)))return 2;break;
        case "dispose":r.Input("1",value,false);r.Dispose();if(!Denied(()=>r.Redact(value)))return 2;break;
        case "isolation":r.Input("1",value,false);using(var other=new SensitiveValueRegistry())if(other.Redact(value)!=value)return 2;break;
        case "length":if(!Denied(()=>r.Input("1",new string('x',SensitiveValueRegistry.MaxValueChars+1),false)))return 2;break;
        case "count":if(!Denied(()=>{for(int i=0;i<=SensitiveValueRegistry.MaxValues;i++){r.Input("1",value+i,false);}}))return 2;break;
        case "pending-bound":if(!Denied(()=>{for(int i=0;i<=SensitiveValueRegistry.MaxPending;i++)r.Input(i.ToString(),value,false);} ))return 2;break;
        case "total":if(!Denied(()=>{for(int i=0;i<128;i++)r.Input(i.ToString(),new string('x',4090)+i,false);} ))return 2;break;
        case "lifetime":TimeSpan elapsed=TimeSpan.Zero;using(var clocked=new SensitiveValueRegistry(()=>elapsed)){clocked.Activate();elapsed=SensitiveValueRegistry.MaxLifetime+TimeSpan.FromSeconds(1);if(!Denied(clocked.Require))return 2;}break;
        case "unavailable":r.Fail();if(!Denied(r.Require)||r.AuditSafe(value)!="[REDACTED]")return 2;break;
        case "no-eviction":try{for(int i=0;i<=SensitiveValueRegistry.MaxValues;i++)r.Input("1",value+i,false);}catch(IpcFailure){}if(!Denied(()=>r.Redact(value)))return 2;break;
        default:return 3;
    }
    Console.WriteLine(mode+":PASS");return 0;
}
string content=Path.Combine(Path.GetDirectoryName(root)!,"local");Directory.CreateDirectory(content);
File.WriteAllText(Path.Combine(content,"index.html"),"<!doctype html><body><input type=password><span>Controlled state</span></body>");
if(mode=="native-session-lifecycle")
{
    string known="harness-"+Guid.NewGuid().ToString("N");SensitiveValueRegistry old;
    using(var first=new WebView2Runtime(root,"bhi_"+Guid.NewGuid().ToString("N"),localContentRoot:content,maxTransferBytes:4096))
    {
        await first.CreateSession();await first.CreatePage("bwp_"+Guid.NewGuid().ToString("N"));old=Access.Registry(first);old.Input("captured-node",known,false);
        await first.CloseSession(15000);if(!Denied(old.Require)||Directory.Exists(root))return 7;
    }
    string next=root+"-next";
    using(var second=new WebView2Runtime(next,"bhi_"+Guid.NewGuid().ToString("N"),localContentRoot:content,maxTransferBytes:4096))
    {
        await second.CreateSession();await second.CreatePage("bwp_"+Guid.NewGuid().ToString("N"));var fresh=Access.Registry(second);
        if(ReferenceEquals(old,fresh)||fresh.Redact(known)!=known)return 8;
        await second.CloseSession(15000);if(Directory.Exists(next)||!Denied(fresh.Require))return 9;
    }
    Console.WriteLine("native-session-lifecycle:PASS;registryDisposed=true;newSessionIndependent=true;cleanup=true");return 0;
}
using var engine=new WebView2Runtime(root,"bhi_"+Guid.NewGuid().ToString("N"),localContentRoot:content,maxTransferBytes:4096);
string page="bwp_"+Guid.NewGuid().ToString("N");
try
{
    await engine.CreateSession();await engine.CreatePage(page);await engine.NavigateLocal(page,"index.html");
    if(mode=="native-structural-collision")
    {
        // Synthetic registry-state injection, NOT human-capture evidence. The
        // value is never logged: demonstrate whether recursive redaction can
        // mutate a fixed IPC discriminator rather than return a typed denial.
        Access.Registry(engine).Input("captured-node", "t", false);
        var o=System.Text.Json.JsonSerializer.SerializeToElement(await engine.Capture(page,24,1800,128));
        if(o.GetProperty("kind").GetString()!="capture")
        {Console.WriteLine("StructuralDiscriminatorChanged=true;rawValueLogged=false");return 17;}
        Console.WriteLine("StructuralDiscriminatorChanged=false");return 0;
    }
    if(mode=="native-navigation-diagnosis")
    {
        File.WriteAllText(Path.Combine(content,"other.html"),"<!doctype html><span id=out>Pending</span><script>out.textContent='Safe result '+decodeURIComponent(location.hash.slice(1));</script>");
        await engine.BeginTakeover(page);
        string known="test-only-"+Guid.NewGuid().ToString("N");
        await Access.Ui(engine,async()=>
        {
            var v=Access.Pages(engine)[page].CoreWebView2;
            // Certification-only synthetic input. No product eval/selector/IPC
            // operation, no credentials provided by Python, no persisted value.
            await v.ExecuteScriptAsync("(()=>{const p=document.querySelector('input');p.value="+System.Text.Json.JsonSerializer.Serialize(known)+";p.dispatchEvent(new Event('input',{bubbles:true}));location.href='other.html#'+encodeURIComponent(p.value);})()");
            return true;
        });
        await Task.Delay(300);await Access.Ui(engine,()=>{Access.Button(engine).PerformClick();return Task.FromResult(true);});
        var lostRegistry=Access.Registry(engine);
        var lost=Access.Controls(lostRegistry).Where(s=>s.SensitiveObserved&&!s.Active&&s.TerminalContinuityUnconfirmed).ToArray();
        if(!lost.Any(s=>s.Current==known&&s.Revision>0)||lost.Any(s=>s.Terminal is not null||s.Committed is not null)||lostRegistry.Redact(known)!="[INPUT_REDACTED]")return 16;
        SensitiveBoundaryFailureReason? firstReason=null;
        SensitiveBoundaryFailureDiagnostics.HarnessObserver=f=>firstReason??=f.Reason;
        bool denied=false;try{await engine.EndTakeover();}catch(IpcFailure e){denied=e.Code=="SECRET_BOUNDARY_UNCONFIRMED";}
        if(!denied||firstReason!=SensitiveBoundaryFailureReason.TERMINAL_CONTINUITY_UNCONFIRMED||!await DeniedAsync(()=>engine.Capture(page,24,1800,128)))return 17;
        var state=System.Text.Json.JsonSerializer.SerializeToElement(await engine.TakeoverState());
        if(!state.GetProperty("humanActive").GetBoolean()||state.GetProperty("contextEpoch").GetInt64()!=0||lostRegistry.AuditSafe(known)!="[REDACTED]")return 18;
        await engine.CloseSession(15000);if(Directory.Exists(root)||!Denied(lostRegistry.Require))return 19;
        Console.WriteLine("native-navigation-diagnosis:PASS;knownValueAbsent=true;ExpectedOutcome=DENY_TERMINAL_CONTINUITY_UNCONFIRMED;knownRetained=true;observationPublished=false;cleanup=true");return 0;
    }
    if(mode=="native-unavailable")
    {
        await Access.Ui(engine,()=>{Access.Dom(engine)[page].LoseSensitiveChannel();return Task.FromResult(true);});
        if(!await DeniedAsync(()=>engine.BeginTakeover(page)))return 4;
    }
    else
    {
        await engine.BeginTakeover(page);
        await Access.Ui(engine,async()=>
        {
            var view=Access.Pages(engine)[page].CoreWebView2;
            if(mode=="native-channel-loss")await view.CallDevToolsProtocolMethodAsync("Runtime.removeBinding","{\"name\":\"__nova_sensitive_capture_v2\"}");
            else if(mode=="native-instrumentation-loss")await view.CallDevToolsProtocolMethodAsync("Runtime.evaluate","{\"expression\":\"0\"}");
            else if(mode=="native-registry-failure")Access.Registry(engine).Fail();
            else return false;
            if(mode=="native-instrumentation-loss")Access.Dom(engine)[page].LoseSensitiveChannel();
            Access.Button(engine).PerformClick();return true;
        });
        if(!await DeniedAsync(engine.EndTakeover))return 4;
    }
    if(!await DeniedAsync(()=>engine.Capture(page,24,1800,128)))return 5;
    var registry=Access.Registry(engine);await engine.CloseSession(15000);
    if(!Denied(registry.Require)||Directory.Exists(root))return 6;
    Console.WriteLine(mode+":PASS;resumeBlocked=true;observationBlocked=true;cleanup=true");return 0;
}
finally{if(Directory.Exists(root))await engine.CloseSession(15000);}

static bool Denied(Action work){try{work();return false;}catch(IpcFailure e){return e.Code=="SECRET_BOUNDARY_UNCONFIRMED";}}
static async Task<bool> DeniedAsync(Func<Task<object>> work){try{await work();return false;}catch(IpcFailure e){return e.Code is "SECRET_BOUNDARY_UNCONFIRMED" or "HUMAN_CONTROL_INCOMPLETE";}}
static class Access
{
    private const BindingFlags Flags=BindingFlags.NonPublic|BindingFlags.Instance;
    public static Dictionary<string,ObservationRuntime> Dom(WebView2Runtime e)=>(Dictionary<string,ObservationRuntime>)typeof(WebView2Runtime).GetField("dom",Flags)!.GetValue(e)!;
    public static Dictionary<string,CoreWebView2Controller> Pages(WebView2Runtime e)=>(Dictionary<string,CoreWebView2Controller>)typeof(WebView2Runtime).GetField("pages",Flags)!.GetValue(e)!;
    public static SensitiveValueRegistry Registry(WebView2Runtime e)=>(SensitiveValueRegistry)typeof(WebView2Runtime).GetField("secrets",Flags)!.GetValue(e)!;
    public static IEnumerable<SensitiveControlState> Controls(SensitiveValueRegistry r)=>((Dictionary<SensitiveControlIdentity,SensitiveControlState>)typeof(SensitiveValueRegistry).GetField("controls",Flags)!.GetValue(r)!).Values;
    public static Button Button(WebView2Runtime e)=>(Button)typeof(WebView2Runtime).GetField("returnControl",Flags)!.GetValue(e)!;
    public static Task<T> Ui<T>(WebView2Runtime e,Func<Task<T>> work)=>(Task<T>)typeof(WebView2Runtime).GetMethod("OnUi",Flags)!.MakeGenericMethod(typeof(T)).Invoke(e,[work])!;
}
