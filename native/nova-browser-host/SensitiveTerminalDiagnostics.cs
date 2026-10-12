namespace NovaBrowserHost;

// Internal, scalar-only test observation. Never a DTO, error or authority.
internal enum SensitiveTerminalDiagnosticKind
{ TERMINAL_RECEIVED, TERMINAL_CREATED, TERMINAL_REJECTED, RETIRE_BEGIN, RETIRE_CONTROL, RETIRE_END, COMMIT_BEGIN, COMMIT_REJECTED, COMMIT_ACCEPTED, RETIREMENT_SEALED, LATE_EVENT_AFTER_RETIREMENT_SEAL }
internal enum SensitiveTerminalDiagnosticRejection
{ NONE, RETIRED_DOCUMENT, OLD_REVISION, NO_TERMINAL, CURRENT_REVISION_MISMATCH, OWNER_OR_DOCUMENT, WITNESS_OR_CURRENT, UNPROTECTED_DOCUMENT }
internal readonly record struct SensitiveTerminalDiagnostic(
    SensitiveTerminalDiagnosticKind Kind,string Generation,string? Control=null,
    long? Revision=null,SensitiveTerminalReason? Reason=null,int? SnapshotLength=null,
    int? CurrentLength=null,bool? Accepted=null,SensitiveTerminalDiagnosticRejection Rejection=SensitiveTerminalDiagnosticRejection.NONE);
internal static class SensitiveTerminalDiagnostics
{
    internal static Action<SensitiveTerminalDiagnostic>? HarnessObserver=null;
    internal static void Emit(SensitiveTerminalDiagnostic data)
    {try{HarnessObserver?.Invoke(data);}catch{}} // Observation cannot decide.
}
