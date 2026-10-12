using System.Diagnostics;
using System.Text.Json;
using NovaBrowserHost;

// Infrastructure only. Version 1 remains health-only; version 2 adds offline lifecycle.
if (!OperatingSystem.IsWindows()) return 10;
try
{
    if (args.Length is not (8 or 12 or 14 or 16)) return 11;
    var options = new Dictionary<string, string>();
    for (int i = 0; i < args.Length; i += 2) if (!options.TryAdd(args[i], args[i + 1])) return 11;
    if (args.Length is 12 or 14 or 16) return await LifecycleServer.Run(options);
    if (!options.Keys.ToHashSet().SetEquals(new[] { "--pipe", "--owner-pid", "--session", "--instance" })) return 11;
    string name = options["--pipe"], session = options["--session"], instance = options["--instance"];
    Protocol.Ref(name, "nova_browser_host"); Protocol.Ref(session, "bws"); Protocol.Ref(instance, "bhi");
    if (!int.TryParse(options["--owner-pid"], out int ownerPid) || ownerPid <= 0) return 11;
    using var owner = Process.GetProcessById(ownerPid);
    using var stop = new CancellationTokenSource();
    // Keep the original process handle alive: PID reuse cannot become a new owner.
    _ = owner.WaitForExitAsync().ContinueWith(_ => stop.Cancel(), TaskScheduler.Default);
    using var pipe = NativePipe.Create(name);
    using (var connection = CancellationTokenSource.CreateLinkedTokenSource(stop.Token))
    {
        connection.CancelAfter(5000); await pipe.WaitForConnectionAsync(connection.Token);
    }
    if (NativePipe.ClientPid(pipe) != (uint)ownerPid) return 12;
    bool ready = false;
    var seen = new Dictionary<string, string>(); var operations = new HashSet<string>();
    while (!stop.IsCancellationRequested)
    {
        JsonElement message;
        try { message = await Protocol.Read(pipe, stop.Token, ready ? 30000 : 5000); }
        catch (IpcFailure e) { await Protocol.Write(pipe, Protocol.Fault(session, e.Code), stop.Token); return 13; }
        string type = Protocol.Text(message.GetProperty("messageType"));
        Protocol.Need(type is "request" or "cancel", "UNKNOWN_MESSAGE");
        string id = Protocol.Text(message.GetProperty("requestId")), op = Protocol.Text(message.GetProperty("operationId"));
        string? error = null;
        if (Protocol.Text(message.GetProperty("browserSessionRef")) != session) error = "CORRELATION_MISMATCH";
        else if (seen.ContainsKey(id) || !operations.Add(op)) error = "DUPLICATE_REQUEST";
        else if (seen.Count >= Protocol.MaxRequests) error = "REQUEST_LIMIT";
        if (error is not null) { await Protocol.Write(pipe, Protocol.Reply(message, null, error), stop.Token); return 13; }
        seen.Add(id, op);
        long remaining = Protocol.Number(message.GetProperty("deadline")) - DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
        if (remaining <= 0 || remaining > 30000)
        { await Protocol.Write(pipe, Protocol.Reply(message, null, "TIMEOUT"), stop.Token); continue; }
        var payload = message.GetProperty("payload");
        if (type == "cancel")
        {
            Protocol.Need(ready, "HANDSHAKE_FAILED");
            string target = Protocol.Text(payload.GetProperty("targetRequestId"));
            string targetOp = Protocol.Text(payload.GetProperty("targetOperationId"));
            if (!seen.TryGetValue(target, out var actualOp) || actualOp != targetOp || target == id)
            { await Protocol.Write(pipe, Protocol.Reply(message, null, "CORRELATION_MISMATCH"), stop.Token); return 13; }
            // Health operations finish synchronously. Never claim rollback or cancellation of a completed operation.
            await Protocol.Write(pipe, Protocol.Reply(message, new { kind = "cancel", disposition = "ALREADY_COMPLETED" }), stop.Token);
            continue;
        }
        string command = Protocol.Text(payload.GetProperty("command"));
        if (!ready)
        {
            if (command != "handshake")
            { await Protocol.Write(pipe, Protocol.Reply(message, null, "HANDSHAKE_FAILED"), stop.Token); return 13; }
            if (!(Protocol.Number(payload.GetProperty("clientPid")) == ownerPid &&
                Protocol.Number(payload.GetProperty("expectedHostPid")) == Environment.ProcessId &&
                Protocol.Text(payload.GetProperty("hostInstanceRef")) == instance))
            { await Protocol.Write(pipe, Protocol.Reply(message, null, "CORRELATION_MISMATCH"), stop.Token); return 13; }
            await Protocol.Write(pipe, Protocol.Reply(message, new { kind = "handshake", hostIdentity = "nova-browser-host",
                hostInstanceRef = instance, hostPid = Environment.ProcessId, ownerPid, ipcProtocol = Protocol.Name,
                ipcVersion = 1, features = new[] { "ping", "cancel", "shutdown" }, activeWebAvailable = false }), stop.Token);
            ready = true;
            await Protocol.Write(pipe, Protocol.Reply(message, null, evt: "HOST_READY"), stop.Token);
        }
        else if (command == "ping")
            await Protocol.Write(pipe, Protocol.Reply(message, new { kind = "ping", state = "READY", hostPid = Environment.ProcessId }), stop.Token);
        else if (command == "shutdown")
        {
            await Protocol.Write(pipe, Protocol.Reply(message, new { kind = "shutdown", state = "STOPPING" }), stop.Token);
            await Protocol.Write(pipe, Protocol.Reply(message, null, evt: "HOST_STOPPED"), stop.Token);
            return 0;
        }
        else if (command == "reserved_browser")
            await Protocol.Write(pipe, Protocol.Reply(message, null, "UNSUPPORTED_COMMAND"), stop.Token);
        else { await Protocol.Write(pipe, Protocol.Reply(message, null, "HANDSHAKE_FAILED"), stop.Token); return 13; }
    }
    return 14;
}
catch (OperationCanceledException) { return 14; }
catch (EndOfStreamException) { return 15; }
// A rejected client can close before the first read. Windows reports either
// EOF or ERROR_BROKEN_PIPE/NO_DATA/PIPE_NOT_CONNECTED; all mean disconnect,
// never a successful request. Preserve the v1 disconnect contract.
catch (IOException e) when ((e.HResult & 0xffff) is 109 or 232 or 233) { return 15; }
catch (IpcFailure) { return 13; }
catch (Exception) { return 16; } // No hostile payload/secret/path in stdout/stderr.
