using System.Diagnostics;
using System.Text.Json;

namespace NovaBrowserHost;

internal static class LifecycleServer
{
    public static async Task<int> Run(Dictionary<string, string> options)
    {
        string[] keys=["--pipe","--owner-pid","--session","--instance","--ipc-version","--udf"];
        bool productiveWire=options["--ipc-version"]=="6";
        bool transferWire=options["--ipc-version"]=="5"||productiveWire;
        if(transferWire)keys=[..keys,"--transfer-max-bytes"];
        bool actionWire=options["--ipc-version"]=="4"||transferWire;
        Protocol.Need(options.Keys.ToHashSet().SetEquals(actionWire&&options.ContainsKey("--local-content-root")?[..keys,"--local-content-root"]:keys));
        Protocol.Need(options["--ipc-version"] is "2" or "3" or "4" or "5" or "6", "PROTOCOL_MISMATCH");
        Protocol.Need(!productiveWire||!options.ContainsKey("--local-content-root"),"INVALID_MESSAGE");
        bool guardWire = options["--ipc-version"] == "3" || actionWire;
        Func<byte[], JsonElement> parse = productiveWire?ProductiveProtocol.Parse:transferWire?TransferProtocol.Parse:actionWire ? ActionProtocol.Parse : guardWire ? GuardProtocol.Parse : LifecycleProtocol.Parse;
        object Reply(JsonElement m, object? result, string? code = null, string? evt = null) => productiveWire?ProductiveProtocol.Reply(m,result,code,evt):transferWire?TransferProtocol.Reply(m,result,code,evt):actionWire ? ActionProtocol.Reply(m,result,code,evt) : guardWire ? GuardProtocol.Reply(m, result, code, evt) : LifecycleProtocol.Reply(m, result, code, evt);
        string session = options["--session"], instance = options["--instance"], name = options["--pipe"];
        Protocol.Ref(session, "bws"); Protocol.Ref(instance, "bhi"); Protocol.Ref(name, "nova_browser_host");
        Protocol.Need(int.TryParse(options["--owner-pid"], out var ownerPid) && ownerPid > 0);
        string udf = options["--udf"];
        Protocol.Need(Path.IsPathFullyQualified(udf) && Path.GetFileName(udf) == "nova_wv2_" + session + "_" + instance, "OWNERSHIP_MISMATCH");
        using var owner = Process.GetProcessById(ownerPid);
        using var stop = new CancellationTokenSource();
        _ = owner.WaitForExitAsync().ContinueWith(_ => stop.Cancel(), TaskScheduler.Default);
        using var pipe = NativePipe.Create(name);
        using (var connect = CancellationTokenSource.CreateLinkedTokenSource(stop.Token))
        { connect.CancelAfter(5000); await pipe.WaitForConnectionAsync(connect.Token); }
        Protocol.Need(NativePipe.ClientPid(pipe) == (uint)ownerPid, "UNAUTHORIZED_CLIENT");
        string? localRoot=options.GetValueOrDefault("--local-content-root");
        if(localRoot is not null)Protocol.Need(Path.IsPathFullyQualified(localRoot)&&Directory.Exists(localRoot)&&(File.GetAttributes(localRoot)&FileAttributes.ReparsePoint)==0,"OWNERSHIP_MISMATCH");
        long transferLimit=0;if(transferWire)Protocol.Need(long.TryParse(options["--transfer-max-bytes"],out transferLimit)&&transferLimit>0,"INVALID_MESSAGE");
        using var engine = new WebView2Runtime(udf, instance, browserSession: session,localContentRoot:localRoot,maxTransferBytes:transferLimit,productiveV12:productiveWire);
        bool ready = false, sessionClosed = false;
        var seen = new Dictionary<string, string>(); var ops = new HashSet<string>();
        while (!stop.IsCancellationRequested)
        {
            JsonElement m;
            try { m = await Protocol.Read(pipe, stop.Token, ready ? 30000 : 5000, parse); }
            catch (IpcFailure e)
            { await Protocol.Write(pipe, productiveWire?ProductiveProtocol.Fault(session,e.Code):transferWire?TransferProtocol.Fault(session,e.Code):actionWire ? ActionProtocol.Fault(session,e.Code) : guardWire ? GuardProtocol.Fault(session, e.Code) : LifecycleProtocol.Fault(session, e.Code), stop.Token, parse); return 13; }
            string id = Protocol.Text(m.GetProperty("requestId")), op = Protocol.Text(m.GetProperty("operationId"));
            string? preflightError = Protocol.Text(m.GetProperty("browserSessionRef")) != session ? "CORRELATION_MISMATCH"
                : seen.ContainsKey(id) || !ops.Add(op) ? "DUPLICATE_REQUEST"
                : seen.Count >= Protocol.MaxRequests ? "REQUEST_LIMIT" : null;
            if (preflightError is not null)
            { await Protocol.Write(pipe, Reply(m, null, preflightError), stop.Token, parse); return 13; }
            seen.Add(id, op);
            long remaining = Protocol.Number(m.GetProperty("deadline")) - DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            string? error = null; object? result = null;
            var payload = m.GetProperty("payload");
            try
            {
                Protocol.Need(remaining is > 0 and <= 30000, "TIMEOUT");
                string type = Protocol.Text(m.GetProperty("messageType"));
                Protocol.Need(type is "request" or "cancel", "UNKNOWN_MESSAGE");
                if (type == "cancel")
                {
                    Protocol.Need(ready, "HANDSHAKE_FAILED");
                    string target = Protocol.Text(payload.GetProperty("targetRequestId"));
                    Protocol.Need(seen.TryGetValue(target, out var targetOp) && targetOp == Protocol.Text(payload.GetProperty("targetOperationId")) && target != id, "CORRELATION_MISMATCH");
                    result = new { kind = "cancel", disposition = "ALREADY_COMPLETED" };
                }
                else
                {
                    string cmd = Protocol.Text(payload.GetProperty("command"));
                    if (!ready)
                    {
                        Protocol.Need(cmd == "handshake", "HANDSHAKE_FAILED");
                        Protocol.Need(Protocol.Number(payload.GetProperty("clientPid")) == ownerPid && Protocol.Number(payload.GetProperty("expectedHostPid")) == Environment.ProcessId && Protocol.Text(payload.GetProperty("hostInstanceRef")) == instance, "CORRELATION_MISMATCH");
                        result = new { kind = "handshake", hostIdentity = "nova-browser-host", hostInstanceRef = instance,
                            hostPid = Environment.ProcessId, ownerPid, ipcProtocol = Protocol.Name, ipcVersion = productiveWire?6:transferWire?5:actionWire ? 4 : guardWire ? 3 : 2,
                            features = new[] { "ping", "cancel", "shutdown", "offline_lifecycle" }, activeWebAvailable = false };
                        await Protocol.Write(pipe, Reply(m, result), stop.Token, parse);
                        await Protocol.Write(pipe, Reply(m, null, evt: "HOST_READY"), stop.Token, parse);
                        ready = true; continue;
                    }
                    Protocol.Need(cmd != "handshake", "HANDSHAKE_FAILED");
                    string? page = m.GetProperty("pageRef").ValueKind == JsonValueKind.Null ? null : Protocol.Text(m.GetProperty("pageRef"));
                    Task<object> task;
                    if (cmd == "ping") task = Task.FromResult<object>(new { kind = "ping", state = "READY", hostPid = Environment.ProcessId });
                    else if (cmd == "session_create") task = engine.CreateSession();
                    else if (cmd == "page_create") task = engine.CreatePage(page!);
                    else if (cmd == "page_metadata") task = engine.PageMetadata(page!);
                    else if (cmd == "runtime_metadata") task = engine.Metadata();
                    else if (cmd == "guard_metadata" && guardWire) task = engine.GuardMetadata();
                    else if(cmd=="takeover_begin"&&transferWire)task=engine.BeginTakeover(page!);
                    else if(cmd=="takeover_end"&&transferWire)task=engine.EndTakeover();
                    else if(cmd=="takeover_state"&&transferWire)task=engine.TakeoverState();
                    else if(cmd=="transfer_metadata"&&transferWire)task=engine.TransferMetadata(page!);
                    else if(cmd=="upload"&&transferWire)task=engine.Upload(page!,payload,async()=>await Protocol.Write(pipe,Reply(m,null,evt:"ACTION_STARTED"),stop.Token,parse));
                    else if(cmd=="download"&&transferWire)task=engine.Download(page!,Protocol.Text(payload.GetProperty("binding")),Protocol.Number(payload.GetProperty("maxBytes")),Protocol.Number(m.GetProperty("deadline")),async()=>await Protocol.Write(pipe,Reply(m,null,evt:"ACTION_STARTED"),stop.Token,parse));
                    else if(cmd=="capture"&&actionWire)task=engine.Capture(page!,(int)Protocol.Number(payload.GetProperty("maxElements")),(int)Protocol.Number(payload.GetProperty("maxText")),(int)Protocol.Number(payload.GetProperty("maxField")));
                    else if(cmd=="resolve"&&actionWire)task=engine.Resolve(page!,Protocol.Text(payload.GetProperty("binding")));
                    else if(cmd=="navigate_admitted"&&productiveWire)task=engine.NavigateAdmitted(page!,payload,
                        async()=>await Protocol.Write(pipe,Reply(m,null,evt:"ACTION_STARTED"),stop.Token,parse),(int)remaining);
                    else if(cmd=="navigate_local"&&actionWire)task=engine.NavigateLocal(page!,Protocol.Text(payload.GetProperty("path")));
                    else if(cmd=="act"&&actionWire)task=engine.Act(page!,Protocol.Text(payload.GetProperty("action")),payload.GetProperty("binding").ValueKind==JsonValueKind.Null?null:Protocol.Text(payload.GetProperty("binding")),Protocol.Text(payload.GetProperty("text")),
                        async()=>await Protocol.Write(pipe,Reply(m,null,evt:"ACTION_STARTED"),stop.Token,parse),payload.GetProperty("fields"),(int)remaining);
                    else if (cmd == "page_close") task = engine.ClosePage(page!);
                    else if (cmd is "session_close" or "shutdown")
                    {
                        if (!sessionClosed) { await engine.CloseSession((int)remaining).WaitAsync(TimeSpan.FromMilliseconds(remaining)); sessionClosed = true; }
                        task = Task.FromResult<object>(cmd == "shutdown" ? new { kind = "shutdown", state = "STOPPING" } : new { kind = "session_close", closed = true, cleanupConfirmed = true });
                    }
                    else throw new IpcFailure("NOT_SUPPORTED_IN_CURRENT_BLOCK");
                    result = await task.WaitAsync(TimeSpan.FromMilliseconds(remaining));
                    Protocol.Need(DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() < Protocol.Number(m.GetProperty("deadline")), "TIMEOUT");
                    if (cmd == "shutdown")
                    {
                        await Protocol.Write(pipe, Reply(m, result), stop.Token, parse);
                        await Protocol.Write(pipe, Reply(m, null, evt: "HOST_STOPPED"), stop.Token, parse);
                        return 0;
                    }
                }
            }
            catch (IpcFailure e) { error = e.Code; }
            catch (TimeoutException) { error = "TIMEOUT"; }
            await Protocol.Write(pipe, Reply(m, error is null ? result : null, error), stop.Token, parse);
            // A timed-out/failed resource operation is never retried or later published.
            if (error is not null && error is not ("NOT_SUPPORTED_IN_CURRENT_BLOCK" or "STALE_TARGET" or "INVALID_ACTION" or "OBSERVATION_LIMIT" or "BUSY" or "TAKEOVER_ACTIVE" or "HUMAN_CONTROL_INCOMPLETE" or "TRANSFER_STALE")) return 13;
        }
        return 14;
    }
}
