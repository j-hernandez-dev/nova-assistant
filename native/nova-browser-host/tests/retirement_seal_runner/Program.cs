using System.Reflection;
using NovaBrowserHost;

// All values remain local to this test process. Only outcomes/codes are printed.
if(args.Length!=1)return 1;
string mode=args[0];
using var r=new SensitiveValueRegistry();
string page="page-a",generation=Guid.NewGuid().ToString("N"),world=Guid.NewGuid().ToString("N"),value=Guid.NewGuid().ToString("N");
SensitiveBoundaryFailureReason? failure=null;
var events=new List<SensitiveTerminalDiagnostic>();
SensitiveBoundaryFailureDiagnostics.HarnessObserver=f=>failure??=f.Reason;
SensitiveTerminalDiagnostics.HarnessObserver=d=>events.Add(d);
try
{
    r.RegisterProtectedWorld(page,generation,world);var id=r.Identity(page,generation,"control-a");
    void Seal()=>r.SealForRetirement(r.SessionOwner,page,generation,world);
    r.ObserveInput(id,2,"",SensitiveInputSignal.CHANGE);
    // Explicit correlated checkpoint proof makes the old rev2 witness real;
    // CHANGE above cannot create it. Retirement only seals/preserves rev5.
    r.Commit(r.ConfirmTerminal(id,2,"",SensitiveTerminalReason.CHECKPOINT)!);
    if(mode.StartsWith("short-",StringComparison.Ordinal))
    {
        string shortValue=new('u',int.Parse(mode[^1..]));r.Observe(id,5,shortValue);
        Seal();Need(failure is null&&Known(r,shortValue)&&!Committed(r,shortValue));
        Need(State(r,id).Current==shortValue&&State(r,id).Revision==5&&State(r,id).Terminal!.Revision==2);
        // Genuine short denial remains a separate strong-boundary contract.
        using var live=new SensitiveValueRegistry();string liveGen=Guid.NewGuid().ToString("N");
        live.RegisterDocument(page,liveGen);var liveId=live.Identity(page,liveGen,"control-a");live.Observe(liveId,5,shortValue);
        Need(Denied(()=>live.Commit(live.ConfirmTerminal(liveId,5,shortValue,SensitiveTerminalReason.SUBMIT)!))&&failure==SensitiveBoundaryFailureReason.SHORT_COMMITTED_VALUE);
    }
    else
    {
        r.Observe(id,5,value);
        switch(mode)
        {
            case "stale-terminal-current":
                Seal();Need(Known(r,value)&&!Committed(r,value)&&State(r,id).Current==value&&State(r,id).Revision==5);
                Need(State(r,id).Terminal!.Revision==2&&!events.Any(d=>d.Kind==SensitiveTerminalDiagnosticKind.TERMINAL_CREATED&&d.Revision==5));
                Need(!events.Any(d=>d.Kind==SensitiveTerminalDiagnosticKind.COMMIT_BEGIN&&d.Revision==5));break;
            case "late-new":case "late-stale":case "late-duplicate":case "sticky-late":
                Seal();var terminal=State(r,id).Terminal;string late="late-"+value;
                long rev=mode=="late-stale"?1:mode=="late-duplicate"?5:6;
                Need(Denied(()=>r.Observe(id,rev,late))&&failure==SensitiveBoundaryFailureReason.LATE_EVENT_AFTER_RETIREMENT_SEAL);
                Need(Known(r,late)&&ReferenceEquals(State(r,id).Terminal,terminal)&&State(r,id).Revision==5);
                Need(Denied(()=>r.Redact("public"))&&Denied(r.Require));
                if(mode=="sticky-late"){string later="again-"+value;Need(Denied(()=>r.Observe(id,7,later))&&Known(r,later));}
                break;
            case "previous-generation":
                Seal();string next=Guid.NewGuid().ToString("N");r.RegisterProtectedWorld(page,next,Guid.NewGuid().ToString("N"));var newer=r.Identity(page,next,"control-a");
                r.Observe(newer,1,"new-"+value);var newerProof=r.ConfirmTerminal(newer,1,"new-"+value,SensitiveTerminalReason.CHECKPOINT);r.Commit(newerProof!);
                Need(Denied(()=>r.Observe(id,6,"old-"+value))&&State(r,newer).Revision==1&&ReferenceEquals(State(r,newer).Terminal,newerProof));break;
            case "pagehide-reuse":case "pagehide-uncommitted":
                r.ObserveInput(id,5,value,SensitiveInputSignal.PAGEHIDE);
                Need(!Committed(r,value)&&State(r,id).Terminal!.Revision==2&&failure is null);
                // PAGEHIDE is weak. This separate exact current checkpoint
                // witness, not page lifecycle notification, is terminal.
                var proof=r.ConfirmTerminal(id,5,value,SensitiveTerminalReason.CHECKPOINT)!;
                r.Commit(proof); // Explicit checkpoint consumes its own witness.
                Seal();Need(ReferenceEquals(State(r,id).Terminal,proof)&&Committed(r,value));
                Need(events.Count(d=>d.Kind==SensitiveTerminalDiagnosticKind.COMMIT_ACCEPTED&&d.Revision==5)==1);break;
            case "wrong-owner":case "wrong-page":case "wrong-generation":case "wrong-world":
                Need(Denied(()=>r.SealForRetirement(mode=="wrong-owner"?"other":r.SessionOwner,mode=="wrong-page"?"other":page,mode=="wrong-generation"?"other":generation,mode=="wrong-world"?"other":world)));
                Need(failure==SensitiveBoundaryFailureReason.RETIREMENT_OWNERSHIP_UNCONFIRMED&&Denied(r.Require)&&!Committed(r,value));break;
            case "unregistered-world":
                string unregistered=Guid.NewGuid().ToString("N");r.RegisterDocument(page,unregistered);Need(Denied(()=>r.SealForRetirement(r.SessionOwner,page,unregistered,world))&&Denied(r.Require));break;
            case "invalid-revision":case "missing-current":
                if(mode=="invalid-revision")State(r,id).Revision=0;else State(r,id).Current=null!;
                Need(Denied(Seal)&&Denied(r.Require)&&!Committed(r,value));break;
            case "multiple-controls":
                var other=r.Identity(page,generation,"control-b");r.Observe(other,8,"second-"+value);
                r.Commit(r.ConfirmTerminal(id,5,value,SensitiveTerminalReason.SUBMIT)!);
                r.Commit(r.ConfirmTerminal(other,8,"second-"+value,SensitiveTerminalReason.SUBMIT)!);
                int beforeSeal=events.Count(d=>d.Kind==SensitiveTerminalDiagnosticKind.COMMIT_BEGIN);Seal();
                Need(Committed(r,value)&&Committed(r,"second-"+value)&&State(r,other).Terminal!.Revision==8&&events.Count(d=>d.Kind==SensitiveTerminalDiagnosticKind.COMMIT_BEGIN)==beforeSeal);break;
            case "no-arbitrary-retire":
                r.RetireDocument(page,generation);Need(!Committed(r,value)&&r.Redact(value)=="[INPUT_REDACTED]"&&State(r,id).Terminal!.Revision==2);break;
            case "forged-engine-reason":
                Need(Denied(()=>r.ConfirmTerminal(id,5,value,(SensitiveTerminalReason)7))&&!Committed(r,value));break;
            case "empty-world":
                string empty=Guid.NewGuid().ToString("N");string emptyWorld=Guid.NewGuid().ToString("N");r.RegisterProtectedWorld(page,empty,emptyWorld);r.SealForRetirement(r.SessionOwner,page,empty,emptyWorld);r.Require();break;
            case "dispose":
                Seal();r.Dispose();Need(!Known(r,value)&&Denied(r.Require));break;
            default:return 2;
        }
    }
    Console.WriteLine("SealPassed=true;exactRevision=true;rawValueRecorded=false");return 0;
}
catch(Exception e){Console.WriteLine("FailureCode="+(e is IpcFailure ipc?ipc.Code:"CONTRACT_FAILED")+";rawValueRecorded=false");return 99;}
static void Need(bool condition){if(!condition)throw new Exception("CONTRACT_FAILED");}
static bool Denied(Action work){try{work();return false;}catch(IpcFailure e){return e.Code=="SECRET_BOUNDARY_UNCONFIRMED";}}
static Dictionary<string,SensitiveValueRegistry.ValueClass> Values(SensitiveValueRegistry r)=>(Dictionary<string,SensitiveValueRegistry.ValueClass>)typeof(SensitiveValueRegistry).GetField("values",BindingFlags.NonPublic|BindingFlags.Instance)!.GetValue(r)!;
static bool Known(SensitiveValueRegistry r,string value)=>Values(r).ContainsKey(value);
static bool Committed(SensitiveValueRegistry r,string value)=>Values(r).TryGetValue(value,out var state)&&state==SensitiveValueRegistry.ValueClass.COMMITTED;
static SensitiveControlState State(SensitiveValueRegistry r,SensitiveControlIdentity id)=>((Dictionary<SensitiveControlIdentity,SensitiveControlState>)typeof(SensitiveValueRegistry).GetField("controls",BindingFlags.NonPublic|BindingFlags.Instance)!.GetValue(r)!)[id];
