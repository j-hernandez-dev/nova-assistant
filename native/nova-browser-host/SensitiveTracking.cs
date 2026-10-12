using System.Text.Json;
using Microsoft.Web.WebView2.Core;

namespace NovaBrowserHost;

internal sealed partial class ObservationRuntime
{
    private const string SensitiveWorld="nova-private-sensitive-v2", SensitiveBinding="__nova_sensitive_capture_v2";
    private sealed class ProtectedDocument(string frame,string unique)
    {
        internal string Frame=frame, EngineUnique=unique, Generation=Guid.NewGuid().ToString("N");
        internal string? WireGeneration;
        internal bool Protected, Retired;
    }
    private sealed class SensitiveCheckpointRequest(ProtectedDocument document,bool terminal)
    {
        internal ProtectedDocument Document=document;
        internal bool Terminal=terminal;
        internal TaskCompletionSource<IReadOnlyList<SensitiveTerminalSnapshot>> Done=new(TaskCreationOptions.RunContinuationsAsynchronously);
    }
    private bool trackingInstalled;
    private readonly Dictionary<int,ProtectedDocument> sensitiveContexts=[];
    private readonly Dictionary<string,ProtectedDocument> knownDocuments=new(StringComparer.Ordinal);
    private readonly Dictionary<string,SensitiveCheckpointRequest> checkpoints=[];
    private string? trackingScript;
    private CoreWebView2DevToolsProtocolEventReceiver? bindingReceiver,createdReceiver,destroyedReceiver,clearedReceiver;
    // Fixed private-world producer. Incarnation nonce and revisions are owned
    // by this instrumentation, not page/model data or a public IPC capability.
    private const string TrackingSource="""
(()=>{if(globalThis.__novaSensitiveCheckpoint)return;
const emit=globalThis.__nova_sensitive_capture_v2;
const generation=Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join('');
let id=0;const ids=new WeakMap(),controls=new Set();
const sensitive=e=>e&&['INPUT','TEXTAREA','SELECT'].includes(e.tagName)&&(e.type==='password'||/password|passwd|otp|one.time|recovery|card|cvv|private.?key|token|secret/i.test([e.name,e.id,e.autocomplete,e.getAttribute('aria-label'),e.getAttribute('data-sensitivity-hint')].join(' ')));
const sample=(e,reason)=>{if(!sensitive(e))return null;
if(e.value.length>4096||controls.size>=64&&!ids.has(e)){emit(JSON.stringify({kind:'unavailable',generation}));return null;}
let state=ids.get(e);if(!state){state={key:String(++id),revision:0};ids.set(e,state);}controls.add(e);
if(state.revision>=9007199254740991){emit(JSON.stringify({kind:'unavailable',generation}));return null;}
return {key:state.key,revision:++state.revision,value:e.value,connected:e.isConnected,reason:e.isConnected?reason:null};};
const capture=(e,reason=null)=>{const value=sample(e,reason);if(value)emit(JSON.stringify({kind:'value',generation,...value}));};
const scan=reason=>{for(const e of document.querySelectorAll('input,textarea,select'))capture(e,reason);
for(const e of Array.from(controls))if(!e.isConnected){capture(e);controls.delete(e);}};
document.addEventListener('input',e=>capture(e.target),true);
for(const type of ['change','blur'])document.addEventListener(type,e=>capture(e.target,type.toUpperCase()),true);
document.addEventListener('submit',event=>{for(const e of document.querySelectorAll('input,textarea,select'))if(e.form===event.target)capture(e,'SUBMIT');},true);
addEventListener('pagehide',()=>scan('PAGEHIDE'),true);
new MutationObserver(()=>scan(null)).observe(document,{childList:true,subtree:true});
Object.defineProperty(globalThis,'__novaSensitiveCheckpoint',{value:(nonce,terminal)=>{
const snapshots=[];for(const e of document.querySelectorAll('input,textarea,select')){const value=sample(e,terminal?'CHECKPOINT':null);if(value)snapshots.push(value);}
for(const e of Array.from(controls))if(!e.isConnected){capture(e);controls.delete(e);}
emit(JSON.stringify({kind:'checkpoint',generation,nonce,snapshots}));return true;}});
emit(JSON.stringify({kind:'ready',generation}));scan(null);
})()
""";
    public async Task InstallSensitiveTracking()
    {
        try
        {
            bindingReceiver=view.GetDevToolsProtocolEventReceiver("Runtime.bindingCalled");bindingReceiver.DevToolsProtocolEventReceived+=SensitiveMessage;
            createdReceiver=view.GetDevToolsProtocolEventReceiver("Runtime.executionContextCreated");createdReceiver.DevToolsProtocolEventReceived+=SensitiveContextCreated;
            destroyedReceiver=view.GetDevToolsProtocolEventReceiver("Runtime.executionContextDestroyed");destroyedReceiver.DevToolsProtocolEventReceived+=SensitiveContextDestroyed;
            clearedReceiver=view.GetDevToolsProtocolEventReceiver("Runtime.executionContextsCleared");clearedReceiver.DevToolsProtocolEventReceived+=SensitiveContextsCleared;
            await Cdp("Runtime.enable",new{});await Cdp("Page.enable",new{});
            await Cdp("Runtime.addBinding",new{name=SensitiveBinding,executionContextName=SensitiveWorld});
            trackingScript=(await Cdp("Page.addScriptToEvaluateOnNewDocument",new{source=TrackingSource,worldName=SensitiveWorld,runImmediately=true})).GetProperty("identifier").GetString();
            trackingInstalled=true;
        }
        catch{secrets.Fail(SensitiveBoundaryFailureReason.CAPTURE_CHANNEL_UNAVAILABLE,SensitiveBoundaryFailureSite.TRACKING_INSTALL_EXCEPTION);throw new IpcFailure("SECRET_BOUNDARY_UNCONFIRMED");}
    }
    private void SensitiveContextCreated(object? sender,CoreWebView2DevToolsProtocolEventReceivedEventArgs e)
    {
        try
        {
            using var j=JsonDocument.Parse(e.ParameterObjectAsJson);var c=j.RootElement.GetProperty("context");
            if(c.GetProperty("name").GetString()!=SensitiveWorld)return;
            int id=c.GetProperty("id").GetInt32();
            string frame=c.GetProperty("auxData").GetProperty("frameId").GetString()!;
            string unique=c.GetProperty("uniqueId").GetString()!;
            Protocol.Need(!string.IsNullOrEmpty(unique),"SECRET_BOUNDARY_UNCONFIRMED");
            if(sensitiveContexts.TryGetValue(id,out var prior)&&prior.EngineUnique==unique)return;
            if(sensitiveContexts.TryGetValue(id,out prior))RetireProtected(prior);
            sensitiveContexts[id]=new(frame,unique);
        }
        catch{secrets.Fail(SensitiveBoundaryFailureReason.CAPTURE_CHANNEL_UNAVAILABLE,SensitiveBoundaryFailureSite.CONTEXT_CREATED_EXCEPTION);}
    }
    private SensitiveTerminalSnapshot? ReadSensitiveValue(ProtectedDocument document,JsonElement m,bool checkpoint=false)
    {
        Protocol.Closed(m,"key","revision","value","connected","reason");
        string key=Protocol.Text(m.GetProperty("key")),value=Protocol.Text(m.GetProperty("value"));
        long revision=Protocol.Number(m.GetProperty("revision"));
        bool connected=m.GetProperty("connected").GetBoolean();
        var identity=secrets.Identity(guard.PageIdentity,document.Generation,key);
        SensitiveTerminalReason? diagnosticReason=null;
        if(m.GetProperty("reason").ValueKind==JsonValueKind.String&&Enum.TryParse<SensitiveTerminalReason>(m.GetProperty("reason").GetString(),false,out var parsedReason)&&Enum.IsDefined(parsedReason))diagnosticReason=parsedReason;
        if(diagnosticReason.HasValue)SensitiveTerminalDiagnostics.Emit(new(SensitiveTerminalDiagnosticKind.TERMINAL_RECEIVED,document.Generation,key,revision,diagnosticReason,value.Length));
        if(document.Retired)
        {if(diagnosticReason.HasValue)SensitiveTerminalDiagnostics.Emit(new(SensitiveTerminalDiagnosticKind.TERMINAL_REJECTED,document.Generation,key,revision,diagnosticReason,value.Length,Accepted:false,Rejection:SensitiveTerminalDiagnosticRejection.RETIRED_DOCUMENT));secrets.Observe(identity,revision,value,connected);return null;}
        Protocol.Need(document.Protected,"SECRET_BOUNDARY_UNCONFIRMED");
        if(m.GetProperty("reason").ValueKind==JsonValueKind.Null){secrets.Observe(identity,revision,value,connected);return null;}
        string text=Protocol.Text(m.GetProperty("reason"));
        if(Enum.TryParse<SensitiveInputSignal>(text,false,out var weak)&&Enum.IsDefined(weak))
        {Protocol.Need(!checkpoint,"SECRET_BOUNDARY_UNCONFIRMED");secrets.ObserveInput(identity,revision,value,weak,connected);return null;}
        Protocol.Need(Enum.TryParse<SensitiveTerminalReason>(text,false,out var reason)&&Enum.IsDefined(reason)&&(!checkpoint||reason==SensitiveTerminalReason.CHECKPOINT)&&connected,"SECRET_BOUNDARY_UNCONFIRMED");
        return secrets.ConfirmTerminal(identity,revision,value,reason);
    }
    private void SensitiveMessage(object? sender,CoreWebView2DevToolsProtocolEventReceivedEventArgs e)
    {
        try
        {
            using var j=JsonDocument.Parse(e.ParameterObjectAsJson);var r=j.RootElement;if(r.GetProperty("name").GetString()!=SensitiveBinding)return;
            int context=r.GetProperty("executionContextId").GetInt32();
            using var p=JsonDocument.Parse(r.GetProperty("payload").GetString()!);var m=p.RootElement;
            string kind=Protocol.Text(m.GetProperty("kind")),wire=Protocol.Text(m.GetProperty("generation"));Protocol.Need(wire.Length==32&&wire.All(Uri.IsHexDigit),"SECRET_BOUNDARY_UNCONFIRMED");
            if(kind=="ready")
            {
                Protocol.Closed(m,"kind","generation");
                Protocol.Need(sensitiveContexts.TryGetValue(context,out var world),"SECRET_BOUNDARY_UNCONFIRMED");
                if(knownDocuments.TryGetValue(wire,out var existing)){Protocol.Need(ReferenceEquals(existing,world),"SECRET_BOUNDARY_UNCONFIRMED");return;}
                Protocol.Need(world!.WireGeneration is null&&knownDocuments.Count<SensitiveValueRegistry.MaxValues,"SECRET_BOUNDARY_UNCONFIRMED");
                world.WireGeneration=wire;world.Protected=true;knownDocuments.Add(wire,world);
                secrets.RegisterProtectedWorld(guard.PageIdentity,world.Generation,world.EngineUnique);return;
            }
            Protocol.Need(knownDocuments.TryGetValue(wire,out var document),"SECRET_BOUNDARY_UNCONFIRMED");
            if(!document!.Retired)Protocol.Need(sensitiveContexts.TryGetValue(context,out var current)&&ReferenceEquals(current,document),"SECRET_BOUNDARY_UNCONFIRMED");
            if(kind=="value")
            {
                Protocol.Closed(m,"kind","generation","key","revision","value","connected","reason");
                var payload=JsonSerializer.SerializeToElement(new{key=m.GetProperty("key"),revision=m.GetProperty("revision"),value=m.GetProperty("value"),connected=m.GetProperty("connected"),reason=m.GetProperty("reason")});
                var snapshot=ReadSensitiveValue(document,payload);
                if(snapshot is not null)secrets.Commit(snapshot);
            }
            else if(kind=="checkpoint")
            {
                Protocol.Closed(m,"kind","generation","nonce","snapshots");
                string nonce=Protocol.Text(m.GetProperty("nonce"));
                Protocol.Need(checkpoints.TryGetValue(nonce,out var request)&&ReferenceEquals(request.Document,document)&&!document.Retired,"SECRET_BOUNDARY_UNCONFIRMED");
                var snapshots=new List<SensitiveTerminalSnapshot>();
                var observations=new List<(SensitiveControlIdentity Identity,long Revision)>();
                foreach(var row in m.GetProperty("snapshots").EnumerateArray())
                {
                    // Entry verification has no terminal authority. Its exact
                    // current observations still require correlated coverage.
                    Protocol.Need(request!.Terminal||row.GetProperty("reason").ValueKind==JsonValueKind.Null,"SECRET_BOUNDARY_UNCONFIRMED");
                    var snapshot=ReadSensitiveValue(document,row,request.Terminal);
                    if(request.Terminal){Protocol.Need(snapshot is not null,"SECRET_BOUNDARY_UNCONFIRMED");snapshots.Add(snapshot!);}
                    else observations.Add((secrets.Identity(guard.PageIdentity,document.Generation,Protocol.Text(row.GetProperty("key"))),Protocol.Number(row.GetProperty("revision"))));
                }
                Protocol.Need(snapshots.Count+observations.Count<=SensitiveValueRegistry.MaxPending,"SECRET_BOUNDARY_UNCONFIRMED");
                if(request!.Terminal){Protocol.Need(snapshots.Select(s=>s.Identity).Distinct().Count()==snapshots.Count,"SECRET_BOUNDARY_UNCONFIRMED");secrets.RequireCheckpointCoverage(guard.PageIdentity,document.Generation,snapshots);}
                else{Protocol.Need(observations.Select(s=>s.Identity).Distinct().Count()==observations.Count,"SECRET_BOUNDARY_UNCONFIRMED");secrets.RequireObservedCoverage(guard.PageIdentity,document.Generation,observations);}
                request!.Done.TrySetResult(snapshots);
            }
            else secrets.Fail(kind=="unavailable"?SensitiveBoundaryFailureReason.REGISTRY_LIMIT:SensitiveBoundaryFailureReason.OTHER,
                kind=="unavailable"?SensitiveBoundaryFailureSite.CAPTURE_REPORTED_UNAVAILABLE:SensitiveBoundaryFailureSite.CAPTURE_UNKNOWN_KIND);
        }
        catch{secrets.Fail(SensitiveBoundaryFailureReason.CAPTURE_CHANNEL_UNAVAILABLE,SensitiveBoundaryFailureSite.BINDING_MESSAGE_EXCEPTION);foreach(var p in checkpoints.Values)p.Done.TrySetException(new IpcFailure("SECRET_BOUNDARY_UNCONFIRMED"));}
    }
    private void RetireProtected(ProtectedDocument document)
    {
        if(document.Retired)return;
        if(document.Protected)secrets.SealForRetirement(secrets.SessionOwner,guard.PageIdentity,document.Generation,document.EngineUnique);
        document.Retired=true;
    }
    private void SensitiveContextDestroyed(object? sender,CoreWebView2DevToolsProtocolEventReceivedEventArgs e)
    {try{using var j=JsonDocument.Parse(e.ParameterObjectAsJson);int id=j.RootElement.GetProperty("executionContextId").GetInt32();if(sensitiveContexts.Remove(id,out var document))RetireProtected(document);}catch{secrets.Fail(SensitiveBoundaryFailureReason.CAPTURE_CHANNEL_UNAVAILABLE,SensitiveBoundaryFailureSite.CONTEXT_DESTROYED_EXCEPTION);}}
    private void SensitiveContextsCleared(object? sender,CoreWebView2DevToolsProtocolEventReceivedEventArgs e)
    {try{foreach(var world in sensitiveContexts.Values)RetireProtected(world);sensitiveContexts.Clear();}catch{secrets.Fail(SensitiveBoundaryFailureReason.CAPTURE_CHANNEL_UNAVAILABLE,SensitiveBoundaryFailureSite.CONTEXTS_CLEARED_EXCEPTION);}}
    private async Task SensitiveCheckpoint(bool terminal)
    {
        secrets.Require();Protocol.Need(trackingInstalled&&trackingScript is not null,"SECRET_BOUNDARY_UNCONFIRMED");
        try
        {
            var tree=(await Cdp("Page.getFrameTree",new{})).GetProperty("frameTree");var frames=new List<string>();
            void Walk(JsonElement t){frames.Add(t.GetProperty("frame").GetProperty("id").GetString()!);if(t.TryGetProperty("childFrames",out var c))foreach(var f in c.EnumerateArray())Walk(f);}Walk(tree);
            foreach(var frame in frames)
            {
                var document=sensitiveContexts.Values.Single(p=>p.Frame==frame&&!p.Retired);
                Protocol.Need(document.Protected,"SECRET_BOUNDARY_UNCONFIRMED");
                string nonce=Guid.NewGuid().ToString("N");var request=new SensitiveCheckpointRequest(document,terminal);checkpoints.Add(nonce,request);
                try
                {
                    // Unique engine context identity, not reusable numeric id.
                    var result=await Cdp("Runtime.evaluate",new{expression="globalThis.__novaSensitiveCheckpoint("+JsonSerializer.Serialize(nonce)+","+(terminal?"true":"false")+")",uniqueContextId=document.EngineUnique,returnByValue=true});
                    Protocol.Need(!result.TryGetProperty("exceptionDetails",out _),"SECRET_BOUNDARY_UNCONFIRMED");
                    IReadOnlyList<SensitiveTerminalSnapshot> snapshots;
                    try{snapshots=await request.Done.Task.WaitAsync(TimeSpan.FromSeconds(2));}
                    catch(TimeoutException){secrets.Diagnose(SensitiveBoundaryFailureReason.PROTECTED_WORLD_ACK_TIMEOUT,SensitiveBoundaryFailureSite.ACK_WAIT_TIMEOUT);throw;}
                    Protocol.Need(!document.Retired&&sensitiveContexts.Values.Any(d=>ReferenceEquals(d,document)),"SECRET_BOUNDARY_UNCONFIRMED");
                    if(terminal)secrets.Checkpoint(snapshots);
                }
                finally{checkpoints.Remove(nonce);}
            }
        }
        catch{secrets.Fail(SensitiveBoundaryFailureReason.CHECKPOINT_EXCEPTION,SensitiveBoundaryFailureSite.CHECKPOINT_EXCEPTION);throw new IpcFailure("SECRET_BOUNDARY_UNCONFIRMED");}
    }
    public async Task ProtectHumanInput(){secrets.Activate();await SensitiveCheckpoint(false);}
    public async Task RememberSensitive()
    {
        // Check both sides of the asynchronous live-world checkpoint. A world
        // retired during the await cannot be silently replaced by a new one.
        secrets.RequireTerminalContinuity();
        await SensitiveCheckpoint(true);
        secrets.RequireTerminalContinuity();
    }
    internal void LoseSensitiveChannel(){trackingInstalled=false;secrets.Fail(SensitiveBoundaryFailureReason.CAPTURE_CHANNEL_UNAVAILABLE,SensitiveBoundaryFailureSite.CAPTURE_CHANNEL_LOST);Invalidate(false);}
}
