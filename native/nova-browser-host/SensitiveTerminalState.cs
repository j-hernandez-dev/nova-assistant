namespace NovaBrowserHost;

// Host-private data, not an IPC DTO or authority token.
internal enum SensitiveInputSignal { INPUT, CHANGE, BLUR, PAGEHIDE }
// Only strong, correlated witnesses have terminal authority. CHECKPOINT is
// specifically takeover END, never entry verification or a generic host flag.
internal enum SensitiveTerminalReason { SUBMIT=3, CHECKPOINT=5 }
internal readonly record struct SensitiveControlIdentity(string Owner,string Page,string Generation,string Control);
internal sealed class SensitiveTerminalSnapshot
{
    internal SensitiveControlIdentity Identity { get; }
    internal long Revision { get; }
    internal string Value { get; }
    internal SensitiveTerminalReason Reason { get; }
    internal SensitiveTerminalSnapshot(SensitiveControlIdentity identity,long revision,string value,SensitiveTerminalReason reason)
    {Identity=identity;Revision=revision;Value=value;Reason=reason;}
}
internal sealed class SensitiveControlState(SensitiveControlIdentity identity)
{
    internal SensitiveControlIdentity Identity { get; }=identity;
    internal long Revision;
    internal string Current="";
    internal bool Active=true;
    internal bool SensitiveObserved;
    internal bool TerminalContinuityUnconfirmed;
    internal SensitiveTerminalSnapshot? Terminal;
    internal SensitiveTerminalSnapshot? Committed;
}
