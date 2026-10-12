using System.Text.Json;
using System.Text.Json.Nodes;
namespace NovaBrowserHost;

// V1.2 productive extension of the same private, PID-bound IPC. Application
// owns Policy/Approval/Grant; no page or model can open this Named Pipe.
internal static class ProductiveProtocol
{
    public static string CanonicalTarget(string value)
    {
        Protocol.Need(value.Length is >0 and <=8192&&!value.Any(c=>char.IsControl(c)||char.IsWhiteSpace(c)||c=='\\'),"INVALID_ACTION");
        Protocol.Need(Uri.TryCreate(value,UriKind.Absolute,out var u)&&(u.Scheme is "http" or "https")&&
            u.UserInfo.Length==0&&u.Fragment.Length==0&&u.Host.Length>0&&u.AbsoluteUri==value,"INVALID_ACTION");
        return value;
    }
    private static void Digest(JsonElement value)
    {string s=Protocol.Text(value);Protocol.Need(s.Length==64&&s.All(c=>"0123456789abcdef".Contains(c)),"INVALID_ACTION");}
    public static JsonElement Parse(byte[] body)
    {
        try
        {
            using var doc=JsonDocument.Parse(body);var m=doc.RootElement.Clone();Protocol.Unique(m);
            Protocol.Need(Protocol.Number(m.GetProperty("schemaVersion"))==6,"PROTOCOL_MISMATCH");
            var copy=JsonNode.Parse(body)!.AsObject();copy["schemaVersion"]=5;
            string type=Protocol.Text(m.GetProperty("messageType"));var p=m.GetProperty("payload");
            if(type=="request")
            {
                string command=Protocol.Text(p.GetProperty("command"));
                if(command=="navigate_admitted")
                {
                    Protocol.Need(System.Text.Encoding.UTF8.GetByteCount(p.GetRawText())<=Protocol.MaxPayload,"OVERSIZED_FRAME");
                    Protocol.Closed(p,"command","capabilityId","canonicalTarget","ownerSessionId","workspaceDigest","policyRevision","authorityDigest","browserContextEpoch");
                    Protocol.Ref(m.GetProperty("pageRef"),"bwp");Protocol.Ref(p.GetProperty("ownerSessionId"),"ses");
                    Protocol.Need(Protocol.Text(p.GetProperty("capabilityId"))=="INTERACTIVE_BROWSER_V1_2","INVALID_ACTION");
                    CanonicalTarget(Protocol.Text(p.GetProperty("canonicalTarget")));Digest(p.GetProperty("workspaceDigest"));Digest(p.GetProperty("authorityDigest"));
                    Protocol.Number(p.GetProperty("policyRevision"));
                    Protocol.Need(p.GetProperty("browserContextEpoch").TryGetInt64(out var contextEpoch)&&contextEpoch>=0);
                    copy["payload"]=JsonSerializer.SerializeToNode(new{command="page_metadata"});
                }
                else if(command=="act")Protocol.Need(new[]{"CLICK","INPUT_TEXT","SELECT_OPTION","PRESS_KEY","NAVIGATE"}.Contains(Protocol.Text(p.GetProperty("action"))),"INVALID_ACTION");
                // Offline fixture navigation is never a productive request.
                else Protocol.Need(command!="navigate_local","INVALID_ACTION");
            }
            if(type=="response"&&m.GetProperty("result").ValueKind!=JsonValueKind.Null)
            {
                var r=m.GetProperty("result");string kind=Protocol.Text(r.GetProperty("kind"));
                if(kind=="handshake"){Protocol.Need(Protocol.Number(r.GetProperty("ipcVersion"))==6);copy["result"]!["ipcVersion"]=5;}
                else if(kind=="navigate_admitted")
                {
                    Protocol.Closed(r,"kind","started","outcome","error","engineEpoch","engineVersion");
                    bool started=r.GetProperty("started").GetBoolean();string outcome=Protocol.Text(r.GetProperty("outcome"));
                    Protocol.Need(outcome is "FAILED_NO_EFFECT_CONFIRMED" or "SUCCEEDED_OBSERVED" or "UNKNOWN");
                    Protocol.Need(started||outcome=="FAILED_NO_EFFECT_CONFIRMED");
                    Protocol.Need(r.GetProperty("engineEpoch").TryGetInt64(out var epoch)&&epoch>=0);
                    Protocol.Need(r.GetProperty("engineVersion").TryGetInt64(out var version)&&version>=0);
                    copy["result"]=JsonSerializer.SerializeToNode(new{kind="ping",state="READY",hostPid=1});
                }
            }
            TransferProtocol.Parse(JsonSerializer.SerializeToUtf8Bytes(copy));return m;
        }
        catch(IpcFailure){throw;}
        catch(Exception e)when(e is JsonException or InvalidOperationException or KeyNotFoundException or ArgumentException){throw new IpcFailure("MALFORMED_FRAME");}
    }
    public static object Reply(JsonElement m,object? result,string? code=null,string? evt=null)
    {var n=JsonSerializer.SerializeToNode(LifecycleProtocol.Reply(m,result,code,evt))!;n["schemaVersion"]=6;return n;}
    public static object Fault(string session,string code)
    {var n=JsonSerializer.SerializeToNode(LifecycleProtocol.Fault(session,code))!;n["schemaVersion"]=6;return n;}
}
