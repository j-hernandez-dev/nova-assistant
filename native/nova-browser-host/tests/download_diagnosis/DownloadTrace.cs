using System.Diagnostics;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;

namespace NovaBrowserHost;

// Compiled ONLY into the separate diagnostic harness executable. No product
// reference, IPC command, page bridge, authority, downloaded data or URI log.
internal static class DownloadTrace
{
    private static readonly Stopwatch Clock=Stopwatch.StartNew();
    private static readonly List<object> Records=[];
    private static string? root,page;
    private static bool overflow;
    internal static void Record(string kind,object? metadata=null)
    {
        try{if(Records.Count>=256){overflow=true;return;}Records.Add(new{sequence=Records.Count+1,milliseconds=Clock.Elapsed.TotalMilliseconds,kind,metadata});}
        catch{overflow=true;} // Observation cannot decide a product outcome.
    }
    internal static async Task Attach(CoreWebView2 view,string udf,string pageRef)
    {
        root=udf;page=pageRef;
        Record("TRACE_ATTACHED",new{runtimeVersion=view.Environment.BrowserVersionString});
        view.DownloadStarting+=(_,e)=>Observe(()=>Record("NATIVE_DOWNLOAD_STARTING_AFTER_PRODUCT_HANDLER",new{
            e.Cancel,e.Handled,state=e.DownloadOperation.State.ToString(),reason=e.DownloadOperation.InterruptReason.ToString(),
            bytes=e.DownloadOperation.BytesReceived,total=e.DownloadOperation.TotalBytesToReceive,
            targetChars=e.ResultFilePath.Length,parentExists=Directory.Exists(Path.GetDirectoryName(e.ResultFilePath)),
            targetExists=File.Exists(e.ResultFilePath),targetUnderOwnedUdf=e.ResultFilePath.StartsWith(udf+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase)}));
        view.SaveFileSecurityCheckStarting+=(_,e)=>Record("FILE_SECURITY_CHECK_OBSERVED",new{e.CancelSave,e.SuppressDefaultPolicy});
        view.ProcessFailed+=(_,e)=>Record("ENGINE_PROCESS_FAILED",new{kind=e.ProcessFailedKind.ToString()});
        view.NavigationStarting+=(_,e)=>Record("NAVIGATION_STARTING",new{e.IsUserInitiated,e.Cancel});
        foreach(string name in new[]{"Network.loadingFailed","Audits.issueAdded","Log.entryAdded"})
            view.GetDevToolsProtocolEventReceiver(name).DevToolsProtocolEventReceived+=(_,e)=>Cdp(name,e.ParameterObjectAsJson);
        // Observation domains only: no Page/Browser.setDownloadBehavior,
        // automation/userGesture flag, request interception or behavior change.
        foreach(string domain in new[]{"Network","Audits","Log"})
        {
            try{await view.CallDevToolsProtocolMethodAsync(domain+".enable","{}");Record("CDP_OBSERVER_READY",new{domain});}
            catch(Exception e){Record("CDP_OBSERVER_UNAVAILABLE",new{domain,errorType=e.GetType().Name});}
        }
    }
    private static void Cdp(string kind,string json)
    {
        try
        {
            using var d=JsonDocument.Parse(json);var r=d.RootElement;
            if(kind=="Network.loadingFailed")
            {
                string raw=r.GetProperty("errorText").GetString()??"";
                string code=raw.StartsWith("net::ERR_",StringComparison.Ordinal)&&raw.All(c=>char.IsAsciiLetterOrDigit(c)||c is ':' or '_')?raw:"OTHER";
                Record("NETWORK_LOADING_FAILED",new{code,cancelled=r.TryGetProperty("canceled",out var c)&&c.GetBoolean()});
            }
            else if(kind=="Audits.issueAdded")Record("ENGINE_ISSUE",new{code=r.GetProperty("issue").GetProperty("code").GetString()});
            else
            {
                // Never persist arbitrary console/page text. Only a fixed
                // recognized engine diagnostic, otherwise a counter enum.
                var entry=r.GetProperty("entry");string text=entry.GetProperty("text").GetString()??"";
                string code=text.Contains("Download is disallowed",StringComparison.Ordinal)?"ENGINE_DOWNLOAD_DISALLOWED":
                    text.Contains("User activation is required",StringComparison.Ordinal)?"ENGINE_USER_ACTIVATION_REQUIRED":"OTHER_ENTRY";
                Record("ENGINE_LOG_METADATA",new{code});
            }
        }
        catch{Record("DIAGNOSTIC_PARSE_UNAVAILABLE");}
    }
    internal static void Resource(string name,int status,int bytes)
    {Record("OFFLINE_RESOURCE_RETURNED",new{resource=name=="payload.txt"?"PAYLOAD_FIXTURE":name=="large.bin"?"OVERSIZE_FIXTURE":"OTHER_CONTROLLED_RESOURCE",status,bytes});}
    private static void Observe(Action read)
    {try{read();}catch{Record("NATIVE_OBSERVATION_UNAVAILABLE");}}
    internal static void State(CoreWebView2DownloadOperation? op,string phase)
    {Observe(()=>Record(phase,new{state=op?.State.ToString(),reason=op?.InterruptReason.ToString(),bytes=op?.BytesReceived,total=op?.TotalBytesToReceive}));}
    internal static void Flush()
    {
        if(root is null)return;
        try{File.WriteAllText(root+".download-trace.json",JsonSerializer.Serialize(new{schemaVersion=1,hostPid=Environment.ProcessId,pageRef=page,overflow,events=Records},new JsonSerializerOptions{WriteIndented=true}));}
        catch{} // No change to cleanup or product errors.
    }
}
