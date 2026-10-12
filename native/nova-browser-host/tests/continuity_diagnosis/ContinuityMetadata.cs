using System.Diagnostics;
using System.Text.Json;

namespace NovaBrowserHost;

// Diagnostic executable ONLY, never compiled into the productive host.
// All arguments are control identities or scalars. Never accepts a raw value,
// URL, DOM text, secret hash, exception message or a public IPC payload.
internal static class ContinuityMetadata
{
    private static readonly object Gate=new();
    private static readonly Stopwatch Clock=Stopwatch.StartNew();
    private static readonly Dictionary<string,string> Pages=new(),Controls=new(),Frames=new();
    private static readonly Dictionary<string,(string Id,bool Live)> Worlds=new();
    private static readonly Dictionary<string,string> LastKinds=new();
    private static readonly AsyncLocal<string?> ScopeReason=new();
    private static string? file;
    private static int ownerPid;
    private static long sequence;
    private static string? firstFailure;
    private static bool overflow,deliveryFailed;
    public static void Init(string[] args)
    {
        var options=new Dictionary<string,string>();
        for(int i=0;i<args.Length;i+=2)options.Add(args[i],args[i+1]);
        if(!options.TryGetValue("--udf",out var udf))return;
        file=udf+".continuity-metadata.jsonl";
        int.TryParse(options.GetValueOrDefault("--owner-pid"),out ownerPid);
        Emit("diagnostic_start");
    }
    private static string Id(Dictionary<string,string> map,string key,string prefix)
    {if(!map.TryGetValue(key,out var id)){id=prefix+"_"+(map.Count+1);map.Add(key,id);}return id;}
    private static string WorldId(string page,int context)
    {
        string key=page+":"+context;
        if(!Worlds.TryGetValue(key,out var value)){value=("world_"+(Worlds.Count+1),false);Worlds.Add(key,value);}
        return value.Id;
    }
    private static (string? Page,string? World,string? Control,bool? Live) Identify(string? key)
    {
        if(key is null)return(null,null,null,null);
        var parts=key.Split(':');
        if(parts.Length<3||!int.TryParse(parts[1],out var context))return(null,null,Id(Controls,key,"control"),null);
        string page=parts[0],world=WorldId(page,context);
        return(Id(Pages,page,"page"),world,Id(Controls,key,"control"),Worlds[page+":"+context].Live);
    }
    public static IDisposable Reason(string reason)
    {var previous=ScopeReason.Value;ScopeReason.Value=reason;return new Restore(previous);}
    private sealed class Restore(string? previous):IDisposable
    {public void Dispose()=>ScopeReason.Value=previous;}
    public static string EventKind(string key)=>LastKinds.GetValueOrDefault(key,"unannotated");
    public static void Emit(string kind,string? key=null,int? length=null,string? classification=null,
        bool? known=null,bool? current=null,int? previousLength=null,string? reason=null,
        string? phase=null,string? failure=null,int? matchingWorlds=null,bool? protectedWorld=null,
        string? page=null,int? context=null,string? frame=null,int? knownCount=null,int? totalChars=null)
    {
        lock(Gate)
        {
            if(file is null||deliveryFailed)return;
            if(sequence>=8192){if(overflow)return;overflow=true;kind="diagnostic_overflow";failure="OTHER";}
            var identity=Identify(key);
            string? p=identity.Page??(page is null?null:Id(Pages,page,"page"));
            string? w=identity.World??(page is not null&&context.HasValue?WorldId(page,context.Value):null);
            string? f=frame is null?null:Id(Frames,frame,"frame");
            var row=new{schemaVersion=1,sequence=++sequence,monotonicTicks=Clock.ElapsedTicks,
                hostProcessId=Environment.ProcessId,ownerProcessId=ownerPid,hostOpaqueId="host_1",sessionOpaqueId="session_1",
                eventKind=kind,pageOpaqueId=p,worldOpaqueId=w,frameOpaqueId=f,controlOpaqueId=identity.Control,
                worldLive=identity.Live,valueLength=length,classification,exactValueAlreadyKnown=known,
                wasCurrentForControl=current,previousCurrentLength=previousLength,commitReason=reason??ScopeReason.Value,
                checkpointPhase=phase,failureReason=failure,firstFailureReason=firstFailure,
                matchingWorlds,protectedWorld,knownCount,totalUtf16=totalChars,
                rawValueRecorded=false,secretHashRecorded=false};
            try{File.AppendAllText(file,JsonSerializer.Serialize(row)+"\n");}
            catch{deliveryFailed=true;} // no logging I/O effect on product semantics
        }
    }
    public static void Fault(string reason,string? key=null,int? length=null,string? detail=null)
    {firstFailure??=reason;Emit("failure",key,length,reason:detail,failure:reason);}
    public static void Value(string key,int length,bool known,bool current,int? previousLength,string? classification)
    {Emit("registry_input",key,length,classification,known,current,previousLength,reason:EventKind(key));}
    public static void Annotate(string page,int context,JsonElement payload)
    {
        string kind=payload.GetProperty("eventKind").GetString()!;
        string[] allowed=["scan","input","change","blur","submit","pagehide","mutation-scan","disconnected-node-scan","final-checkpoint-scan"];
        if(!allowed.Contains(kind)){Fault("OTHER",detail:"DIAGNOSTIC_ANNOTATION_UNKNOWN");return;}
        string key=page+":"+context+":"+payload.GetProperty("key").GetString();
        LastKinds[key]=kind;
        Emit("page_event_observed",key,payload.GetProperty("length").GetInt32(),reason:kind);
    }
    public static void Created(string page,int context,string frame)
    {
        string key=page+":"+context;
        string id="world_incarnation_"+(++worldIncarnation);
        Worlds[key]=(id,true);Emit("world_created",page:page,context:context,frame:frame);
    }
    private static int worldIncarnation;
    public static void Destroyed(string page,int context)
    {
        string key=page+":"+context;WorldId(page,context);var old=Worlds[key];
        Emit("world_destroyed_observed",page:page,context:context);
        Worlds[key]=(old.Id,false);
    }
    public static void Selected(string page,string frame,Dictionary<int,string> contexts,HashSet<int> protectedContexts)
    {
        var matches=contexts.Where(p=>p.Value==frame).Select(p=>p.Key).ToArray();
        Emit("checkpoint_frame_selection",page:page,frame:frame,phase:"SELECT_WORLD",matchingWorlds:matches.Length);
        foreach(var id in matches)Emit("checkpoint_world_candidate",page:page,context:id,frame:frame,protectedWorld:protectedContexts.Contains(id),phase:"SELECT_WORLD");
        if(matches.Length!=1)Fault("CHECKPOINT_CONTINUITY_FAILURE",detail:"FRAME_MATCH_NOT_SINGLE");
        else if(!protectedContexts.Contains(matches[0]))Fault("CAPTURE_CHANNEL_FAILURE",detail:"WORLD_UNPROTECTED");
    }
    public static void RegistryDisposed(int count,int chars)=>Emit("registry_disposed",knownCount:count,totalChars:chars);
}

