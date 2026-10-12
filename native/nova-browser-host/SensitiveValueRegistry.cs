using System.Diagnostics;
using System.Text;
using System.Runtime.CompilerServices;

namespace NovaBrowserHost;

// Infrastructure only. One instance per owned BrowserSession/host, never
// serialized, persisted, logged, exported or shared with another session.
// Every nonempty buffer actually observed is remembered immediately. Public
// literal protection distinguishes intermediate editing from terminal values.
// Pending only tracks a control's current state; it cannot erase knowledge.
// No eviction on editing, world retirement, navigation, or context epoch change.
internal sealed class SensitiveValueRegistry : IDisposable
{
    internal const int MaxValues=1024, MaxPending=64, MaxValueChars=4096, MaxTotalChars=262144;
    internal static readonly TimeSpan MaxLifetime=TimeSpan.FromMinutes(30);
    internal enum ValueClass { TRANSIENT, COMMITTED }
    private readonly Dictionary<string,ValueClass> values=new(StringComparer.Ordinal);
    private readonly Dictionary<SensitiveControlIdentity,SensitiveControlState> controls=[];
    private readonly Dictionary<(string Page,string Generation),bool> documents=[];
    private readonly Dictionary<(string Page,string Generation),string> protectedWorlds=[];
    private readonly HashSet<(string Page,string Generation)> sealedDocuments=[];
    private readonly Dictionary<string,SensitiveControlIdentity> directControls=new(StringComparer.Ordinal);
    internal string SessionOwner { get; }=Guid.NewGuid().ToString("N");
    private readonly string directGeneration=Guid.NewGuid().ToString("N");
    private int totalChars;
    private readonly Func<TimeSpan> elapsed;
    private bool unavailable, disposed;
    private bool active;
    private SensitiveBoundaryFailure? firstFailure;
    internal void Diagnose(SensitiveBoundaryFailureReason reason, SensitiveBoundaryFailureSite site,
        string? opaqueControl=null, int? currentLength=null, SensitiveTerminalReason? terminalReason=null,
        string? commitCaller=null, long? snapshotRevision=null, long? currentRevision=null, string? generation=null)
    {
        if(firstFailure is not null)return;
        firstFailure=new(reason,site,opaqueControl,currentLength,terminalReason,commitCaller,snapshotRevision,currentRevision,generation);
        SensitiveBoundaryFailureDiagnostics.Selected(firstFailure.Value);
    }
    public SensitiveValueRegistry(Func<TimeSpan>? elapsed=null)
    {var clock=Stopwatch.StartNew();this.elapsed=elapsed??(()=>clock.Elapsed);}
    internal void Activate(){Require();active=true;}
    public void Require()
    {
        if(disposed||unavailable||active&&elapsed()>MaxLifetime)
        {
            Diagnose(disposed||unavailable?SensitiveBoundaryFailureReason.OTHER:SensitiveBoundaryFailureReason.REGISTRY_EXPIRED,
                disposed?SensitiveBoundaryFailureSite.REGISTRY_DISPOSED:unavailable?SensitiveBoundaryFailureSite.REGISTRY_ALREADY_UNAVAILABLE:SensitiveBoundaryFailureSite.REGISTRY_EXPIRED);
            unavailable=true;throw new IpcFailure("SECRET_BOUNDARY_UNCONFIRMED");
        }
    }
    internal void Fail(SensitiveBoundaryFailureReason reason=SensitiveBoundaryFailureReason.OTHER,
        SensitiveBoundaryFailureSite site=SensitiveBoundaryFailureSite.UNSPECIFIED)
    {Diagnose(reason,site);unavailable=true;}
    internal void Input(string key,string value,bool commit,bool humanEditing=false)
    {
        // A scalar observation is not a terminal witness. Legacy commit=true
        // is rejected rather than mapped to an invented fifth authority.
        Require();
        Protocol.Need(!commit,"SECRET_BOUNDARY_UNCONFIRMED");
        if(!directControls.TryGetValue(key,out var identity))
        {RegisterDocument("host-scalar",directGeneration);identity=Identity("host-scalar",directGeneration,key);directControls.Add(key,identity);}
        long revision=controls.TryGetValue(identity,out var state)?checked(state.Revision+1):1;
        Observe(identity,revision,value);
    }
    internal void RegisterDocument(string page,string generation)
    {
        Require();Protocol.Need(page.Length is >0 and <=128&&generation.Length is >0 and <=128,"SECRET_BOUNDARY_UNCONFIRMED");
        var key=(page,generation);if(documents.ContainsKey(key))return;
        if(documents.Count>=MaxValues){Fail(SensitiveBoundaryFailureReason.REGISTRY_LIMIT);Require();}
        documents.Add(key,true);
    }
    internal SensitiveControlIdentity Identity(string page,string generation,string control)=>new(SessionOwner,page,generation,control);
    internal void RegisterProtectedWorld(string page,string generation,string engineUnique)
    {
        Require();Protocol.Need(engineUnique.Length is >0 and <=256,"SECRET_BOUNDARY_UNCONFIRMED");
        RegisterDocument(page,generation);var key=(page,generation);
        Protocol.Need(documents[key]&&!sealedDocuments.Contains(key),"SECRET_BOUNDARY_UNCONFIRMED");
        if(protectedWorlds.TryGetValue(key,out var prior))
        {Protocol.Need(prior==engineUnique,"SECRET_BOUNDARY_UNCONFIRMED");return;}
        Protocol.Need(!protectedWorlds.Values.Contains(engineUnique,StringComparer.Ordinal),"SECRET_BOUNDARY_UNCONFIRMED");
        protectedWorlds.Add(key,engineUnique);
    }
    internal SensitiveControlIdentity DirectIdentity(string key)=>directControls[key];
    internal long ObservedRevision(SensitiveControlIdentity identity)=>controls[identity].Revision;
    internal bool ObserveInput(SensitiveControlIdentity identity,long revision,string value,SensitiveInputSignal signal,bool connected=true)
    {
        Protocol.Need(Enum.IsDefined(signal),"SECRET_BOUNDARY_UNCONFIRMED");
        return Observe(identity,revision,value,connected);
    }
    internal bool Observe(SensitiveControlIdentity identity,long revision,string value,bool connected=true)
    {
        // After a seal, even an old/duplicate buffer remains known, but can
        // never revise sealed current metadata. A late capture invalidates the
        // ordering witness and makes publication/resume sticky fail-closed.
        bool sealedGeneration=sealedDocuments.Contains((identity.Page,identity.Generation));
        if(!sealedGeneration)Require();
        if(value.Length>MaxValueChars){Fail(SensitiveBoundaryFailureReason.REGISTRY_LIMIT,SensitiveBoundaryFailureSite.VALUE_SIZE);Require();}
        Protocol.Need(identity.Owner==SessionOwner&&documents.ContainsKey((identity.Page,identity.Generation))&&identity.Control.Length is >0 and <=128&&revision is >0 and <=9007199254740991,"SECRET_BOUNDARY_UNCONFIRMED");
        Add(value); // stale/retired buffers remain known, without selecting them.
        if(sealedGeneration)
        {
            SensitiveTerminalDiagnostics.Emit(new(SensitiveTerminalDiagnosticKind.LATE_EVENT_AFTER_RETIREMENT_SEAL,identity.Generation,identity.Control,revision,CurrentLength:value.Length,Accepted:false));
            Diagnose(SensitiveBoundaryFailureReason.LATE_EVENT_AFTER_RETIREMENT_SEAL,SensitiveBoundaryFailureSite.POST_RETIREMENT_EVENT);
            Fail();Require();
        }
        if(!documents[(identity.Page,identity.Generation)])return false;
        if(!controls.TryGetValue(identity,out var state))
        {
            if(controls.Count>=MaxValues){Fail(SensitiveBoundaryFailureReason.REGISTRY_LIMIT);Require();}
            state=new(identity);controls.Add(identity,state);
        }
        state.SensitiveObserved|=value.Length>0;
        if(revision<state.Revision)return false;
        if(revision==state.Revision){Protocol.Need(state.Current==value,"SECRET_BOUNDARY_UNCONFIRMED");return state.Active==connected;}
        if(connected&&value.Length>0&&(!state.Active||state.Current.Length==0)&&controls.Values.Count(s=>s.Active&&s.Current.Length>0)>=MaxPending)
        {Fail(SensitiveBoundaryFailureReason.REGISTRY_LIMIT,SensitiveBoundaryFailureSite.PENDING_COUNT);Require();}
        state.Revision=revision;state.Current=value;state.Active=connected;return connected;
    }
    internal SensitiveTerminalSnapshot? ConfirmTerminal(SensitiveControlIdentity identity,long revision,string value,SensitiveTerminalReason reason)
    {
        Protocol.Need(Enum.IsDefined(reason),"SECRET_BOUNDARY_UNCONFIRMED");
        if(!Observe(identity,revision,value))
        {SensitiveTerminalDiagnostics.Emit(new(SensitiveTerminalDiagnosticKind.TERMINAL_REJECTED,identity.Generation,identity.Control,revision,reason,value.Length,controls.TryGetValue(identity,out var prior)?prior.Current.Length:null,false,documents.TryGetValue((identity.Page,identity.Generation),out var live)&&live?SensitiveTerminalDiagnosticRejection.OLD_REVISION:SensitiveTerminalDiagnosticRejection.RETIRED_DOCUMENT));return null;}
        var state=controls[identity];
        if(state.Terminal is not null&&state.Terminal.Revision==revision)
        {Protocol.Need(state.Terminal.Value==value&&state.Terminal.Reason==reason,"SECRET_BOUNDARY_UNCONFIRMED");return state.Terminal;}
        var snapshot=new SensitiveTerminalSnapshot(identity,revision,value,reason);
        state.Terminal=snapshot;
        SensitiveTerminalDiagnostics.Emit(new(SensitiveTerminalDiagnosticKind.TERMINAL_CREATED,identity.Generation,identity.Control,revision,reason,value.Length,state.Current.Length,true));return snapshot;
    }
    private void Add(string value)
    {
        if(value.Length==0||values.ContainsKey(value))return;
        if(values.Count>=MaxValues||value.Length>MaxTotalChars-totalChars){Fail(SensitiveBoundaryFailureReason.REGISTRY_LIMIT,values.Count>=MaxValues?SensitiveBoundaryFailureSite.VALUE_COUNT:SensitiveBoundaryFailureSite.TOTAL_UTF16);Require();}
        values.Add(value,ValueClass.TRANSIENT);totalChars+=value.Length;
    }
    internal void Commit(SensitiveTerminalSnapshot snapshot,[CallerMemberName] string caller="")
    {
        Require();var identity=snapshot.Identity;
        SensitiveTerminalDiagnostics.Emit(new(SensitiveTerminalDiagnosticKind.COMMIT_BEGIN,identity.Generation,identity.Control,snapshot.Revision,snapshot.Reason,snapshot.Value.Length,controls.TryGetValue(identity,out var observed)?observed.Current.Length:null));
        if(!(identity.Owner==SessionOwner&&documents.TryGetValue((identity.Page,identity.Generation),out var diagnosticLive)&&diagnosticLive&&controls.ContainsKey(identity)))
            SensitiveTerminalDiagnostics.Emit(new(SensitiveTerminalDiagnosticKind.COMMIT_REJECTED,identity.Generation,identity.Control,snapshot.Revision,snapshot.Reason,snapshot.Value.Length,Accepted:false,Rejection:SensitiveTerminalDiagnosticRejection.OWNER_OR_DOCUMENT));
        Protocol.Need(identity.Owner==SessionOwner&&documents.TryGetValue((identity.Page,identity.Generation),out var live)&&live&&controls.TryGetValue(identity,out var state),"SECRET_BOUNDARY_UNCONFIRMED");
        var current=controls[identity];
        if(!(current.Active&&ReferenceEquals(current.Terminal,snapshot)&&current.Revision==snapshot.Revision&&current.Current==snapshot.Value))
            SensitiveTerminalDiagnostics.Emit(new(SensitiveTerminalDiagnosticKind.COMMIT_REJECTED,identity.Generation,identity.Control,snapshot.Revision,snapshot.Reason,snapshot.Value.Length,current.Current.Length,false,SensitiveTerminalDiagnosticRejection.WITNESS_OR_CURRENT));
        Protocol.Need(current.Active&&ReferenceEquals(current.Terminal,snapshot)&&current.Revision==snapshot.Revision&&current.Current==snapshot.Value,"SECRET_BOUNDARY_UNCONFIRMED");
        if(ReferenceEquals(current.Committed,snapshot))return;
        string v=snapshot.Value;if(v.Length==0){current.Committed=snapshot;return;}
        Add(v);values[v]=ValueClass.COMMITTED;
        // A terminal credential too short for safe literal matching closes the
        // session boundary, not a word-boundary/min-length availability escape.
        if(v.Length<=3){Diagnose(SensitiveBoundaryFailureReason.SHORT_COMMITTED_VALUE,SensitiveBoundaryFailureSite.CURRENT_COMMIT_SHORT,identity.Page+":"+identity.Generation+":"+identity.Control,v.Length,snapshot.Reason,caller,snapshot.Revision,current.Revision,identity.Generation);Fail();Require();}
        current.Committed=snapshot;
        SensitiveTerminalDiagnostics.Emit(new(SensitiveTerminalDiagnosticKind.COMMIT_ACCEPTED,identity.Generation,identity.Control,snapshot.Revision,snapshot.Reason,v.Length,current.Current.Length,true));
    }
    internal void Retire(string prefix)
    {Require();foreach(var item in directControls.Where(k=>k.Key.StartsWith(prefix,StringComparison.Ordinal)).ToArray())RetireControl(item.Value);}
    private void RetireControl(SensitiveControlIdentity identity)
    {
        if(!controls.TryGetValue(identity,out var state))return;
        SensitiveTerminalDiagnostics.Emit(new(SensitiveTerminalDiagnosticKind.RETIRE_CONTROL,identity.Generation,identity.Control,state.Revision,state.Terminal?.Reason,state.Terminal?.Value.Length,state.Current.Length,state.Terminal is not null&&state.Terminal.Revision==state.Revision,state.Terminal is null?SensitiveTerminalDiagnosticRejection.NO_TERMINAL:state.Terminal.Revision!=state.Revision?SensitiveTerminalDiagnosticRejection.CURRENT_REVISION_MISMATCH:SensitiveTerminalDiagnosticRejection.NONE));
        // Retirement is only a lifecycle witness. Preserve current/revision
        // and monotonic knowledge; never consume even an uncommitted snapshot.
        // A different generation/control cannot resolve this lineage later.
        bool confirmed=state.Committed is not null&&
            ReferenceEquals(state.Terminal,state.Committed)&&
            state.Committed.Revision==state.Revision&&state.Committed.Value==state.Current;
        state.TerminalContinuityUnconfirmed|=state.SensitiveObserved&&!confirmed;
        state.Active=false;
    }
    internal void RetireDocument(string page,string generation)
    {
        Require();if(!documents.TryGetValue((page,generation),out var live)||!live)return;
        SensitiveTerminalDiagnostics.Emit(new(SensitiveTerminalDiagnosticKind.RETIRE_BEGIN,generation));
        foreach(var state in controls.Values.Where(s=>s.Identity.Page==page&&s.Identity.Generation==generation).ToArray())RetireControl(state.Identity);
        documents[(page,generation)]=false;
        SensitiveTerminalDiagnostics.Emit(new(SensitiveTerminalDiagnosticKind.RETIRE_END,generation));
    }
    // Synchronous on the owned WebView2 dispatcher. Sealing freezes lifecycle
    // ordering, NOT semantic terminality. No snapshot or Commit is permitted.
    // Only an engine lifecycle callback with the registered unique world may
    // use this primitive; generic RetireDocument intentionally cannot do so.
    internal void SealForRetirement(string owner,string page,string generation,string engineUnique)
    {
        Require();var key=(page,generation);
        if(!(owner==SessionOwner&&documents.TryGetValue(key,out var live)&&live&&
            protectedWorlds.TryGetValue(key,out var world)&&world==engineUnique&&!sealedDocuments.Contains(key)))
        {Fail(SensitiveBoundaryFailureReason.RETIREMENT_OWNERSHIP_UNCONFIRMED,SensitiveBoundaryFailureSite.RETIREMENT_SEAL);Require();}
        sealedDocuments.Add(key);
        SensitiveTerminalDiagnostics.Emit(new(SensitiveTerminalDiagnosticKind.RETIREMENT_SEALED,generation));
        var selected=controls.Values.Where(s=>s.Active&&s.Identity.Page==page&&s.Identity.Generation==generation).ToArray();
        foreach(var state in selected)
        {
            if(state.Identity.Owner!=SessionOwner||state.Current is null||state.Revision is <=0 or >9007199254740991)
            {Fail(SensitiveBoundaryFailureReason.RETIREMENT_OWNERSHIP_UNCONFIRMED,SensitiveBoundaryFailureSite.RETIREMENT_SEAL);throw new IpcFailure("SECRET_BOUNDARY_UNCONFIRMED");}
        }
        RetireDocument(page,generation);
    }
    internal void RequireTerminalContinuity()
    {
        Require();
        var unresolved=controls.Values.FirstOrDefault(s=>s.TerminalContinuityUnconfirmed);
        if(unresolved is null)return;
        Diagnose(SensitiveBoundaryFailureReason.TERMINAL_CONTINUITY_UNCONFIRMED,
            SensitiveBoundaryFailureSite.RETIRED_LINEAGE_AT_TAKEOVER_END,
            opaqueControl:unresolved.Identity.Control,currentRevision:unresolved.Revision,
            generation:unresolved.Identity.Generation);
        Fail();Require();
    }
    internal void Checkpoint()
    {Require();foreach(var state in controls.Values.Where(s=>s.Active&&s.Terminal is not null&&s.Terminal.Revision==s.Revision).ToArray())Commit(state.Terminal!);Require();}
    internal void Checkpoint(IEnumerable<SensitiveTerminalSnapshot> snapshots)
    {Require();foreach(var snapshot in snapshots)Commit(snapshot);Require();}
    internal void RequireCheckpointCoverage(string page,string generation,IReadOnlyCollection<SensitiveTerminalSnapshot> snapshots)
    {
        Require();Protocol.Need(documents.TryGetValue((page,generation),out var live)&&live,"SECRET_BOUNDARY_UNCONFIRMED");
        foreach(var state in controls.Values.Where(s=>s.Active&&s.Identity.Page==page&&s.Identity.Generation==generation))
            Protocol.Need(snapshots.Any(s=>s.Identity==state.Identity&&s.Revision==state.Revision&&ReferenceEquals(s,state.Terminal)),"SECRET_BOUNDARY_UNCONFIRMED");
    }
    internal void RequireObservedCoverage(string page,string generation,IReadOnlyCollection<(SensitiveControlIdentity Identity,long Revision)> observations)
    {
        Require();Protocol.Need(documents.TryGetValue((page,generation),out var live)&&live,"SECRET_BOUNDARY_UNCONFIRMED");
        foreach(var state in controls.Values.Where(s=>s.Active&&s.Identity.Page==page&&s.Identity.Generation==generation))
            Protocol.Need(observations.Any(s=>s.Identity==state.Identity&&s.Revision==state.Revision),"SECRET_BOUNDARY_UNCONFIRMED");
    }
    internal string Redact(string value)
    {
        Require();
        // Short transient buffers protect exact page-derived leaves only.
        // Committed short values cannot reach publication: Commit closes it.
        if(values.ContainsKey(value))return "[INPUT_REDACTED]";
        var ordered=values.Keys.Where(v=>v.Length>=4).OrderByDescending(v=>v.Length).ThenBy(v=>v,StringComparer.Ordinal).ToArray();
        var result=new StringBuilder();int start=0;
        while(start<value.Length)
        {
            int next=value.Length;string? match=null;
            foreach(var v in ordered){int i=value.IndexOf(v,start,StringComparison.Ordinal);if(i>=0&&i<next){next=i;match=v;}}
            result.Append(value,start,next-start);
            if(match is null)break;
            result.Append("[INPUT_REDACTED]");start=next+match.Length;
        }
        return result.ToString();
    }
    internal string PublicUrl(string value)
    {
        Require();if(!Uri.TryCreate(value,UriKind.Absolute,out var u)||u.Scheme is not("http" or "https"))return "about:blank";
        string s=new UriBuilder(u){UserName="",Password="",Query="",Fragment=""}.Uri.AbsoluteUri;
        // Both the literal and normal URI-escaped spelling of a known value.
        foreach(var v in values.Keys.Where(v=>v.Length>=4||s==v||s.Equals(Uri.EscapeDataString(v),StringComparison.OrdinalIgnoreCase)).OrderByDescending(x=>x.Length))
            if(s.Contains(v,StringComparison.Ordinal)||s.Contains(Uri.EscapeDataString(v),StringComparison.OrdinalIgnoreCase))
            {
                // A fixed internal omission sentinel, NOT a fabricated origin
                // or an actionable remote identity. Python suppresses its refs.
                string origin=u.GetLeftPart(UriPartial.Authority);
                if(v.Length<=3||Redact(origin)!=origin)return "about:blank";
                return origin+"/redacted";
            }
        return s;
    }
    internal string AuditSafe(string value)
    {try{return Redact(value);}catch(IpcFailure){return "[REDACTED]";}}
    public void Dispose(){disposed=true;unavailable=true;values.Clear();controls.Clear();documents.Clear();protectedWorlds.Clear();sealedDocuments.Clear();directControls.Clear();totalChars=0;}
}
