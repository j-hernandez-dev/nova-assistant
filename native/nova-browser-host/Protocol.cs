using System.Buffers.Binary;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace NovaBrowserHost;

internal sealed class IpcFailure(string code) : Exception(code)
{
    public string Code { get; } = code;
}

internal static class Protocol
{
    public const int MaxFrame = 16384, MaxPayload = 4096, MaxRequests = 4096;
    public const string Name = "nova-browser-host-ipc";
    private static readonly string[] Keys = ["schemaVersion", "messageType", "requestId", "browserSessionRef",
        "pageRef", "operationId", "deadline", "payload", "result", "error"];
    public static readonly HashSet<string> Codes = ["MALFORMED_FRAME", "OVERSIZED_FRAME", "INVALID_MESSAGE",
        "UNKNOWN_MESSAGE", "PROTOCOL_MISMATCH", "CORRELATION_MISMATCH", "DUPLICATE_REQUEST",
        "UNSUPPORTED_COMMAND", "TIMEOUT", "CANCELLED", "DISCONNECTED", "PROCESS_START_FAILED",
        "HANDSHAKE_FAILED", "PROCESS_EXIT_UNEXPECTED", "UNAUTHORIZED_CLIENT", "HOST_NOT_STARTED",
        "INVALID_STATE", "CLEANUP_UNCONFIRMED", "REQUEST_LIMIT"];

    public static void Need(bool ok, string code = "INVALID_MESSAGE")
    { if (!ok) throw new IpcFailure(code); }

    public static string Text(JsonElement e) { Need(e.ValueKind == JsonValueKind.String); return e.GetString()!; }
    public static long Number(JsonElement e, long max = 9007199254740991)
    { Need(e.ValueKind == JsonValueKind.Number && e.TryGetInt64(out _) && e.GetInt64() > 0 && e.GetInt64() <= max); return e.GetInt64(); }
    public static void Ref(JsonElement e, string prefix) => Ref(Text(e), prefix);
    public static void Ref(string value, string prefix) => Need(Regex.IsMatch(value, "^" + prefix + "_[0-9a-f]{32}$", RegexOptions.CultureInvariant));
    public static void Closed(JsonElement e, params string[] names)
    {
        Need(e.ValueKind == JsonValueKind.Object);
        var got = e.EnumerateObject().Select(p => p.Name).ToArray();
        Need(got.Length == names.Length && got.ToHashSet().SetEquals(names));
    }
    internal static void Unique(JsonElement e)
    {
        if (e.ValueKind == JsonValueKind.Object)
        {
            var keys = new HashSet<string>();
            foreach (var p in e.EnumerateObject()) { Need(keys.Add(p.Name)); Unique(p.Value); }
        }
        else if (e.ValueKind == JsonValueKind.Array) foreach (var child in e.EnumerateArray()) Unique(child);
    }

    public static JsonElement Parse(byte[] body)
    {
        try
        {
            using var document = JsonDocument.Parse(body, new JsonDocumentOptions { MaxDepth = 8 });
            var m = document.RootElement.Clone(); Unique(m); Closed(m, Keys);
            Need(Number(m.GetProperty("schemaVersion")) == 1, "PROTOCOL_MISMATCH");
            string type = Text(m.GetProperty("messageType"));
            Need(type is "request" or "response" or "event" or "cancel" or "protocol_error", "UNKNOWN_MESSAGE");
            Ref(m.GetProperty("browserSessionRef"), "bws");
            var page = m.GetProperty("pageRef");
            if (page.ValueKind != JsonValueKind.Null) Ref(page, "bwp");
            if (type == "protocol_error")
                Need(m.GetProperty("requestId").ValueKind == JsonValueKind.Null && m.GetProperty("operationId").ValueKind == JsonValueKind.Null && page.ValueKind == JsonValueKind.Null);
            else { Ref(m.GetProperty("requestId"), "bhr"); Ref(m.GetProperty("operationId"), "op"); }
            Number(m.GetProperty("deadline"));
            var p = m.GetProperty("payload"); Need(p.ValueKind == JsonValueKind.Object);
            Need(System.Text.Encoding.UTF8.GetByteCount(p.GetRawText()) <= MaxPayload);
            if (type is "request" or "cancel" or "event")
            {
                Need(m.GetProperty("result").ValueKind == JsonValueKind.Null && m.GetProperty("error").ValueKind == JsonValueKind.Null);
                if (type == "request")
                {
                    Need(p.TryGetProperty("command", out var cmd)); string c = Text(cmd);
                    Need(c is "handshake" or "ping" or "shutdown" or "reserved_browser", "UNSUPPORTED_COMMAND");
                    if (c == "handshake")
                    {
                        Closed(p, "command", "clientPid", "expectedHostPid", "hostInstanceRef", "protocol");
                        Number(p.GetProperty("clientPid"), uint.MaxValue); Number(p.GetProperty("expectedHostPid"), uint.MaxValue);
                        Ref(p.GetProperty("hostInstanceRef"), "bhi");
                        Need(Text(p.GetProperty("protocol")) == Name, "PROTOCOL_MISMATCH");
                    }
                    else Closed(p, "command");
                    Need((page.ValueKind != JsonValueKind.Null) == (c == "reserved_browser"));
                }
                else if (type == "cancel")
                {
                    Closed(p, "targetRequestId", "targetOperationId"); Ref(p.GetProperty("targetRequestId"), "bhr");
                    Ref(p.GetProperty("targetOperationId"), "op"); Need(page.ValueKind == JsonValueKind.Null);
                }
                else
                {
                    Closed(p, "event"); Need(Text(p.GetProperty("event")) is "HOST_READY" or "HOST_STOPPED");
                    Need(page.ValueKind == JsonValueKind.Null);
                }
            }
            else
            {
                Closed(p);
                var result = m.GetProperty("result"); var error = m.GetProperty("error");
                Need((result.ValueKind == JsonValueKind.Null) != (error.ValueKind == JsonValueKind.Null));
                if (error.ValueKind != JsonValueKind.Null) { Closed(error, "code"); Need(Codes.Contains(Text(error.GetProperty("code")))); }
                else { Need(type == "response"); Result(result); }
            }
            return m;
        }
        catch (IpcFailure) { throw; }
        catch (Exception e) when (e is JsonException or InvalidOperationException or KeyNotFoundException or ArgumentException)
        { throw new IpcFailure("MALFORMED_FRAME"); }
    }

    private static void Result(JsonElement r)
    {
        Need(r.ValueKind == JsonValueKind.Object && r.TryGetProperty("kind", out _));
        switch (Text(r.GetProperty("kind")))
        {
            case "handshake":
                Closed(r, "kind", "hostIdentity", "hostInstanceRef", "hostPid", "ownerPid", "ipcProtocol", "ipcVersion", "features", "activeWebAvailable");
                Need(Text(r.GetProperty("hostIdentity")) == "nova-browser-host" && Text(r.GetProperty("ipcProtocol")) == Name);
                Ref(r.GetProperty("hostInstanceRef"), "bhi"); Number(r.GetProperty("hostPid"), uint.MaxValue); Number(r.GetProperty("ownerPid"), uint.MaxValue);
                Need(Number(r.GetProperty("ipcVersion")) == 1 && r.GetProperty("activeWebAvailable").ValueKind == JsonValueKind.False);
                Need(r.GetProperty("features").ValueKind == JsonValueKind.Array && r.GetProperty("features").EnumerateArray().Select(Text).SequenceEqual(new[] { "ping", "cancel", "shutdown" }));
                break;
            case "ping": Closed(r, "kind", "state", "hostPid"); Need(Text(r.GetProperty("state")) == "READY"); Number(r.GetProperty("hostPid"), uint.MaxValue); break;
            case "shutdown": Closed(r, "kind", "state"); Need(Text(r.GetProperty("state")) == "STOPPING"); break;
            case "cancel": Closed(r, "kind", "disposition"); Need(Text(r.GetProperty("disposition")) == "ALREADY_COMPLETED"); break;
            default: throw new IpcFailure("INVALID_MESSAGE");
        }
    }

    public static async Task<JsonElement> Read(Stream pipe, CancellationToken stop, int budgetMs, Func<byte[], JsonElement>? parser = null)
    {
        using var timer = CancellationTokenSource.CreateLinkedTokenSource(stop); timer.CancelAfter(budgetMs);
        var header = new byte[4]; await pipe.ReadExactlyAsync(header, timer.Token);
        uint length = BinaryPrimitives.ReadUInt32LittleEndian(header);
        Need(length is > 0 and <= MaxFrame, "OVERSIZED_FRAME");
        var body = new byte[length]; await pipe.ReadExactlyAsync(body, timer.Token);
        return (parser ?? Parse)(body);
    }

    public static async Task Write(Stream pipe, object message, CancellationToken stop, Func<byte[], JsonElement>? parser = null)
    {
        byte[] body = JsonSerializer.SerializeToUtf8Bytes(message); (parser ?? Parse)(body);
        Need(body.Length <= MaxFrame, "OVERSIZED_FRAME");
        var header = new byte[4]; BinaryPrimitives.WriteUInt32LittleEndian(header, (uint)body.Length);
        using var timer = CancellationTokenSource.CreateLinkedTokenSource(stop); timer.CancelAfter(5000);
        await pipe.WriteAsync(header, timer.Token); await pipe.WriteAsync(body, timer.Token); await pipe.FlushAsync(timer.Token);
    }

    public static object Reply(JsonElement m, object? result, string? code = null, string? evt = null) => new
    {
        schemaVersion = 1, messageType = evt is null ? "response" : "event",
        requestId = Text(m.GetProperty("requestId")), browserSessionRef = Text(m.GetProperty("browserSessionRef")),
        pageRef = m.GetProperty("pageRef").ValueKind == JsonValueKind.Null ? null : Text(m.GetProperty("pageRef")),
        operationId = Text(m.GetProperty("operationId")), deadline = Number(m.GetProperty("deadline")),
        payload = evt is null ? (object)new { } : new { @event = evt }, result,
        error = code is null ? null : new { code }
    };

    public static object Fault(string session, string code) => new
    {
        schemaVersion = 1, messageType = "protocol_error", requestId = (string?)null, browserSessionRef = session,
        pageRef = (string?)null, operationId = (string?)null, deadline = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() + 5000,
        payload = new { }, result = (object?)null, error = new { code }
    };
}
