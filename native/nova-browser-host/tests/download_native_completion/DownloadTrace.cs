using System.Diagnostics;
using System.IO.MemoryMappedFiles;
using System.Text;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;

namespace NovaBrowserHost;

// Diagnostic build ONLY. Scalar metadata in a bounded, owner-correlated sidecar
// survives host loss; no public IPC, content, URLs, response body or authority.
internal static class DownloadTrace
{
    private const int Capacity=256,SlotBytes=4096,HeaderBytes=256;
    private static readonly Stopwatch Clock=Stopwatch.StartNew();
    private static readonly List<object> Records=[];
    private static MemoryMappedFile? map;
    private static MemoryMappedViewAccessor? live;
    private static string? root,page;
    private static bool overflow,subscribed;
    private static readonly Dictionary<string,string> Requests=[];
    private static string Argument(string key)
    {var a=Environment.GetCommandLineArgs();int at=Array.IndexOf(a,key);return at>=0&&at+1<a.Length?a[at+1]:"";}
    internal static void Record(string kind,object? metadata=null)
    {
        try
        {
            if(Records.Count>=Capacity){overflow=true;live?.Write(28,1);return;}
            var row=new{sequence=Records.Count+1,milliseconds=Clock.Elapsed.TotalMilliseconds,counterTicks=Stopwatch.GetTimestamp(),kind,metadata};
            byte[] bytes=JsonSerializer.SerializeToUtf8Bytes(row);
            if(bytes.Length>SlotBytes-4){overflow=true;live?.Write(28,1);return;}
            Records.Add(row);
            if(live is not null)
            {
                long at=HeaderBytes+(Records.Count-1)*SlotBytes;
                live.WriteArray(at+4,bytes,0,bytes.Length);live.Write(at,bytes.Length);
                live.Write(24,Records.Count); // publish length/count last; no Flush per event
            }
        }
        catch{overflow=true;} // Observer cannot change a product decision.
    }
    private static void Observe(Action read)
    {try{read();}catch{Record("NATIVE_OBSERVATION_UNAVAILABLE");}}
    internal static async Task Attach(CoreWebView2 view,string udf,string pageRef)
    {
        root=udf;page=pageRef;
        using(var file=new FileStream(udf+".native-live.bin",FileMode.CreateNew,FileAccess.ReadWrite,FileShare.ReadWrite))
            file.SetLength(HeaderBytes+Capacity*SlotBytes);
        map=MemoryMappedFile.CreateFromFile(udf+".native-live.bin",FileMode.Open,null,HeaderBytes+Capacity*SlotBytes,MemoryMappedFileAccess.ReadWrite);
        live=map.CreateViewAccessor();
        live.Write(0,0x4e444c36);live.Write(4,1);live.Write(8,Environment.ProcessId);
        live.Write(12,int.Parse(Argument("--owner-pid")));live.Write(16,Stopwatch.Frequency);
        Record("TRACE_ATTACHED",new{runtimeVersion=view.Environment.BrowserVersionString,pageRef});
        view.DownloadStarting+=(_,e)=>Observe(()=>
        {
            var op=e.DownloadOperation;
            Record("NATIVE_DOWNLOAD_STARTING_AFTER_PRODUCT_HANDLER",new{
                e.Cancel,e.Handled,operationCreated=true,state=op.State.ToString(),reason=op.InterruptReason.ToString(),
                bytes=op.BytesReceived,total=op.TotalBytesToReceive});
            op.StateChanged+=(_,_)=>State(op,"NATIVE_STATE_CHANGED");
            op.BytesReceivedChanged+=(_,_)=>State(op,"NATIVE_BYTES_CHANGED");
        });
        subscribed=true;Record("DOWNLOAD_STARTING_SUBSCRIPTION_ACTIVE");
        view.SaveFileSecurityCheckStarting+=(_,e)=>Record("FILE_SECURITY_CHECK_OBSERVED",new{e.CancelSave,e.SuppressDefaultPolicy});
        view.ProcessFailed+=(_,e)=>Record("ENGINE_PROCESS_FAILED",new{kind=e.ProcessFailedKind.ToString()});
        view.NavigationStarting+=(_,e)=>Record("NAVIGATION_STARTING",new{e.IsUserInitiated,e.Cancel,resource=ResourceKind(e.Uri)});
        view.NavigationCompleted+=(_,e)=>Record("NAVIGATION_COMPLETED",new{e.IsSuccess,webError=e.WebErrorStatus.ToString(),currentResource=ResourceKind(view.Source)});
        view.SourceChanged+=(_,e)=>Record("SOURCE_CHANGED",new{e.IsNewDocument,resource=ResourceKind(view.Source)});
        view.WebResourceResponseReceived+=(_,e)=>Observe(()=>
        {
            if(ResourceKind(e.Request.Uri)!="PAYLOAD_FIXTURE")return;
            var headers=e.Response.Headers;
            string disposition=headers.Contains("Content-Disposition")?headers.GetHeader("Content-Disposition"):"";
            string type=headers.Contains("Content-Type")?headers.GetHeader("Content-Type"):"";
            Record("FIXTURE_RESPONSE_RECEIVED",new{status=e.Response.StatusCode,
                contentType=type.StartsWith("text/plain",StringComparison.OrdinalIgnoreCase)?"TEXT_PLAIN":"OTHER",
                disposition=disposition.Length==0?"ABSENT":disposition.StartsWith("attachment",StringComparison.OrdinalIgnoreCase)?"ATTACHMENT":"OTHER"});
        });
        foreach(string name in new[]{"Network.requestWillBeSent","Network.responseReceived","Network.loadingFinished","Network.loadingFailed","Audits.issueAdded","Log.entryAdded"})
            view.GetDevToolsProtocolEventReceiver(name).DevToolsProtocolEventReceived+=(_,e)=>Cdp(name,e.ParameterObjectAsJson);
        bool domainsReady=true;
        foreach(string domain in new[]{"Network","Audits","Log"})
        {
            try{await view.CallDevToolsProtocolMethodAsync(domain+".enable","{}");Record("CDP_OBSERVER_READY",new{domain});}
            catch(Exception e){domainsReady=false;Record("CDP_OBSERVER_UNAVAILABLE",new{domain,errorType=e.GetType().Name});}
        }
        Record("OBSERVER_READY_BEFORE_CONTENT",new{downloadStartingSubscribed=subscribed,domainsReady});
        File.WriteAllText(udf+".native-ready.json",JsonSerializer.Serialize(new{schemaVersion=1,hostPid=Environment.ProcessId,
            ownerPid=int.Parse(Argument("--owner-pid")),browserSessionRef=Argument("--session"),pageRef,
            downloadStartingSubscribed=subscribed,domainsReady,readyCounterTicks=Stopwatch.GetTimestamp(),counterFrequency=Stopwatch.Frequency}));
    }
    private static string ResourceKind(string value)
    {
        if(!Uri.TryCreate(value,UriKind.Absolute,out var u)||u.Scheme!="https"||u.Host is not("nova-local.invalid" or "nova-second.invalid"))return "OTHER";
        return u.AbsolutePath=="/payload.txt"?"PAYLOAD_FIXTURE":u.AbsolutePath=="/index.html"?"INDEX_FIXTURE":"OTHER_CONTROLLED_RESOURCE";
    }
    private static void Cdp(string kind,string json)
    {
        try
        {
            using var d=JsonDocument.Parse(json);var r=d.RootElement;
            if(kind=="Network.requestWillBeSent")
            {
                string resource=ResourceKind(r.GetProperty("request").GetProperty("url").GetString()??"");
                if(resource!="PAYLOAD_FIXTURE")return;
                string id=r.GetProperty("requestId").GetString()!;
                if(Requests.Count>=32){Record("REQUEST_TRACKING_LIMIT");return;}
                Requests.TryAdd(id,"nr_"+Guid.NewGuid().ToString("N"));
                Record("FIXTURE_REQUEST_OBSERVED",new{requestRef=Requests[id],redirect=r.TryGetProperty("redirectResponse",out _)});
            }
            else if(kind.StartsWith("Network.",StringComparison.Ordinal))
            {
                string id=r.GetProperty("requestId").GetString()!;if(!Requests.TryGetValue(id,out var opaque))return;
                if(kind=="Network.responseReceived")Record("FIXTURE_NETWORK_RESPONSE",new{requestRef=opaque,status=r.GetProperty("response").GetProperty("status").GetDouble()});
                else if(kind=="Network.loadingFinished")Record("FIXTURE_LOADING_FINISHED",new{requestRef=opaque});
                else
                {
                    string raw=r.GetProperty("errorText").GetString()??"";
                    string code=raw.StartsWith("net::ERR_",StringComparison.Ordinal)&&raw.All(c=>char.IsAsciiLetterOrDigit(c)||c is ':' or '_')?raw:"OTHER";
                    Record("FIXTURE_LOADING_FAILED",new{requestRef=opaque,code,cancelled=r.TryGetProperty("canceled",out var c)&&c.GetBoolean()});
                }
            }
            else if(kind=="Audits.issueAdded")Record("ENGINE_ISSUE",new{code=r.GetProperty("issue").GetProperty("code").GetString()});
            else
            {
                string text=r.GetProperty("entry").GetProperty("text").GetString()??"";
                string code=text.Contains("Download is disallowed",StringComparison.Ordinal)?"ENGINE_DOWNLOAD_DISALLOWED":
                    text.Contains("User activation is required",StringComparison.Ordinal)?"ENGINE_USER_ACTIVATION_REQUIRED":"OTHER_ENTRY";
                Record("ENGINE_LOG_METADATA",new{code});
            }
        }
        catch{Record("DIAGNOSTIC_PARSE_UNAVAILABLE");}
    }
    internal static void Resource(string name,int status,int bytes)
    {Record("OFFLINE_RESOURCE_RETURNED",new{resource=name=="payload.txt"?"PAYLOAD_FIXTURE":name=="large.bin"?"OVERSIZE_FIXTURE":"OTHER_CONTROLLED_RESOURCE",status,bytes});}
    internal static void State(CoreWebView2DownloadOperation? op,string phase)
    {Observe(()=>Record(phase,new{state=op?.State.ToString(),reason=op?.InterruptReason.ToString(),bytes=op?.BytesReceived,total=op?.TotalBytesToReceive}));}
    internal static void Flush()
    {
        if(root is null)return;
        try{File.WriteAllText(root+".native-complete.json",JsonSerializer.Serialize(new{schemaVersion=1,hostPid=Environment.ProcessId,pageRef=page,overflow,
            counterFrequency=Stopwatch.Frequency,events=Records},new JsonSerializerOptions{WriteIndented=true}));}
        catch{}
    }
}
