using System.Reflection;
using NovaBrowserHost;

// Direct host-producer state-machine contracts. No raw values leave C#.
if(args.Length!=1)return 1;
string mode=args[0],page="page-a",gen=Guid.NewGuid().ToString("N"),world=Guid.NewGuid().ToString("N");
using var r=new SensitiveValueRegistry();
r.RegisterProtectedWorld(page,gen,world);var id=r.Identity(page,gen,"control-a");
string value=Guid.NewGuid().ToString("N")+"-terminal!";
var events=new List<SensitiveTerminalDiagnostic>();SensitiveTerminalDiagnostics.HarnessObserver=d=>events.Add(d);
SensitiveBoundaryFailure? failure=null;SensitiveBoundaryFailureDiagnostics.HarnessObserver=f=>failure??=f;
SensitiveControlState Current()=>((Dictionary<SensitiveControlIdentity,SensitiveControlState>)typeof(SensitiveValueRegistry).GetField("controls",BindingFlags.NonPublic|BindingFlags.Instance)!.GetValue(r)!)[id];
Dictionary<string,SensitiveValueRegistry.ValueClass> Values()=>(Dictionary<string,SensitiveValueRegistry.ValueClass>)typeof(SensitiveValueRegistry).GetField("values",BindingFlags.NonPublic|BindingFlags.Instance)!.GetValue(r)!;
bool Transient(string v)=>Values().TryGetValue(v,out var state)&&state==SensitiveValueRegistry.ValueClass.TRANSIENT;
void Weak(SensitiveInputSignal signal,long rev,string v)=>r.ObserveInput(id,rev,v,signal);
void Strong(SensitiveTerminalReason reason,long rev,string v)=>r.Checkpoint([r.ConfirmTerminal(id,rev,v,reason)??throw new IpcFailure("SECRET_BOUNDARY_UNCONFIRMED")]);
try
{
    if(mode.StartsWith("weak-",StringComparison.Ordinal))
    {
        var signal=Enum.Parse<SensitiveInputSignal>(mode.Contains("pagehide")?"PAGEHIDE":mode.Contains("blur")?"BLUR":"CHANGE");
        string observed=mode.EndsWith("long",StringComparison.Ordinal)?value:mode.EndsWith("two",StringComparison.Ordinal)?value[..2]:value[..1];
        Weak(SensitiveInputSignal.INPUT,1,observed);Weak(signal,2,observed);
        Need(Transient(observed)&&Current().Revision==2&&Current().Current==observed&&Current().Terminal is null&&Current().Committed is null);
        Need(!events.Any(d=>d.Kind is SensitiveTerminalDiagnosticKind.TERMINAL_CREATED or SensitiveTerminalDiagnosticKind.COMMIT_BEGIN));
        r.Require();Need(failure is null&&r.Redact(observed)=="[INPUT_REDACTED]");
    }
    else if(mode is "blur-then-end" or "change-then-end")
    {
        Weak(SensitiveInputSignal.INPUT,1,value[..1]);Weak(mode=="blur-then-end"?SensitiveInputSignal.BLUR:SensitiveInputSignal.CHANGE,2,value[..1]);
        Need(Transient(value[..1])&&Current().Terminal is null&&failure is null);
        Weak(SensitiveInputSignal.INPUT,3,value);Strong(SensitiveTerminalReason.CHECKPOINT,3,value);
        Need(Current().Committed!.Value==value&&Current().Committed!.Revision==3&&Transient(value[..1]));
    }
    else if(mode is "change-then-retire" or "blur-then-pagehide")
    {
        Weak(SensitiveInputSignal.INPUT,1,value);Weak(mode=="change-then-retire"?SensitiveInputSignal.CHANGE:SensitiveInputSignal.BLUR,2,value);
        Need(Transient(value)&&Current().Terminal is null);
        if(mode=="change-then-retire")r.SealForRetirement(r.SessionOwner,page,gen,world);
        else
        {
            Weak(SensitiveInputSignal.PAGEHIDE,3,value);
            Need(Transient(value)&&Current().Terminal is null&&failure is null);
            Strong(SensitiveTerminalReason.CHECKPOINT,3,value);
        }
        if(mode=="change-then-retire")
        {Need(Transient(value)&&Current().Terminal is null&&Current().Committed is null&&Current().Current==value&&!Current().Active&&failure is null);}
        else Need(Current().Committed!.Reason==SensitiveTerminalReason.CHECKPOINT);
    }
    else if(mode is "strong-pagehide-long" or "strong-pagehide-short" or "pagehide-retire-long" or "pagehide-retire-short" or "pagehide-end-long" or "pagehide-end-short")
    {
        string v=mode.EndsWith("short",StringComparison.Ordinal)?value[..2]:value;
        Weak(SensitiveInputSignal.INPUT,1,v);Weak(SensitiveInputSignal.PAGEHIDE,2,v);
        Need(Transient(v)&&Current().Current==v&&Current().Revision==2&&Current().Terminal is null&&Current().Committed is null&&failure is null);
        Need(!events.Any(d=>d.Kind is SensitiveTerminalDiagnosticKind.TERMINAL_CREATED or SensitiveTerminalDiagnosticKind.COMMIT_BEGIN));
        var reason=SensitiveTerminalReason.CHECKPOINT;
        if(mode.Contains("retire"))
        {
            r.SealForRetirement(r.SessionOwner,page,gen,world);
            Need(Transient(v)&&Current().Current==v&&Current().Revision==2&&Current().Terminal is null&&Current().Committed is null&&failure is null);
            Need(!events.Any(d=>d.Kind is SensitiveTerminalDiagnosticKind.TERMINAL_CREATED or SensitiveTerminalDiagnosticKind.COMMIT_BEGIN));
            Need(Denied(r.RequireTerminalContinuity)&&failure?.Reason==SensitiveBoundaryFailureReason.TERMINAL_CONTINUITY_UNCONFIRMED&&failure?.TerminalReason is null);
        }
        else
        {
        Action finish=()=>Strong(reason,2,v);
        if(v.Length<=3)
        {Need(Denied(finish)&&failure?.Reason==SensitiveBoundaryFailureReason.SHORT_COMMITTED_VALUE&&failure?.TerminalReason==reason&&failure?.SnapshotRevision==2&&failure?.CurrentRevision==2&&failure?.Generation==gen&&Denied(r.Require));}
        else{finish();Need(Current().Committed!.Reason==reason&&Current().Committed!.Value==v&&r.Redact(v)=="[INPUT_REDACTED]");}
        }
    }
    else if(mode.StartsWith("strong-engine_world_retire-",StringComparison.Ordinal))
    {
        string v=mode.EndsWith("short",StringComparison.Ordinal)?value[..2]:value;
        Weak(SensitiveInputSignal.INPUT,1,v);r.SealForRetirement(r.SessionOwner,page,gen,world);
        Need(Transient(v)&&Current().Current==v&&Current().Revision==1&&Current().Terminal is null&&Current().Committed is null&&failure is null);
        Need(!events.Any(d=>d.Kind is SensitiveTerminalDiagnosticKind.TERMINAL_CREATED or SensitiveTerminalDiagnosticKind.COMMIT_BEGIN));
        Need(Denied(r.RequireTerminalContinuity)&&failure?.Reason==SensitiveBoundaryFailureReason.TERMINAL_CONTINUITY_UNCONFIRMED&&failure?.TerminalReason is null);
    }
    else if(mode.StartsWith("strong-",StringComparison.Ordinal))
    {
        var reason=Enum.Parse<SensitiveTerminalReason>(mode.Split('-')[1].ToUpperInvariant());
        string v=mode.EndsWith("short",StringComparison.Ordinal)?value[..2]:value;
        Weak(SensitiveInputSignal.INPUT,1,v);
        Action finish=()=>Strong(reason,1,v);
        if(v.Length<=3)
        {Need(Denied(finish)&&failure?.Reason==SensitiveBoundaryFailureReason.SHORT_COMMITTED_VALUE&&failure?.TerminalReason==reason&&failure?.SnapshotRevision==1&&failure?.CurrentRevision==1&&failure?.Generation==gen&&Denied(r.Require));}
        else{finish();Need(Current().Committed!.Reason==reason&&Current().Committed!.Value==v&&r.Redact(v)=="[INPUT_REDACTED]");}
    }
    else if(mode.StartsWith("lifecycle-",StringComparison.Ordinal))
    {
        string v=mode.Contains("short")?value[..2]:value;
        Weak(SensitiveInputSignal.INPUT,1,v);
        if(mode is "lifecycle-submit-long-retire" or "lifecycle-checkpoint-long-retire")
        {
            Strong(mode.Contains("submit")?SensitiveTerminalReason.SUBMIT:SensitiveTerminalReason.CHECKPOINT,1,v);
            var committed=Current().Committed;int calls=events.Count(d=>d.Kind==SensitiveTerminalDiagnosticKind.COMMIT_BEGIN);
            r.SealForRetirement(r.SessionOwner,page,gen,world);r.RequireTerminalContinuity();
            Need(ReferenceEquals(Current().Committed,committed)&&Current().Current==v&&Current().Revision==1&&!Current().TerminalContinuityUnconfirmed);
            Need(events.Count(d=>d.Kind==SensitiveTerminalDiagnosticKind.COMMIT_BEGIN)==calls&&r.Redact(v)=="[INPUT_REDACTED]");
        }
        else if(mode=="lifecycle-unconsumed-snapshot")
        {
            var proof=r.ConfirmTerminal(id,1,v,SensitiveTerminalReason.CHECKPOINT)!;
            r.SealForRetirement(r.SessionOwner,page,gen,world);
            Need(Transient(v)&&ReferenceEquals(Current().Terminal,proof)&&Current().Committed is null);
            Need(Denied(r.RequireTerminalContinuity)&&failure?.Reason==SensitiveBoundaryFailureReason.TERMINAL_CONTINUITY_UNCONFIRMED);
        }
        else
        {
            if(mode=="lifecycle-empty-after-sensitive")Weak(SensitiveInputSignal.INPUT,2,"");
            r.SealForRetirement(r.SessionOwner,page,gen,world);
            Need(Transient(v)&&Current().Terminal is null&&Current().Committed is null&&Current().SensitiveObserved&&!Current().Active);
            Need(r.Redact(v)=="[INPUT_REDACTED]"&&!events.Any(d=>d.Kind is SensitiveTerminalDiagnosticKind.TERMINAL_CREATED or SensitiveTerminalDiagnosticKind.COMMIT_BEGIN));
            if(mode=="lifecycle-replacement-no-rebind")
            {
                string next=Guid.NewGuid().ToString("N");r.RegisterProtectedWorld(page,next,Guid.NewGuid().ToString("N"));var replacement=r.Identity(page,next,id.Control);
                r.Observe(replacement,1,value);r.Commit(r.ConfirmTerminal(replacement,1,value,SensitiveTerminalReason.CHECKPOINT)!);
            }
            Need(Denied(r.RequireTerminalContinuity)&&failure?.Reason==SensitiveBoundaryFailureReason.TERMINAL_CONTINUITY_UNCONFIRMED&&failure?.TerminalReason is null&&failure?.Generation==gen);
            Need(Denied(r.Require)&&Denied(()=>r.Redact("public")));
        }
    }
    else if(mode.StartsWith("invalid-authority-",StringComparison.Ordinal))
    {
        Weak(SensitiveInputSignal.INPUT,1,value);
        int obsolete=int.Parse(mode.Split('-')[2]);
        Need(Denied(()=>r.ConfirmTerminal(id,1,value,(SensitiveTerminalReason)obsolete))&&Transient(value)&&Current().Terminal is null);
    }
    else if(mode=="legacy-input-commit-rejected")
    {Need(Denied(()=>r.Input("old",value,true))&&!Values().ContainsKey(value));}
    else if(mode=="entry-coverage-no-commit")
    {
        Weak(SensitiveInputSignal.INPUT,1,value[..2]);r.RequireObservedCoverage(page,gen,[(id,1)]);
        Need(Transient(value[..2])&&Current().Terminal is null&&failure is null);
        Need(Denied(()=>r.RequireObservedCoverage(page,gen,[])));
    }
    else return 2;
    Console.WriteLine("StrongAuthorityPassed=true;securityAssertions=true;rawValueRecorded=false");return 0;
}
catch(Exception e){Console.WriteLine("FailureCode="+(e is IpcFailure ipc?ipc.Code:"CONTRACT_FAILED")+";rawValueRecorded=false");return 99;}
static void Need(bool c){if(!c)throw new Exception("CONTRACT_FAILED");}
static bool Denied(Action work){try{work();return false;}catch(IpcFailure e){return e.Code=="SECRET_BOUNDARY_UNCONFIRMED";}}
