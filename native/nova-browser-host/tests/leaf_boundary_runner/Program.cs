using System.Reflection;
using System.Text.Json;
using NovaBrowserHost;

// Only static field/leaf constants or host-private generated test material.
// No raw secret/CDP response is logged or exported to Python.
if(args.Length!=2)return 1;
string mode=args[0],root=args[1];
try
{
    using var registry=new SensitiveValueRegistry();registry.Input("short","x",false,true);
    if(mode.StartsWith("native-",StringComparison.Ordinal))
    {
        string content=Path.Combine(Path.GetDirectoryName(root)!,"local");Directory.CreateDirectory(content);
        string body=mode switch
        {
            "native-text"=>"<span>x</span>",
            "native-title"=>"<title>x</title><span>example</span>",
            "native-label"=>"<button aria-label=x>example</button>",
            "native-label-fragments"=>"<span id=l1>x</span><span id=l2>other</span><button aria-labelledby='l1 l2'>button</button>",
            "native-joins"=>"<span>x</span><span>b</span>",
            _=>"<span>example</span>"
        };
        File.WriteAllText(Path.Combine(content,"index.html"),"<!doctype html>"+body);
        using var engine=new WebView2Runtime(root,"bhi_"+Guid.NewGuid().ToString("N"),localContentRoot:content,maxTransferBytes:4096);
        string page="bwp_"+Guid.NewGuid().ToString("N");
        try
        {
            await engine.CreateSession();await engine.CreatePage(page);await engine.NavigateLocal(page,"index.html");
            var owned=(SensitiveValueRegistry)typeof(WebView2Runtime).GetField("secrets",BindingFlags.NonPublic|BindingFlags.Instance)!.GetValue(engine)!;
            owned.Input("native-host-known","x",false,true);
            var result=JsonSerializer.SerializeToElement(await engine.Capture(page,24,1800,128));
            if(mode=="native-text"&&result.GetProperty("text").GetString()!="[INPUT_REDACTED]")return 21;
            if(mode=="native-title"&&result.GetProperty("title").GetString()!="[INPUT_REDACTED]")return 22;
            if(mode=="native-example"&&result.GetProperty("text").GetString()!="example")return 23;
            if(mode=="native-joins"&&result.GetProperty("text").GetString()!="[INPUT_REDACTED] b")return 24;
            if(mode=="native-label"&&result.GetProperty("elements")[0].GetProperty("name").GetString()!="[INPUT_REDACTED]")return 25;
            if(mode=="native-label-fragments"&&result.GetProperty("elements")[0].GetProperty("name").GetString()!="[INPUT_REDACTED] other")return 26;
            if(result.TryGetProperty("leaves",out _)||result.TryGetProperty("nameLeaves",out _)||result.GetProperty("kind").GetString()!="capture")return 27;
            await engine.CloseSession(15000);if(Directory.Exists(root))return 28;
            Console.WriteLine("NativeLeafPassed=true;publicSchemaUnchanged=true;cleanup=true;rawValueRecorded=false");return 0;
        }
        finally{if(Directory.Exists(root))await engine.CloseSession(15000);}
    }
    List<PageDerivedTextLeaf> Text(params string[] items)=>items.Select(s=>new PageDerivedTextLeaf("TEXT",s)).ToList();
    string Summary(params string[] items)=>PageDerivedTextLeaves.SafeSummary(Text(items),registry.Redact);
    switch(mode)
    {
        case "short-exact":if(Summary("x")!="[INPUT_REDACTED]")return 2;break;
        case "short-substring":if(Summary("example")!="example")return 3;break;
        case "two-leaves":registry.Input("other","a",false,true);if(Summary("a","b")!="[INPUT_REDACTED] b")return 4;break;
        case "host-separator":if(Summary("x","tail")!="[INPUT_REDACTED] tail")return 5;break;
        case "title":case "label":case "dialog":case "state":if(registry.Redact("x")!="[INPUT_REDACTED]"||registry.Redact("example")!="example")return 6;break;
        case "long-transient":case "long-committed":
            string known=Guid.NewGuid().ToString("N");registry.Input("long",known,false);
            if(mode=="long-committed"){var identity=registry.DirectIdentity("long");registry.Checkpoint([registry.ConfirmTerminal(identity,registry.ObservedRevision(identity),known,SensitiveTerminalReason.CHECKPOINT)!]);}
            if(Summary("prefix "+known+" tail").Contains(known))return 7;break;
        case "leaf-count-bound":if(!Denied(()=>PageDerivedTextLeaves.SafeSummary(Text(Enumerable.Repeat("v",1025).ToArray()),registry.Redact)))return 8;break;
        case "leaf-length-bound":if(!Denied(()=>Summary(new string('v',32769))))return 9;break;
        case "aggregate-bound":if(!Denied(()=>Summary(new string('v',32768),new string('v',32768))))return 10;break;
        case "private-schema":
            var data=JsonSerializer.SerializeToElement(new[]{new{kind="TEXT",text="x"}});if(PageDerivedTextLeaves.Read(data).Count!=1)return 11;break;
        case "unknown-leaf-kind":
            if(!Denied(()=>PageDerivedTextLeaves.Read(JsonSerializer.SerializeToElement(new[]{new{kind="DOM",text="x"}}))))return 12;break;
        default:return 15;
    }
    Console.WriteLine("LeafPassed=true;boundariesPreserved=true;rawValueRecorded=false");return 0;
}
catch(Exception e){Console.WriteLine("FailureCode="+(e is IpcFailure ipc?ipc.Code:"UNCLASSIFIED")+";rawValueRecorded=false");return 99;}
static bool Denied(Action work){try{work();return false;}catch(IpcFailure e){return e.Code=="OBSERVATION_LIMIT";}}
