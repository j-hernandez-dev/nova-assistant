namespace NovaBrowserHost;

// Infrastructure-only diagnostics. Not a wire DTO, observation or authority.
// Captures the first already-selected failure; it cannot change a decision.
internal enum SensitiveBoundaryFailureReason
{
    OTHER=1, SHORT_COMMITTED_VALUE, NO_PROTECTED_WORLD,
    MULTIPLE_TRACKED_WORLDS, PROTECTED_WORLD_ACK_TIMEOUT,
    PROTECTED_WORLD_ACK_INVALID, CAPTURE_CHANNEL_UNAVAILABLE,
    CHECKPOINT_EXCEPTION, REGISTRY_LIMIT, REGISTRY_EXPIRED,
    LATE_EVENT_AFTER_RETIREMENT_SEAL, RETIREMENT_OWNERSHIP_UNCONFIRMED,
    TERMINAL_CONTINUITY_UNCONFIRMED
}

internal enum SensitiveBoundaryFailureSite
{
    REGISTRY_DISPOSED=1, REGISTRY_ALREADY_UNAVAILABLE, REGISTRY_EXPIRED,
    VALUE_SIZE, PENDING_COUNT, VALUE_COUNT, TOTAL_UTF16, CURRENT_COMMIT_SHORT,
    TRACKING_INSTALL_EXCEPTION, CONTEXT_CREATED_EXCEPTION,
    BINDING_CONTEXT_NOT_TRACKED, VALUE_WORLD_NOT_PROTECTED,
    ACK_WORLD_NOT_PROTECTED, ACK_NONCE_NOT_PENDING,
    CAPTURE_REPORTED_UNAVAILABLE, CAPTURE_UNKNOWN_KIND, BINDING_MESSAGE_EXCEPTION,
    CONTEXT_DESTROYED_EXCEPTION, CONTEXTS_CLEARED_EXCEPTION,
    TRACKING_NOT_INSTALLED, FRAME_WORLD_SELECTION, FRAME_WORLD_NOT_PROTECTED,
    ACK_WAIT_TIMEOUT, CHECKPOINT_EXCEPTION, CAPTURE_CHANNEL_LOST,
    TAKEOVER_BEGIN_WRAPPER, TAKEOVER_END_WRAPPER, UNSPECIFIED,
    RETIREMENT_SEAL, POST_RETIREMENT_EVENT, RETIRED_LINEAGE_AT_TAKEOVER_END
}

internal readonly record struct SensitiveBoundaryFailure(
    SensitiveBoundaryFailureReason Reason, SensitiveBoundaryFailureSite Site,
    string? OpaqueControl=null, int? CurrentLength=null,
    SensitiveTerminalReason? TerminalReason=null, string? CommitCaller=null,
    long? SnapshotRevision=null, long? CurrentRevision=null, string? Generation=null);

internal static class SensitiveBoundaryFailureDiagnostics
{
    // Null in the productive executable. Only a separately compiled test sink
    // can subscribe; no command, flag, IPC or page bridge can install it.
    internal static Action<SensitiveBoundaryFailure>? HarnessObserver = null;
    internal static void Selected(SensitiveBoundaryFailure failure)
    {
        try { HarnessObserver?.Invoke(failure); }
        catch { } // Diagnostic delivery must never affect fail-closed behavior.
    }
}
