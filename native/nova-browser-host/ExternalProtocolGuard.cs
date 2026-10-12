using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;

namespace NovaBrowserHost;

// Infrastructure observation, not Application authority. Exact SecurityAudit v1
// envelope; null ToolCall/Grant/Approval, host-owned observation operation ID.
internal interface IGuardAudit : IDisposable
{
    void Append(object record);
}
internal sealed class DurableGuardAudit(string path) : IGuardAudit
{
    private FileStream? file;
    public void Append(object record)
    {
        file ??= new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read,
            4096, FileOptions.WriteThrough);
        byte[] bytes = JsonSerializer.SerializeToUtf8Bytes(record);
        Protocol.Need(bytes.Length <= 16384, "GUARD_AUDIT_FAILED");
        file.Write(bytes); file.WriteByte(10); file.Flush(true);
    }
    public void Dispose() => file?.Dispose();
}

/// <summary>One binding owns all launch/popup subscriptions for one controller.
/// Cancel first, no deferral/IPC/approval/relaunch. Only disposed after Close.
/// No public native handles and no page-facing bridges.</summary>
internal sealed class ExternalProtocolGuard : IDisposable
{
    private readonly CoreWebView2 view;
    private readonly GuardJournal journal;
    private readonly string page;
    private readonly Action invalidate;
    private bool installed, retired;
    internal string PageIdentity=>page;
    public bool Installed => installed;
    public ExternalProtocolGuard(CoreWebView2 view, GuardJournal journal, string page, Action invalidate)
    {
        this.view = view; this.journal = journal; this.page = page; this.invalidate = invalidate;
        try
        {
            view.LaunchingExternalUriScheme += Launch;
            view.NewWindowRequested += Popup;
            installed = true;
            journal.Installed(page);
        }
        catch
        {
            installed = false; invalidate();
            throw new IpcFailure("GUARD_UNAVAILABLE");
        }
    }
    private void Launch(object? sender, CoreWebView2LaunchingExternalUriSchemeEventArgs e)
    {
        e.Cancel = true; // MUST be the first statement; no optional work before denial.
        try { journal.Denied(page, e.Uri, e.InitiatingOrigin, e.IsUserInitiated, e.Cancel, "EXTERNAL_PROTOCOL_GUARD_DENIAL"); }
        catch { invalidate(); } // Denial already occurred; never claim durable receipt.
    }
    private void Popup(object? sender, CoreWebView2NewWindowRequestedEventArgs e)
    {
        e.Handled = true; // No unowned WebView, default browser, or popup window.
        try { journal.Denied(page, e.Uri, null, e.IsUserInitiated, true, "POPUP_DENIED_PRE_EFFECT"); }
        catch { invalidate(); }
    }
    public void Require()
    {
        if (!installed || journal.Gap) { invalidate(); throw new IpcFailure(journal.Gap ? "GUARD_AUDIT_FAILED" : "GUARD_UNAVAILABLE"); }
    }
    // Every removal invalidates first. There is no removal/allow operation in IPC.
    internal void Revoke()
    { Dispose(); }
    // Called only by runtime after controller.Close. Retiring one page must not
    // invalidate other owned guarded controls. Unexpected Dispose is different.
    internal void RetireAfterControlClosed()
    { retired = true; Dispose(); }
    public void Dispose()
    {
        if (!retired) invalidate();
        installed = false;
        try { view.LaunchingExternalUriScheme -= Launch; view.NewWindowRequested -= Popup; }
        catch (InvalidOperationException) { } // Closed native control.
    }
}

internal sealed class GuardJournal : IDisposable
{
    private readonly string session, instance, stream = Guid.NewGuid().ToString();
    private readonly IGuardAudit audit;
    private readonly List<object> receipts = [];
    private readonly Dictionary<string, long> installation = [];
    private long sequence;
    public bool Gap { get; private set; }
    // Metadata-only native correlation: interception/Cancel-first unchanged.
    public long ContextEpoch { get; set; }=1;
    internal Func<string,string> SensitiveSanitize { get; set; }=value=>value;
    public GuardJournal(string session, string instance, IGuardAudit audit)
    { this.session = session; this.instance = instance; this.audit = audit; }
    public void Installed(string page) => installation.Add(page, ++sequence);
    public bool Owns(string page) => installation.ContainsKey(page) && !Gap;
    internal static string Scheme(string uri)
    {
        int colon = uri.IndexOf(':');
        if (colon is < 1 or > 64) return "redacted";
        string s = uri[..colon].ToLowerInvariant();
        return s.All(c => char.IsAsciiLetterOrDigit(c) || c is '+' or '-' or '.') && char.IsAsciiLetter(s[0]) ? s : "redacted";
    }
    internal static string? Origin(string? origin)
    {
        if (origin is null || !Uri.TryCreate(origin, UriKind.Absolute, out var u) || u.Scheme is not ("http" or "https")) return null;
        // No path/query/userinfo. Hostname itself is not persisted; untrusted data.
        return u.Scheme + "://sha256:" + Hash(u.IdnHost + ":" + u.Port);
    }
    private static string Hash(string text) => Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(text)));
    public void Denied(string page, string uri, string? origin, bool gesture, bool cancelled, string reason)
    {
        Protocol.Need(cancelled && Owns(page) && receipts.Count < 1024, "GUARD_AUDIT_FAILED");
        long n = ++sequence;
        var scope = new { domain = "ACTIVE_WEB", browserSessionRef = session, pageRef = page,
            browserContextEpoch = ContextEpoch, hostInstanceRef = instance, installationSequence = installation[page],
            eventSequence = n, scheme = Scheme(SensitiveSanitize(uri)), initiatingOrigin = Origin(origin is null?null:SensitiveSanitize(origin)),
            userGesture = gesture, cancel = cancelled, authority = "NONE" };
        var record = new { schemaVersion = 1, recordId = Guid.NewGuid().ToString(), auditStreamId = stream,
            auditSequence = n, timestamp = DateTimeOffset.UtcNow.ToString("o"), kind = "policy",
            sessionId = session, turnId = (string?)null, operationId = "host-observation-" + Guid.NewGuid().ToString("N"),
            toolCallId = (string?)null, agentId = (string?)null, tool = "ExternalProtocolGuard", origin = "application",
            data = new { decision = "DENY", reason, action = "external_protocol_launch", resource = Scheme(SensitiveSanitize(uri)) + ":",
                outcome = "DENIED_PRE_EFFECT", effectState = "none", retryAllowed = false, observationScope = scope } };
        try
        {
            audit.Append(record);
            receipts.Add(new { sequence = n, recordId = record.recordId, pageRef = page, cancel = true,
                outcome = "DENIED_PRE_EFFECT", reason, durable = true });
        }
        catch
        {
            Gap = true;
            receipts.Add(new { sequence = n, recordId = (string?)null, pageRef = page, cancel = true,
                outcome = "DENIED_PRE_EFFECT", reason = "GUARD_AUDIT_DELIVERY_FAILED", durable = false });
            throw new IpcFailure("GUARD_AUDIT_FAILED");
        }
    }
    public object Metadata(bool usable) => new { kind = "guard_metadata", browserSessionRef = session,
        hostInstanceRef = instance, contextEpoch = ContextEpoch, externalProtocolGuard = usable && !Gap ? "HOST_PRE_EFFECT_DENY" : "UNKNOWN",
        auditGap = Gap, policy = "DENY_ALL", popupPolicy = "DENY_ALL",
        installations = installation.Select(p => new { pageRef = p.Key, sequence = p.Value }).ToArray(), receipts = receipts.ToArray() };
    public void Dispose() => audit.Dispose();
}
