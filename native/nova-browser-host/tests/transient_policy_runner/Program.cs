using System.Reflection;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;
using NovaBrowserHost;

// Test executable only: values are generated/retained in this native process.
// No values, page text, exceptions or scripts are printed/exported to Python.
if(args.Length!=2)return 1;
string mode=args[0],root=args[1];
SensitiveBoundaryFailureReason? firstReason=null;
SensitiveBoundaryFailureDiagnostics.HarnessObserver=f=>firstReason??=f.Reason;
try
{
    if(mode.StartsWith("contract-",StringComparison.Ordinal))
    {
        using var r=new SensitiveValueRegistry();
        string longValue=Guid.NewGuid().ToString("N"),next=Guid.NewGuid().ToString("N");
        switch(mode[9..])
        {
            case "transient-short":
                r.Input("p","s",false,true);
                if(r.Redact("Safe result")!="Safe result"||r.Redact("Continue")!="Continue"||
                   r.PublicUrl("https://nova-second.invalid/path")!="https://nova-second.invalid/path"||
                   r.Redact("s")!="[INPUT_REDACTED]")return 11;
                break;
            case "transient-long":
                r.Input("p",longValue,false,true);
                if(r.Redact("prefix "+longValue+" suffix").Contains(longValue))return 12;
                break;
            case "committed-long":
                r.Input("p",longValue,false,true);r.Checkpoint([TerminalProof(r,"p",longValue,SensitiveTerminalReason.CHECKPOINT)]);
                if(r.Redact("prefix "+longValue+" suffix").Contains(longValue)||!State(r,longValue,true))return 13;
                break;
            case "committed-short-1":
            case "committed-short-2":
            case "committed-short-3":
                string shortValue=new('s',int.Parse(mode[^1..]));
                r.Input("p",shortValue,false,true);
                if(!Denied(()=>r.Checkpoint([TerminalProof(r,"p",shortValue,SensitiveTerminalReason.CHECKPOINT)]))||!State(r,shortValue,true)||
                   !Denied(r.Require)||!Denied(()=>r.Redact("Safe result")))return 14;
                break;
            case "promotion":
                r.Input("p",longValue,false,true);if(!State(r,longValue,false))return 15;
                r.Checkpoint([TerminalProof(r,"p",longValue,SensitiveTerminalReason.CHECKPOINT)]);if(!State(r,longValue,true))return 16;
                r.Input("p",longValue,false,true);if(!State(r,longValue,true))return 17;
                break;
            case "terminal-retire":
                r.Input("world:p","s",false,true);r.Input("world:p",longValue,false,true);
                var retired=RetirementProof(r,"world:p",longValue);
                // A real submit witness, not retirement, commits this value.
                r.Commit(TerminalProof(r,"world:p",longValue,SensitiveTerminalReason.SUBMIT));
                r.SealForRetirement(r.SessionOwner,retired.Identity.Page,retired.Identity.Generation,retired.World);
                r.Retire("world:");if(!State(r,"s",false)||!State(r,longValue,true))return 18;
                break;
            case "terminal-checkpoint":
                r.Input("p","s",false,true);r.Input("p",longValue,false,true);
                r.Checkpoint([TerminalProof(r,"p",longValue,SensitiveTerminalReason.CHECKPOINT)]);
                if(!State(r,"s",false)||!State(r,longValue,true))return 19;
                break;
            case "history-clear":
                foreach(var v in new[]{"A","AB","ABC","ABX",longValue,"",next})r.Input("p",v,false,true);
                r.Checkpoint([TerminalProof(r,"p",next,SensitiveTerminalReason.CHECKPOINT)]);foreach(var v in new[]{"A","AB","ABC","ABX",longValue,next})
                    if(r.Redact(v)!="[INPUT_REDACTED]")return 20;
                if(r.Redact("Safe result")!="Safe result")return 21;
                break;
            case "short-retire-denied":
                r.Input("world:p","s",false,true);RetirementProof(r,"world:p","s");if(!Denied(()=>r.Commit(TerminalProof(r,"world:p","s",SensitiveTerminalReason.SUBMIT))))return 22;break;
            case "short-checkpoint-denied":
                r.Input("p","s",false,true);var shortSnapshot=TerminalProof(r,"p","s",SensitiveTerminalReason.CHECKPOINT);if(!Denied(()=>r.Checkpoint([shortSnapshot])))return 23;break;
            case "no-eviction":
                if(!Denied(()=>{for(int i=0;i<=SensitiveValueRegistry.MaxValues;i++)r.Input("p",longValue+i,false,true);})||
                   !Denied(r.Require)||!State(r,longValue+"0",false))return 24;break;
            case "lifecycle":
                r.Input("p",longValue,false,true);r.Dispose();if(!Denied(r.Require))return 25;
                using(var other=new SensitiveValueRegistry())if(other.Redact(longValue)!=longValue)return 26;
                break;
            default:return 2;
        }
        Console.WriteLine("ContractPassed=true;monotonic=true;rawValueRecorded=false");return 0;
    }
    string content=Path.Combine(Path.GetDirectoryName(root)!,"local");Directory.CreateDirectory(content);
    File.WriteAllText(Path.Combine(content,"index.html"),"<!doctype html><input type=password id=p><span id=out>Pending</span><button id=target>Continue</button><form id=form></form>");
    File.WriteAllText(Path.Combine(content,"other.html"),"<!doctype html><span id=out>Pending</span><script>out.textContent=decodeURIComponent(location.hash.slice(1));document.title='Controlled';</script>");
    using var engine=new WebView2Runtime(root,"bhi_"+Guid.NewGuid().ToString("N"),localContentRoot:content,maxTransferBytes:4096);
    string page="bwp_"+Guid.NewGuid().ToString("N");
    try
    {
        await engine.CreateSession();await engine.CreatePage(page);await engine.NavigateLocal(page,"index.html");
        await engine.BeginTakeover(page);
        var registry=Access.Registry(engine);
        string observed=mode=="native-schema"?"capture":Guid.NewGuid().ToString("N");
        string terminal=Guid.NewGuid().ToString("N");
        string initial=mode.StartsWith("native-short",StringComparison.Ordinal)?"s":observed;
        await Edit(engine,page,initial,mode=="native-committed-long");
        // Barrier in the native test process, never IPC: actual private-world
        // input event must have reached the real registry before further editing.
        await WaitKnown(registry,initial);
        if(mode=="native-committed-short")
        {
            await Edit(engine,page,"ss",true);await WaitKnown(registry,"ss");
            await Access.Ui(engine,()=>{Access.Button(engine).PerformClick();return Task.FromResult(true);});
            if(!await DeniedAsync(engine.EndTakeover)||!await DeniedAsync(()=>engine.Capture(page,24,1800,128)))return 31;
        }
        else
        {
            await Edit(engine,page,terminal);await WaitKnown(registry,terminal);
            string reflection=mode=="native-short-exact"?"s":mode=="native-short-preserved"?"Safe result":"Safe result "+observed;
            await Access.Ui(engine,async()=>{
                await Access.View(engine,page).ExecuteScriptAsync("(()=>{const s="+JsonSerializer.Serialize(reflection)+";out.textContent=s;document.title=s;target.setAttribute('aria-label',s);form.setAttribute('aria-label',s);})()");
                if(mode=="native-short-exact")await Access.View(engine,page).ExecuteScriptAsync("target.hidden=true;form.hidden=true");
                return true;
            });
            if(mode is "native-navigation" or "native-cross" or "native-history")
            {
                string destination=mode=="native-cross"?"https://nova-second.invalid/other.html":"other.html";
                await Access.Ui(engine,async()=>{await Access.View(engine,page).ExecuteScriptAsync("location.href="+JsonSerializer.Serialize(destination+"#"+Uri.EscapeDataString(terminal))+";");return true;});
                await Task.Delay(300);
                if(mode=="native-history")
                {
                    await Access.Ui(engine,async()=>{await Access.View(engine,page).ExecuteScriptAsync("history.back()");return true;});await Task.Delay(300);
                    await Access.Ui(engine,async()=>{await Access.View(engine,page).ExecuteScriptAsync("history.forward()");return true;});await Task.Delay(300);
                }
            }
            else if(mode=="native-submit")
                await Access.Ui(engine,async()=>{await Access.View(engine,page).ExecuteScriptAsync("form.addEventListener('submit',e=>e.preventDefault());form.requestSubmit()");return true;});
            await Access.Ui(engine,()=>{Access.Button(engine).PerformClick();return Task.FromResult(true);});
            if(mode is "native-navigation" or "native-cross" or "native-history")
            {
                var lost=Access.Controls(registry).Where(s=>s.SensitiveObserved&&!s.Active&&s.TerminalContinuityUnconfirmed).ToArray();
                if(lost.Length==0||!State(registry,terminal,false)||lost.Any(s=>s.Revision<=0||s.Terminal is not null||s.Committed is not null))return 41;
                if(!lost.Any(s=>s.Current==terminal)||lost.Any(s=>Access.DocumentLive(registry,s.Identity)))return 42;
                bool denied=false;try{await engine.EndTakeover();}catch(IpcFailure e){denied=e.Code=="SECRET_BOUNDARY_UNCONFIRMED";}
                var state=JsonSerializer.SerializeToElement(await engine.TakeoverState());
                if(!denied||firstReason!=SensitiveBoundaryFailureReason.TERMINAL_CONTINUITY_UNCONFIRMED||!state.GetProperty("humanActive").GetBoolean()||state.GetProperty("contextEpoch").GetInt64()!=0)return 43;
                if(!await DeniedAsync(()=>engine.Capture(page,24,1800,128))||!State(registry,terminal,false)||!State(registry,observed,false))return 44;
                var denialRequest=JsonSerializer.SerializeToElement(new{schemaVersion=5,messageType="request",requestId="bhr_"+Guid.NewGuid().ToString("N"),browserSessionRef="bws_"+Guid.NewGuid().ToString("N"),pageRef=(string?)null,operationId="op_"+Guid.NewGuid().ToString("N"),deadline=DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()+5000,payload=new{command="takeover_end"},result=(object?)null,error=(object?)null});
                using var deniedFrame=new MemoryStream();await Protocol.Write(deniedFrame,TransferProtocol.Reply(denialRequest,null,"SECRET_BOUNDARY_UNCONFIRMED"),CancellationToken.None,TransferProtocol.Parse);
                var denialPayload=TransferProtocol.Parse(deniedFrame.ToArray()[4..]);
                if(denialPayload.GetProperty("error").GetProperty("code").GetString()!="SECRET_BOUNDARY_UNCONFIRMED"||denialPayload.GetProperty("result").ValueKind!=JsonValueKind.Null||denialPayload.GetRawText().Contains(terminal,StringComparison.Ordinal))return 45;
                Console.WriteLine("ExpectedOutcome=DENY_TERMINAL_CONTINUITY_UNCONFIRMED;observed=true;retired=true;strongSnapshot=false;knownRetained=true;observationPublished=false");
            }
            else
            {
            await engine.EndTakeover();
            var payload=JsonSerializer.SerializeToElement(await engine.Capture(page,24,1800,128));
            if(payload.GetProperty("kind").GetString()!="capture"||!State(registry,terminal,true))return 32;
            // Unchanged CHANGE fixture is now a weak signal. Its historical
            // value remains known/protected, not COMMITTED by a fifth source.
            if(mode=="native-committed-long"&&!State(registry,observed,false))return 39;
            if(mode=="native-short-preserved")
            {if(!payload.GetProperty("text").GetString()!.Contains("Safe result")||!State(registry,"s",false))return 33;}
            else
            {
                string known=mode=="native-short-exact"?"s":mode is "native-navigation" or "native-cross" or "native-history"?terminal:observed;
                if(payload.GetProperty("title").GetString()==known||payload.GetProperty("text").GetString()!.Trim()==known)return 34;
                if(known.Length>=4&&(payload.GetProperty("text").GetString()!.Contains(known)||payload.GetProperty("title").GetString()!.Contains(known)))return 35;
                if(!payload.GetProperty("text").GetString()!.Contains("[INPUT_REDACTED]"))return 36;
            }
            // Public payload only is framed. Fixed discriminators, identifiers,
            // errors and events remain valid; no recursive envelope redaction.
            var request=JsonSerializer.SerializeToElement(new{schemaVersion=5,messageType="request",requestId="bhr_"+Guid.NewGuid().ToString("N"),browserSessionRef="bws_"+Guid.NewGuid().ToString("N"),pageRef=page,operationId="op_"+Guid.NewGuid().ToString("N"),deadline=DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()+5000,payload=new{command="capture",maxElements=24,maxText=1800,maxField=128},result=(object?)null,error=(object?)null});
            using var stream=new MemoryStream();await Protocol.Write(stream,TransferProtocol.Reply(request,payload),CancellationToken.None,TransferProtocol.Parse);
            var parsed=TransferProtocol.Parse(stream.ToArray()[4..]);
            if(parsed.GetProperty("result").GetProperty("kind").GetString()!="capture")return 37;
            }
        }
        await engine.CloseSession(15000);
        if(Directory.Exists(root)||!Denied(registry.Require))return 38;
        Console.WriteLine("NativePassed=true;pageDataProtected=true;controlPlaneUnchanged=true;closedSerializerValid=true;cleanup=true;rawValueRecorded=false");return 0;
    }
    finally{if(Directory.Exists(root))await engine.CloseSession(15000);}
}
catch(Exception e){Console.WriteLine("FailureCode="+(e is IpcFailure ipc?ipc.Code:"UNCLASSIFIED")+";rawValueRecorded=false");return 99;}

static bool Denied(Action work){try{work();return false;}catch(IpcFailure e){return e.Code=="SECRET_BOUNDARY_UNCONFIRMED";}}
static SensitiveTerminalSnapshot TerminalProof(SensitiveValueRegistry registry,string key,string observedValue,SensitiveTerminalReason reason)
{
    // Direct host-producer proof: exact owner/Page/incarnation/control and the
    // revision of the value already observed. No lookup chooses its value.
    var identity=registry.DirectIdentity(key);
    return registry.ConfirmTerminal(identity,registry.ObservedRevision(identity),observedValue,reason)
        ??throw new IpcFailure("SECRET_BOUNDARY_UNCONFIRMED");
}
static (SensitiveControlIdentity Identity,string World) RetirementProof(SensitiveValueRegistry registry,string key,string observedValue)
{
    var identity=registry.DirectIdentity(key);string world=Guid.NewGuid().ToString("N");
    registry.RegisterProtectedWorld(identity.Page,identity.Generation,world);
    registry.ObserveInput(identity,registry.ObservedRevision(identity),observedValue,SensitiveInputSignal.PAGEHIDE);
    // A weak lifecycle notification preserves current; it cannot commit.
    if(!State(registry,observedValue,false))throw new Exception("WEAK_SIGNAL_COMMITTED");
    return (identity,world);
}
static async Task<bool> DeniedAsync(Func<Task<object>> work){try{await work();return false;}catch(IpcFailure e){return e.Code is "SECRET_BOUNDARY_UNCONFIRMED" or "HUMAN_CONTROL_INCOMPLETE";}}
static bool State(SensitiveValueRegistry r,string value,bool committed)
{
    var values=(Dictionary<string,SensitiveValueRegistry.ValueClass>)typeof(SensitiveValueRegistry).GetField("values",BindingFlags.NonPublic|BindingFlags.Instance)!.GetValue(r)!;
    return values.TryGetValue(value,out var state)&&state==(committed?SensitiveValueRegistry.ValueClass.COMMITTED:SensitiveValueRegistry.ValueClass.TRANSIENT);
}
static async Task WaitKnown(SensitiveValueRegistry r,string value)
{
    var end=DateTime.UtcNow.AddSeconds(2);
    while(DateTime.UtcNow<end){if(State(r,value,false)||State(r,value,true))return;await Task.Delay(10);}
    throw new IpcFailure("SECRET_BOUNDARY_UNCONFIRMED");
}
static Task Edit(WebView2Runtime e,string page,string value,bool commit=false)=>Access.Ui(e,async()=>{
    await Access.View(e,page).ExecuteScriptAsync("(()=>{const p=document.getElementById('p');p.value="+JsonSerializer.Serialize(value)+";p.dispatchEvent(new Event("+JsonSerializer.Serialize(commit?"change":"input")+",{bubbles:true}));})()");return true;
});
static class Access
{
    private const BindingFlags Flags=BindingFlags.NonPublic|BindingFlags.Instance;
    public static CoreWebView2 View(WebView2Runtime e,string page)=>((Dictionary<string,CoreWebView2Controller>)typeof(WebView2Runtime).GetField("pages",Flags)!.GetValue(e)!)[page].CoreWebView2;
    public static SensitiveValueRegistry Registry(WebView2Runtime e)=>(SensitiveValueRegistry)typeof(WebView2Runtime).GetField("secrets",Flags)!.GetValue(e)!;
    public static IEnumerable<SensitiveControlState> Controls(SensitiveValueRegistry r)=>((Dictionary<SensitiveControlIdentity,SensitiveControlState>)typeof(SensitiveValueRegistry).GetField("controls",Flags)!.GetValue(r)!).Values;
    public static bool DocumentLive(SensitiveValueRegistry r,SensitiveControlIdentity id)=>((Dictionary<(string,string),bool>)typeof(SensitiveValueRegistry).GetField("documents",Flags)!.GetValue(r)!)[(id.Page,id.Generation)];
    public static Button Button(WebView2Runtime e)=>(Button)typeof(WebView2Runtime).GetField("returnControl",Flags)!.GetValue(e)!;
    public static Task<T> Ui<T>(WebView2Runtime e,Func<Task<T>> work)=>(Task<T>)typeof(WebView2Runtime).GetMethod("OnUi",Flags)!.MakeGenericMethod(typeof(T)).Invoke(e,[work])!;
}

