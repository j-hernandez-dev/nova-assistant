using System.Text.Json;
using System.Text.Json.Nodes;

namespace NovaBrowserHost;

// Closed read-only v3 guard-observability extension. No navigation, script,
// relaunch, remove-handler, takeover, authority, or arbitrary audit command.
internal static class GuardProtocol
{
    public static JsonElement Parse(byte[] body)
    {
        using var doc = JsonDocument.Parse(body);
        var m = doc.RootElement.Clone(); Protocol.Unique(m);
        Protocol.Need(Protocol.Number(m.GetProperty("schemaVersion")) == 3, "PROTOCOL_MISMATCH");
        var copy = JsonNode.Parse(body)!.AsObject(); copy["schemaVersion"] = 2;
        string type = Protocol.Text(m.GetProperty("messageType"));
        if (type == "request" && Protocol.Text(m.GetProperty("payload").GetProperty("command")) == "guard_metadata")
        {
            Protocol.Closed(m.GetProperty("payload"), "command");
            Protocol.Need(m.GetProperty("pageRef").ValueKind == JsonValueKind.Null);
            copy["payload"] = JsonSerializer.SerializeToNode(new { command = "runtime_metadata" });
        }
        if (type is "response" or "protocol_error" && m.GetProperty("error").ValueKind != JsonValueKind.Null
            && Protocol.Text(m.GetProperty("error").GetProperty("code")) is "GUARD_UNAVAILABLE" or "GUARD_AUDIT_FAILED")
        {
            Protocol.Closed(m.GetProperty("error"), "code");
            copy["error"] = JsonSerializer.SerializeToNode(new { code = "INVALID_STATE" });
        }
        if (type == "response" && m.GetProperty("result").ValueKind != JsonValueKind.Null)
        {
            var r = m.GetProperty("result"); string kind = Protocol.Text(r.GetProperty("kind"));
            if (kind == "handshake")
            {
                Protocol.Need(Protocol.Number(r.GetProperty("ipcVersion")) == 3);
                copy["result"]!["ipcVersion"] = 2;
            }
            else if (kind == "guard_metadata")
            {
                Protocol.Closed(r, "kind", "browserSessionRef", "hostInstanceRef", "contextEpoch", "externalProtocolGuard", "auditGap", "policy", "popupPolicy", "installations", "receipts");
                Protocol.Ref(r.GetProperty("browserSessionRef"), "bws"); Protocol.Ref(r.GetProperty("hostInstanceRef"), "bhi");
                Protocol.Need(Protocol.Text(r.GetProperty("policy")) == "DENY_ALL" && Protocol.Text(r.GetProperty("popupPolicy")) == "DENY_ALL");
                Protocol.Need(Protocol.Text(r.GetProperty("externalProtocolGuard")) is "HOST_PRE_EFFECT_DENY" or "UNKNOWN");
                foreach (var i in r.GetProperty("installations").EnumerateArray()) { Protocol.Closed(i, "pageRef", "sequence"); Protocol.Ref(i.GetProperty("pageRef"), "bwp"); Protocol.Number(i.GetProperty("sequence")); }
                foreach (var i in r.GetProperty("receipts").EnumerateArray()) Protocol.Closed(i, "sequence", "recordId", "pageRef", "cancel", "outcome", "reason", "durable");
                copy["result"] = JsonSerializer.SerializeToNode(new { kind = "ping", state = "READY", hostPid = 1 });
            }
        }
        LifecycleProtocol.Parse(JsonSerializer.SerializeToUtf8Bytes(copy));
        return m;
    }
    public static object Reply(JsonElement m, object? result, string? code = null, string? evt = null)
    {
        var node = JsonSerializer.SerializeToNode(LifecycleProtocol.Reply(m, result, code, evt))!;
        node["schemaVersion"] = 3; return node;
    }
    public static object Fault(string session, string code)
    { var node = JsonSerializer.SerializeToNode(LifecycleProtocol.Fault(session, code))!; node["schemaVersion"] = 3; return node; }
}
