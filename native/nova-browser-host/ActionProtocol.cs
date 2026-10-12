using System.Text.Json;
using System.Text.Json.Nodes;

namespace NovaBrowserHost;

// v4 typed observation/action extension. Not a generic CDP/eval transport.
internal static class ActionProtocol
{
    public static readonly string[] Actions=["CLICK","INPUT_TEXT","SELECT_OPTION","PRESS_KEY","SCROLL","BACK","FORWARD","WAIT","NAVIGATE","FORM_SUBMIT"];
    public static JsonElement Parse(byte[] body)
    {
        try
        {
            using var doc=JsonDocument.Parse(body);var m=doc.RootElement.Clone();Protocol.Unique(m);
            Protocol.Need(Protocol.Number(m.GetProperty("schemaVersion"))==4,"PROTOCOL_MISMATCH");
            var copy=JsonNode.Parse(body)!.AsObject();copy["schemaVersion"]=3;
            string type=Protocol.Text(m.GetProperty("messageType"));var p=m.GetProperty("payload");
            if(type=="request")
            {
                string command=Protocol.Text(p.GetProperty("command"));
                if(command is "capture" or "resolve" or "act" or "navigate_local")
                {
                    Protocol.Need(System.Text.Encoding.UTF8.GetByteCount(p.GetRawText())<=Protocol.MaxPayload,"OVERSIZED_FRAME");
                    Protocol.Ref(m.GetProperty("pageRef"),"bwp");
                    if(command=="capture")
                    {Protocol.Closed(p,"command","maxElements","maxText","maxField");Protocol.Number(p.GetProperty("maxElements"),32);Protocol.Number(p.GetProperty("maxText"),8192);Protocol.Number(p.GetProperty("maxField"),512);}
                    else if(command=="resolve") {Protocol.Closed(p,"command","binding");Protocol.Ref(p.GetProperty("binding"),"wvb");}
                    else if(command=="navigate_local") {Protocol.Closed(p,"command","path");Protocol.Need(Protocol.Text(p.GetProperty("path")) is "index.html" or "other.html" or "frame.html");}
                    else
                    {
                        Protocol.Closed(p,"command","action","binding","text","fields");Protocol.Need(Actions.Contains(Protocol.Text(p.GetProperty("action"))));
                        if(p.GetProperty("binding").ValueKind!=JsonValueKind.Null)Protocol.Ref(p.GetProperty("binding"),"wvb");
                        Protocol.Need(Protocol.Text(p.GetProperty("text")).Length<=2048);
                        Protocol.Need(p.GetProperty("fields").ValueKind==JsonValueKind.Array&&p.GetProperty("fields").GetArrayLength()<=32);
                        foreach(var f in p.GetProperty("fields").EnumerateArray()){Protocol.Closed(f,"binding","value");Protocol.Ref(f.GetProperty("binding"),"wvb");Protocol.Need(Protocol.Text(f.GetProperty("value")).Length<=1024);}
                    }
                    copy["payload"]=JsonSerializer.SerializeToNode(new{command="page_metadata"});
                }
            }
            if(type=="event"&&Protocol.Text(p.GetProperty("event"))=="ACTION_STARTED")
            {Protocol.Closed(p,"event");Protocol.Ref(m.GetProperty("pageRef"),"bwp");copy["pageRef"]=null;copy["payload"]=JsonSerializer.SerializeToNode(new{@event="HOST_READY"});}
            if(type is "response" or "protocol_error"&&m.GetProperty("error").ValueKind!=JsonValueKind.Null)
            {
                Protocol.Closed(m.GetProperty("error"),"code");string code=Protocol.Text(m.GetProperty("error").GetProperty("code"));
                if(code is "STALE_TARGET" or "INVALID_ACTION" or "OBSERVATION_LIMIT" or "BUSY" or "LOCAL_NAVIGATION_FAILED")copy["error"]=JsonSerializer.SerializeToNode(new{code="INVALID_STATE"});
            }
            if(type=="response"&&m.GetProperty("result").ValueKind!=JsonValueKind.Null)
            {
                var r=m.GetProperty("result");string kind=Protocol.Text(r.GetProperty("kind"));
                if(kind=="handshake"){Protocol.Need(Protocol.Number(r.GetProperty("ipcVersion"))==4);copy["result"]!["ipcVersion"]=3;}
                else if(kind is "capture" or "resolve" or "act" or "navigate_local")
                {
                    if(kind=="capture")
                    {Protocol.Closed(r,"kind","engineEpoch","engineVersion","url","title","text","elements","dialogs");foreach(var el in r.GetProperty("elements").EnumerateArray())Protocol.Closed(el,"binding","fingerprint","role","name","kind","capabilities","state","href","isForm");}
                    else if(kind=="resolve")Protocol.Closed(r,"kind","found","fingerprint","origin","capabilities","engineEpoch","engineVersion");
                    else if(kind=="act")Protocol.Closed(r,"kind","started","outcome","error","engineEpoch","engineVersion");
                    else Protocol.Closed(r,"kind","localOnly");
                    copy["result"]=JsonSerializer.SerializeToNode(new{kind="ping",state="READY",hostPid=1});
                }
            }
            GuardProtocol.Parse(JsonSerializer.SerializeToUtf8Bytes(copy));return m;
        }
        catch(IpcFailure){throw;}
        catch(Exception e)when(e is JsonException or InvalidOperationException or KeyNotFoundException or ArgumentException){throw new IpcFailure("MALFORMED_FRAME");}
    }
    public static object Reply(JsonElement m,object? result,string? code=null,string? evt=null)
    {var n=JsonSerializer.SerializeToNode(LifecycleProtocol.Reply(m,result,code,evt))!;n["schemaVersion"]=4;return n;}
    public static object Fault(string session,string code)
    {var n=JsonSerializer.SerializeToNode(LifecycleProtocol.Fault(session,code))!;n["schemaVersion"]=4;return n;}
}
