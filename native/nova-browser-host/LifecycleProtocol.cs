using System.Text.Json;
using System.Text.Json.Nodes;

namespace NovaBrowserHost;

// Separate versioned extension: v1 remains strict/unchanged for its clients.
internal static class LifecycleProtocol
{
    public static readonly string[] Commands = ["session_create", "page_create", "page_metadata", "runtime_metadata", "page_close", "session_close"];
    private static readonly string[] EngineErrors = ["RUNTIME_ABSENT", "RUNTIME_INCOMPATIBLE", "ENVIRONMENT_CREATION_FAILED", "CONTROL_CREATION_FAILED",
        "WEBVIEW2_PROCESS_FAILED", "NOT_SUPPORTED_IN_CURRENT_BLOCK", "OWNERSHIP_MISMATCH"];
    public static JsonElement Parse(byte[] body)
    {
        try
        {
            using var doc = JsonDocument.Parse(body, new JsonDocumentOptions { MaxDepth = 8 });
            var m = doc.RootElement.Clone(); Protocol.Unique(m);
            Protocol.Closed(m, "schemaVersion", "messageType", "requestId", "browserSessionRef", "pageRef", "operationId", "deadline", "payload", "result", "error");
            Protocol.Need(Protocol.Number(m.GetProperty("schemaVersion")) == 2, "PROTOCOL_MISMATCH");
            var copy = JsonNode.Parse(body)!.AsObject(); copy["schemaVersion"] = 1;
            string type = Protocol.Text(m.GetProperty("messageType"));
            if (type == "request" && Commands.Contains(Protocol.Text(m.GetProperty("payload").GetProperty("command"))))
            {
                string command = Protocol.Text(m.GetProperty("payload").GetProperty("command"));
                Protocol.Closed(m.GetProperty("payload"), "command");
                Protocol.Need((m.GetProperty("pageRef").ValueKind != JsonValueKind.Null) == command.StartsWith("page_", StringComparison.Ordinal));
                if (m.GetProperty("pageRef").ValueKind != JsonValueKind.Null) Protocol.Ref(m.GetProperty("pageRef"), "bwp");
                copy["pageRef"] = "bwp_" + new string('0', 32); copy["payload"] = JsonSerializer.SerializeToNode(new { command = "reserved_browser" });
            }
            else if (type is "response" or "protocol_error" && m.GetProperty("error").ValueKind != JsonValueKind.Null)
            {
                var error = m.GetProperty("error"); Protocol.Closed(error, "code");
                Protocol.Need(Protocol.Codes.Contains(Protocol.Text(error.GetProperty("code"))) || EngineErrors.Contains(Protocol.Text(error.GetProperty("code"))));
                copy["error"] = JsonSerializer.SerializeToNode(new { code = "INVALID_STATE" });
            }
            else if (type == "response" && m.GetProperty("result").ValueKind != JsonValueKind.Null)
            {
                Result(m.GetProperty("result"));
                copy["result"] = JsonSerializer.SerializeToNode(new { kind = "ping", state = "READY", hostPid = 1 });
            }
            Protocol.Parse(JsonSerializer.SerializeToUtf8Bytes(copy));
            return m;
        }
        catch (IpcFailure) { throw; }
        catch (Exception e) when (e is JsonException or InvalidOperationException or KeyNotFoundException or ArgumentException)
        { throw new IpcFailure("MALFORMED_FRAME"); }
    }
    private static void Result(JsonElement r)
    {
        string kind = Protocol.Text(r.GetProperty("kind"));
        if (kind == "handshake")
        {
            Protocol.Closed(r, "kind", "hostIdentity", "hostInstanceRef", "hostPid", "ownerPid", "ipcProtocol", "ipcVersion", "features", "activeWebAvailable");
            Protocol.Need(Protocol.Number(r.GetProperty("ipcVersion")) == 2 && r.GetProperty("activeWebAvailable").ValueKind == JsonValueKind.False);
            Protocol.Need(r.GetProperty("features").EnumerateArray().Select(Protocol.Text).SequenceEqual(new[] { "ping", "cancel", "shutdown", "offline_lifecycle" }));
            Protocol.Need(Protocol.Text(r.GetProperty("hostIdentity")) == "nova-browser-host" && Protocol.Text(r.GetProperty("ipcProtocol")) == Protocol.Name);
            Protocol.Ref(r.GetProperty("hostInstanceRef"), "bhi"); Protocol.Number(r.GetProperty("hostPid"), uint.MaxValue); Protocol.Number(r.GetProperty("ownerPid"), uint.MaxValue);
        }
        else if (kind == "runtime_metadata")
        {
            Protocol.Closed(r, "kind", "engine", "sdkVersion", "runtimeVersion", "architecture", "platform", "hostInstanceRef", "contextEpoch", "udfIdentity", "processes", "configuration", "requiredApiMetadata");
            Protocol.Closed(r.GetProperty("configuration"), "additionalBrowserArguments", "exclusiveUserDataFolderAccess", "targetCompatibleBrowserVersion", "initialContent", "webMessageEnabled", "hostObjectsAllowed", "devToolsEnabled", "inPrivate");
            Protocol.Closed(r.GetProperty("requiredApiMetadata"), "environment", "controller", "processInfos", "browserProcessExited", "launchingExternalUriSchemeSdk", "externalProtocolGuardCertified");
            foreach (var p in r.GetProperty("processes").EnumerateArray()) Protocol.Closed(p, "pid", "kind", "imageIdentity");
        }
        else if (kind is "session_create" or "page_create" or "page_metadata") Protocol.Closed(r, "kind", "hostInstanceRef", "contextEpoch", "state");
        else if (kind is "page_close" or "session_close") Protocol.Closed(r, "kind", "closed", "cleanupConfirmed");
        else if (kind == "ping") Protocol.Closed(r, "kind", "state", "hostPid");
        else if (kind == "shutdown") Protocol.Closed(r, "kind", "state");
        else if (kind == "cancel") Protocol.Closed(r, "kind", "disposition");
        else throw new IpcFailure("INVALID_MESSAGE");
    }
    public static object Reply(JsonElement m, object? result, string? code = null, string? evt = null) => new
    {
        schemaVersion = 2, messageType = evt is null ? "response" : "event",
        requestId = Protocol.Text(m.GetProperty("requestId")), browserSessionRef = Protocol.Text(m.GetProperty("browserSessionRef")),
        pageRef = m.GetProperty("pageRef").ValueKind == JsonValueKind.Null ? null : Protocol.Text(m.GetProperty("pageRef")),
        operationId = Protocol.Text(m.GetProperty("operationId")), deadline = Protocol.Number(m.GetProperty("deadline")),
        payload = evt is null ? (object)new { } : new { @event = evt }, result, error = code is null ? null : new { code }
    };
    public static object Fault(string session, string code) => new
    {
        schemaVersion = 2, messageType = "protocol_error", requestId = (string?)null, browserSessionRef = session,
        pageRef = (string?)null, operationId = (string?)null, deadline = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() + 5000,
        payload = new { }, result = (object?)null, error = new { code }
    };
}
