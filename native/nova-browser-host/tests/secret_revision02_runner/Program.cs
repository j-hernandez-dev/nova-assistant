using System.Reflection;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;
using NovaBrowserHost;

// Certification only. No new IPC operation, page bridge, product flag or
// arbitrary model script. Values stay in this process/native engine memory;
// receipts contain only booleans/opaque case IDs. Never print exception data.
if(args.Length!=2)return 1;
string mode=args[0],root=args[1];
SensitiveBoundaryFailure? selectedFailure=null;
int submitWitnesses=0;
SensitiveBoundaryFailureDiagnostics.HarnessObserver=f=>selectedFailure??=f;
SensitiveTerminalDiagnostics.HarnessObserver=e=>
{if(e.Kind==SensitiveTerminalDiagnosticKind.TERMINAL_CREATED&&e.Reason==SensitiveTerminalReason.SUBMIT)submitWitnesses++;};
try
{
    if(mode.StartsWith("contract-",StringComparison.Ordinal))
    {
        using var registry=new SensitiveValueRegistry();
        string seed=Guid.NewGuid().ToString("N");
        var steps=Cases.Steps(mode[9..],seed);
        if(mode=="contract-count")
        {
            bool denied=false;
            try{for(int i=0;i<=SensitiveValueRegistry.MaxValues;i++)registry.Input("control",seed+i,false,true);}
            catch(IpcFailure e){denied=e.Code=="SECRET_BOUNDARY_UNCONFIRMED";}
            if(!denied||!Cases.Denied(registry.Require))return 20;
        }
        else if(mode=="contract-total")
        {
            bool denied=false;
            try{for(int i=0;i<100;i++)registry.Input("control",new string('x',4090)+i,false,true);}
            catch(IpcFailure e){denied=e.Code=="SECRET_BOUNDARY_UNCONFIRMED";}
            if(!denied||!Cases.Denied(registry.Require))return 21;
        }
        else
        {
            var known=new List<string>();
            for(int i=0;i<steps.Length;i++)
            {
                registry.Input(mode=="contract-multiple"?"control:"+i%3:"control",steps[i],false,true);
                if(steps[i].Length>0)known.Add(steps[i]);
                foreach(var old in known)if(registry.Redact(old)!="[INPUT_REDACTED]")return 22;
            }
            if(mode=="contract-dedup")for(int i=0;i<2048;i++)registry.Input("control",seed,false,true);
            registry.Retire("control");registry.Checkpoint();
            foreach(var old in known)if(registry.Redact(old)!="[INPUT_REDACTED]")return 23;
        }
        Console.WriteLine("ContractPassed=true;monotonic=true;rawValueRecorded=false");return 0;
    }
    string content=Path.Combine(Path.GetDirectoryName(root)!,"local");Directory.CreateDirectory(content);
    File.WriteAllText(Path.Combine(content,"index.html"),"<!doctype html><input type=password id=p><input type=password id=q><span id=out>Pending</span><button id=target>Target</button><form id=form></form><script>p.oninput=()=>out.textContent=p.value;</script>");
    File.WriteAllText(Path.Combine(content,"other.html"),"<!doctype html><span id=out>Pending</span><script>out.textContent=decodeURIComponent(location.hash.slice(1));document.title=out.textContent;</script>");
    using var engine=new WebView2Runtime(root,"bhi_"+Guid.NewGuid().ToString("N"),localContentRoot:content,maxTransferBytes:4096);
    string page="bwp_"+Guid.NewGuid().ToString("N");
    try
    {
        await engine.CreateSession();await engine.CreatePage(page);await engine.NavigateLocal(page,"index.html");
        var before=JsonSerializer.SerializeToElement(await engine.Capture(page,24,1800,128));
        string[] steps;
        if(mode.StartsWith("native-schema-",StringComparison.Ordinal))
        {
            string[] collisions=["capture","event","error","success","t","1"];
            steps=[collisions[int.Parse(mode[14..])]];
        }
        else steps=Cases.Steps(mode[12..],Guid.NewGuid().ToString("N"));
        await engine.BeginTakeover(page);
        for(int i=0;i<steps.Length;i++)
        {
            string value=steps[i],id=mode=="native-edit-multiple"&&i%2==1?"q":"p";
            await Access.Ui(engine,async()=>
            {
                await Access.View(engine,page).ExecuteScriptAsync("(()=>{const e=document.getElementById("+JsonSerializer.Serialize(id)+");e.value="+JsonSerializer.Serialize(value)+";e.dispatchEvent(new Event('input',{bubbles:true}));})()");return true;
            });
        }
        string[] known=steps.Where(s=>s.Length>0).Distinct().ToArray();
        string reflected=string.Join(" ",known);
        await Access.Ui(engine,async()=>
        {
            await Access.View(engine,page).ExecuteScriptAsync("(()=>{const s="+JsonSerializer.Serialize(reflected)+";out.textContent=s;document.title=s;target.setAttribute('aria-label',s);form.setAttribute('aria-label',s);})()");return true;
        });
        if(mode is "native-edit-same" or "native-edit-cross" or "native-edit-history")
        {
            string destination=mode=="native-edit-cross"?"https://nova-second.invalid/other.html":"other.html";
            await Access.Ui(engine,async()=>{await Access.View(engine,page).ExecuteScriptAsync("location.href="+JsonSerializer.Serialize(destination+"#"+Uri.EscapeDataString(reflected))+";");return true;});
            await Task.Delay(300);
            if(mode=="native-edit-history")
            {
                await Access.Ui(engine,async()=>{await Access.View(engine,page).ExecuteScriptAsync("history.back()");return true;});await Task.Delay(300);
                await Access.Ui(engine,async()=>{await Access.View(engine,page).ExecuteScriptAsync("history.forward()");return true;});await Task.Delay(300);
            }
        }
        await Access.Ui(engine,()=>{Access.Button(engine).PerformClick();return Task.FromResult(true);});
        bool lostSource=mode is "native-edit-same" or "native-edit-cross" or "native-edit-history";
        bool shortTerminal=mode is "native-edit-prefix" or "native-schema-4" or "native-schema-5";
        if(lostSource||shortTerminal)
        {
            // Prospective expectation only. The actual native edit, reflection,
            // navigation, and human-completion sequence above is unchanged.
            var registry=Access.Registry(engine);
            bool knownBefore=known.All(v=>Access.Known(registry).ContainsKey(v));
            bool retiredWithoutWitness=Access.Controls(registry).Any(s=>
                s.Identity.Owner==registry.SessionOwner&&s.Identity.Page==page&&s.SensitiveObserved&&
                s.Revision>0&&!s.Active&&s.TerminalContinuityUnconfirmed&&s.Terminal is null&&s.Committed is null);
            bool denied=false;try{await engine.EndTakeover();}
            catch(IpcFailure e){denied=e.Code=="SECRET_BOUNDARY_UNCONFIRMED";}
            var expected=lostSource?SensitiveBoundaryFailureReason.TERMINAL_CONTINUITY_UNCONFIRMED:SensitiveBoundaryFailureReason.SHORT_COMMITTED_VALUE;
            if(!denied||selectedFailure?.Reason!=expected||!knownBefore||submitWitnesses!=0)return 40;
            if(lostSource&&!retiredWithoutWitness)return 41;
            if(shortTerminal&&!(steps[^1].Length is >=1 and <=3&&
                selectedFailure?.TerminalReason==SensitiveTerminalReason.CHECKPOINT&&
                selectedFailure?.SnapshotRevision==selectedFailure?.CurrentRevision&&
                selectedFailure?.CurrentLength==steps[^1].Length&&
                Access.Controls(registry).Any(s=>s.Identity.Page==page&&s.Active&&s.SensitiveObserved&&
                    s.Current==steps[^1]&&s.Terminal is{} terminal&&terminal.Value==steps[^1]&&terminal.Reason==SensitiveTerminalReason.CHECKPOINT&&
                    terminal.Revision==s.Revision)))return 42;
            bool projectionBlocked=false;try{await engine.Capture(page,24,1800,128);}
            catch(IpcFailure){projectionBlocked=true;}
            var state=JsonSerializer.SerializeToElement(await engine.TakeoverState());
            if(!projectionBlocked||!state.GetProperty("humanActive").GetBoolean()||
                state.GetProperty("contextEpoch").GetInt64()!=0||!known.All(v=>Access.Known(registry).ContainsKey(v)))return 43;
            // A closed denial publishes no page-derived leaves. Keep the same
            // serializer/control-plane assertions without inventing a capture.
            var denialRequest=JsonSerializer.SerializeToElement(new{schemaVersion=5,messageType="request",requestId="bhr_"+Guid.NewGuid().ToString("N"),browserSessionRef="bws_"+Guid.NewGuid().ToString("N"),pageRef=page,operationId="op_"+Guid.NewGuid().ToString("N"),deadline=DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()+5000,payload=new{command="capture",maxElements=24,maxText=1800,maxField=128},result=(object?)null,error=(object?)null});
            foreach(var reply in new[]{TransferProtocol.Reply(denialRequest,null,"SECRET_BOUNDARY_UNCONFIRMED"),TransferProtocol.Reply(denialRequest,null,evt:"ACTION_STARTED")})
            {
                using var stream=new MemoryStream();await Protocol.Write(stream,reply,CancellationToken.None,TransferProtocol.Parse);
                byte[] frame=stream.ToArray();if(BitConverter.ToInt32(frame,0)!=frame.Length-4)return 30;
                var parsed=TransferProtocol.Parse(frame[4..]);
                if(parsed.GetProperty("requestId").GetString()!=denialRequest.GetProperty("requestId").GetString()||parsed.GetProperty("schemaVersion").GetInt32()!=5||parsed.GetProperty("result").ValueKind!=JsonValueKind.Null)return 31;
                if(parsed.GetProperty("messageType").GetString()=="response"&&parsed.GetProperty("error").GetProperty("code").GetString()!="SECRET_BOUNDARY_UNCONFIRMED")return 44;
            }
            await engine.CloseSession(15000);if(Directory.Exists(root)||!Cases.Denied(registry.Require)||Access.Known(registry).Count!=0)return 32;
            Console.WriteLine("ExpectedOutcome=DENY;reason="+expected+";knownRetained=true;noResume=true;projectionBlocked=true;pageDataProtected=true;controlPlaneUnchanged=true;closedSerializerValid=true;cleanup=true;rawValueRecorded=false");return 0;
        }
        await engine.EndTakeover();
        var result=JsonSerializer.SerializeToElement(await engine.Capture(page,24,1800,128));
        if(result.GetProperty("kind").GetString()!="capture"||!result.GetProperty("text").GetString()!.Contains("[INPUT_REDACTED]",StringComparison.Ordinal))return 24;
        foreach(string leaf in new[]{"title","text"})
            if(known.Any(v=>result.GetProperty(leaf).GetString()!.Contains(v,StringComparison.Ordinal)))return 25;
        foreach(var row in result.GetProperty("elements").EnumerateArray())
        {
            if(!row.GetProperty("binding").GetString()!.StartsWith("wvb_",StringComparison.Ordinal)||row.GetProperty("fingerprint").GetString()!.Length!=64)return 26;
            if(known.Any(v=>row.GetProperty("name").GetString()!.Contains(v,StringComparison.Ordinal)))return 27;
        }
        if(mode is "native-edit-same" or "native-edit-cross" or "native-edit-history")
            if(result.GetProperty("engineEpoch").GetInt64()<=before.GetProperty("engineEpoch").GetInt64())return 28;
        foreach(var value in known)if(Access.Registry(engine).Redact(value)!="[INPUT_REDACTED]")return 29;
        // Closed C# parser + length-prefixed serializer remain authoritative.
        var request=JsonSerializer.SerializeToElement(new{schemaVersion=5,messageType="request",requestId="bhr_"+Guid.NewGuid().ToString("N"),browserSessionRef="bws_"+Guid.NewGuid().ToString("N"),pageRef=page,operationId="op_"+Guid.NewGuid().ToString("N"),deadline=DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()+5000,payload=new{command="capture",maxElements=24,maxText=1800,maxField=128},result=(object?)null,error=(object?)null});
        foreach(var reply in new[]{TransferProtocol.Reply(request,result),TransferProtocol.Reply(request,null,"SECRET_BOUNDARY_UNCONFIRMED"),TransferProtocol.Reply(request,null,evt:"ACTION_STARTED")})
        {
            using var stream=new MemoryStream();await Protocol.Write(stream,reply,CancellationToken.None,TransferProtocol.Parse);
            byte[] frame=stream.ToArray();if(BitConverter.ToInt32(frame,0)!=frame.Length-4)return 30;
            var parsed=TransferProtocol.Parse(frame[4..]);
            if(parsed.GetProperty("requestId").GetString()!=request.GetProperty("requestId").GetString()||parsed.GetProperty("schemaVersion").GetInt32()!=5)return 31;
        }
        await engine.CloseSession(15000);if(Directory.Exists(root)||!Cases.Denied(Access.Registry(engine).Require))return 32;
        Console.WriteLine("NativePassed=true;pageDataProtected=true;controlPlaneUnchanged=true;closedSerializerValid=true;cleanup=true;rawValueRecorded=false");return 0;
    }
    finally{if(Directory.Exists(root))await engine.CloseSession(15000);}
}
catch(Exception e){Console.WriteLine("FailureCode="+(e is IpcFailure ipc?ipc.Code:"UNCLASSIFIED")+";rawValueRecorded=false");return 99;}

static class Cases
{
    public static string[] Steps(string mode,string seed)=>mode switch
    {
        "prefix"=>[seed[..1],seed[..2],seed[..3],seed[..2]+"x"],
        "shrink"=>[seed,seed[..16],seed[..8]],
        "replacement"=>[seed,"next-"+seed,"other-"+seed],
        "clear"=>[seed,"","new-"+seed],
        "paste"=>[seed,"pasted-"+seed],
        "multiple"=>[seed,"sibling-"+seed,"alternate-"+seed,"final-"+seed],
        _=>[seed,"replacement-"+seed]
    };
    public static bool Denied(Action work){try{work();return false;}catch(IpcFailure e){return e.Code=="SECRET_BOUNDARY_UNCONFIRMED";}}
}
static class Access
{
    private const BindingFlags Flags=BindingFlags.NonPublic|BindingFlags.Instance;
    public static CoreWebView2 View(WebView2Runtime e,string page)=>((Dictionary<string,CoreWebView2Controller>)typeof(WebView2Runtime).GetField("pages",Flags)!.GetValue(e)!)[page].CoreWebView2;
    public static SensitiveValueRegistry Registry(WebView2Runtime e)=>(SensitiveValueRegistry)typeof(WebView2Runtime).GetField("secrets",Flags)!.GetValue(e)!;
    public static Dictionary<string,SensitiveValueRegistry.ValueClass> Known(SensitiveValueRegistry r)=>(Dictionary<string,SensitiveValueRegistry.ValueClass>)typeof(SensitiveValueRegistry).GetField("values",Flags)!.GetValue(r)!;
    public static IEnumerable<SensitiveControlState> Controls(SensitiveValueRegistry r)=>((Dictionary<SensitiveControlIdentity,SensitiveControlState>)typeof(SensitiveValueRegistry).GetField("controls",Flags)!.GetValue(r)!).Values;
    public static Button Button(WebView2Runtime e)=>(Button)typeof(WebView2Runtime).GetField("returnControl",Flags)!.GetValue(e)!;
    public static Task<T> Ui<T>(WebView2Runtime e,Func<Task<T>> work)=>(Task<T>)typeof(WebView2Runtime).GetMethod("OnUi",Flags)!.MakeGenericMethod(typeof(T)).Invoke(e,[work])!;
}
