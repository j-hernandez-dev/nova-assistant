using System.Text.Json;
using System.Text.Json.Nodes;
namespace NovaBrowserHost;

internal static class TransferProtocol
{
    public static JsonElement Parse(byte[] body)
    {
        try
        {
            using var doc=JsonDocument.Parse(body);var m=doc.RootElement.Clone();Protocol.Unique(m);
            Protocol.Need(Protocol.Number(m.GetProperty("schemaVersion"))==5,"PROTOCOL_MISMATCH");
            var copy=JsonNode.Parse(body)!.AsObject();copy["schemaVersion"]=4;
            string type=Protocol.Text(m.GetProperty("messageType"));var p=m.GetProperty("payload");
            if(type=="request")
            {
                string command=Protocol.Text(p.GetProperty("command"));
                if(command is "takeover_begin" or "transfer_metadata" or "upload" or "download")
                {
                    Protocol.Ref(m.GetProperty("pageRef"),"bwp");
                    Protocol.Need(System.Text.Encoding.UTF8.GetByteCount(p.GetRawText())<=Protocol.MaxPayload,"OVERSIZED_FRAME");
                    if(command=="upload")
                    {
                        Protocol.Closed(p,"command","binding","source","filename","size","mime","sha256");Protocol.Ref(p.GetProperty("binding"),"wvb");Protocol.Ref(p.GetProperty("source"),"wvu");
                        string filename=Protocol.Text(p.GetProperty("filename")),mime=Protocol.Text(p.GetProperty("mime")),digest=Protocol.Text(p.GetProperty("sha256"));
                        Protocol.Need(filename.Length is >0 and <=255&&filename is not ("." or "..")&&!filename.Any(c=>char.IsControl(c)||c is '/' or '\\' or ':')&&p.GetProperty("size").GetInt64()>=0);
                        Protocol.Need(mime.Length is >0 and <=128&&!mime.Any(char.IsControl)&&digest.Length==64&&digest.All(c=>"0123456789abcdef".Contains(c)));
                    }
                    else if(command=="download")
                    {Protocol.Closed(p,"command","binding","maxBytes");Protocol.Ref(p.GetProperty("binding"),"wvb");Protocol.Number(p.GetProperty("maxBytes"));}
                    else Protocol.Closed(p,"command");
                    copy["payload"]=JsonSerializer.SerializeToNode(new{command="page_metadata"});
                }
                if(command is "takeover_end" or "takeover_state")
                {Protocol.Closed(p,"command");Protocol.Need(m.GetProperty("pageRef").ValueKind==JsonValueKind.Null);copy["payload"]=JsonSerializer.SerializeToNode(new{command="guard_metadata"});}
            }
            if(type is "response" or "protocol_error"&&m.GetProperty("error").ValueKind!=JsonValueKind.Null)
            {
                Protocol.Closed(m.GetProperty("error"),"code");string code=Protocol.Text(m.GetProperty("error").GetProperty("code"));
                if(code is "TAKEOVER_ACTIVE" or "HUMAN_CONTROL_INCOMPLETE" or "SECRET_BOUNDARY_UNCONFIRMED" or "TRANSFER_STALE" or "TRANSFER_INTERRUPTED")copy["error"]=JsonSerializer.SerializeToNode(new{code="INVALID_STATE"});
            }
            if(type=="response"&&m.GetProperty("result").ValueKind!=JsonValueKind.Null)
            {
                var r=m.GetProperty("result");string kind=Protocol.Text(r.GetProperty("kind"));
                if(kind=="handshake"){Protocol.Need(Protocol.Number(r.GetProperty("ipcVersion"))==5);copy["result"]!["ipcVersion"]=4;}
                else if(kind=="guard_metadata")copy["result"]!["contextEpoch"]=1;
                else if(kind is "session_create" or "page_create" or "page_metadata" or "runtime_metadata")
                {Protocol.Need(r.GetProperty("contextEpoch").GetInt64()>=0);copy["result"]!["contextEpoch"]=1;}
                else if(kind=="capture")foreach(var el in copy["result"]!["elements"]!.AsArray())el!["capabilities"]=new JsonArray(el["capabilities"]!.AsArray().Where(c=>c!.GetValue<string>() is not ("UPLOAD_FILE" or "DOWNLOAD")).Select(c=>c!.DeepClone()).ToArray());
                else if(kind is "takeover_begin" or "takeover_end" or "takeover_state" or "transfer_metadata" or "download")
                {
                    if(kind=="takeover_state")Protocol.Closed(r,"kind","humanActive","humanCompleted","humanAborted","contextEpoch");
                    else if(kind is "takeover_begin" or "takeover_end")Protocol.Closed(r,"kind","humanActive","contextEpoch");
                    else if(kind=="transfer_metadata")Protocol.Closed(r,"kind","humanPaused","events");
                    else Protocol.Closed(r,"kind","started","outcome","fileToken","size","mime","sha256","suggestedName","origin");
                    copy["result"]=JsonSerializer.SerializeToNode(new{kind="ping",state="READY",hostPid=1});
                }
            }
            ActionProtocol.Parse(JsonSerializer.SerializeToUtf8Bytes(copy));return m;
        }
        catch(IpcFailure){throw;}
        catch(Exception e)when(e is JsonException or InvalidOperationException or KeyNotFoundException or ArgumentException){throw new IpcFailure("MALFORMED_FRAME");}
    }
    public static object Reply(JsonElement m,object? result,string? code=null,string? evt=null)
    {var n=JsonSerializer.SerializeToNode(LifecycleProtocol.Reply(m,result,code,evt))!;n["schemaVersion"]=5;return n;}
    public static object Fault(string session,string code)
    {var n=JsonSerializer.SerializeToNode(LifecycleProtocol.Fault(session,code))!;n["schemaVersion"]=5;return n;}
}
