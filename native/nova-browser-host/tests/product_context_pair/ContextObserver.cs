using System.Diagnostics;
using System.IO.MemoryMappedFiles;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;

namespace NovaBrowserHost;

// Additive diagnostic assembly only. No public command, authority or mutation.
// Native calls/headers/target metadata are inspected only for controlled fixtures.
internal static class ContextObserver
{
    private const int Slots=256,Stride=4096,Header=128;
    private static readonly List<object> Rows=[];
    private static readonly Dictionary<string,string> Aliases=[];
    private static readonly Dictionary<string,string> ObjectWorld=[];
    private static MemoryMappedFile? map;
    private static MemoryMappedViewAccessor? live;
    private static EventWaitHandle? eventSignal;
    private static string? root;
    private static string Alias(string key)
    {if(!Aliases.TryGetValue(key,out var a)){a="opaque_"+Guid.NewGuid().ToString("N");Aliases[key]=a;}return a;}
    private static string Arg(string key)
    {var a=Environment.GetCommandLineArgs();int i=Array.IndexOf(a,key);return i>=0&&i+1<a.Length?a[i+1]:"";}
    private static string Digest(string text)=>Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(text)));
    private static string SafeUrl(string value)
    {if(Uri.TryCreate(value,UriKind.Absolute,out var u)&&u.Scheme=="https"&&(u.Host is "nova-local.invalid" or "nova-second.invalid")&&u.Query.Length==0&&u.Fragment.Length==0)return u.GetLeftPart(UriPartial.Authority)+u.AbsolutePath;return "OTHER";}
    internal static void Record(string kind,object? metadata=null)
    {
        try
        {
            if(Rows.Count>=Slots){live?.Write(24,1);return;}
            var row=new{sequence=Rows.Count+1,counterTicks=Stopwatch.GetTimestamp(),kind,metadata};byte[] b=JsonSerializer.SerializeToUtf8Bytes(row);
            if(b.Length>Stride-4){live?.Write(24,1);return;}Rows.Add(row);
            if(live is not null){long at=Header+(Rows.Count-1)*Stride;live.WriteArray(at+4,b,0,b.Length);live.Write(at,b.Length);live.Write(20,Rows.Count);}
        }
        catch{} // Observation never decides/cancels a product operation.
    }
    internal static void EnvironmentOptions(CoreWebView2EnvironmentOptions o)
    {Record("ENVIRONMENT_OPTIONS",new{o.AdditionalBrowserArguments,o.ExclusiveUserDataFolderAccess,o.TargetCompatibleBrowserVersion});}
    internal static void Attach(CoreWebView2 view,string udf,string page)
    {
        root=udf;
        using(var f=new FileStream(udf+".context.bin",FileMode.CreateNew,FileAccess.ReadWrite,FileShare.ReadWrite))f.SetLength(Header+Slots*Stride);
        map=MemoryMappedFile.CreateFromFile(udf+".context.bin",FileMode.Open,null,Header+Slots*Stride,MemoryMappedFileAccess.ReadWrite);live=map.CreateViewAccessor();
        live.Write(0,0x50435438);live.Write(4,1);live.Write(8,Environment.ProcessId);live.Write(12,int.Parse(Arg("--owner-pid")));
        foreach(var row in Rows.ToArray())
        {byte[] b=JsonSerializer.SerializeToUtf8Bytes(row);int index=Array.IndexOf(Rows.ToArray(),row);live.WriteArray(Header+index*Stride+4,b,0,b.Length);live.Write(Header+index*Stride,b.Length);}
        live.Write(20,Rows.Count);
        string signal="Local\\nova_product_context_"+Arg("--instance");eventSignal=new(false,EventResetMode.ManualReset,signal);
        var s=view.Settings;
        Record("EFFECTIVE_SETTINGS",new{s.IsWebMessageEnabled,s.AreHostObjectsAllowed,s.AreDevToolsEnabled,s.IsPasswordAutosaveEnabled,s.IsGeneralAutofillEnabled,s.AreDefaultScriptDialogsEnabled});
        Record("PROFILE_CONFIG",new{view.Profile.IsInPrivateModeEnabled,udfChars=udf.Length,defaultDownloadFolderChars=view.Profile.DefaultDownloadFolderPath.Length,
            defaultDownloadFolderInsideUdf=view.Profile.DefaultDownloadFolderPath.StartsWith(udf+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase),runtimeVersion=view.Environment.BrowserVersionString,pageRef=page});
        Record("FIXED_SCRIPT_IDENTITY",new{performSha256=Digest(ObservationScripts.Perform),performChars=ObservationScripts.Perform.Length,worldName=ObservationScripts.Version,metaSha256=Digest(ObservationScripts.Meta)});
        view.DownloadStarting+=(_,e)=>
        {
            // Product handler owns Cancel/Handled. This observer never changes them.
            Record("DOWNLOAD_STARTING_OBSERVED",new{e.Cancel,e.Handled,operationCreated=e.DownloadOperation is not null});eventSignal!.Set();
        };
        File.WriteAllText(udf+".context-ready.json",JsonSerializer.Serialize(new{schemaVersion=1,hostPid=Environment.ProcessId,ownerPid=int.Parse(Arg("--owner-pid")),pageRef=page,signal,observerActive=true}));
    }
    internal static void Controller(CoreWebView2Controller c)
    {Record("CONTROLLER_CONFIG",new{c.IsVisible,bounds=new{c.Bounds.X,c.Bounds.Y,c.Bounds.Width,c.Bounds.Height},coreType=c.CoreWebView2.GetType().FullName});}
    internal static void ResourceStart(string uri)
    {Record("RESOURCE_CALLBACK_ENTER",new{uri=SafeUrl(uri)});}
    internal static void ResourceDone(string name,int status,int length)
    {Record("RESOURCE_RESPONSE_CREATED",new{resource=name is "payload.txt" or "download.txt"?"PAYLOAD":"OTHER",status,length,contentDisposition="ABSENT",streamType="MemoryStream(data,false)",explicitDisposal=false});}
    internal static void Target(string objectId,string meta)
    {
        try
        {
        using var d=JsonDocument.Parse(meta);var m=d.RootElement;
        Record("EXACT_DOWNLOAD_TARGET",new{objectRef=Alias(objectId),worldRef=ObjectWorld.GetValueOrDefault(objectId),tag=m.GetProperty("tag").GetString(),href=SafeUrl(m.GetProperty("href").GetString()!),
            visible=m.GetProperty("visible").GetBoolean(),disabled=m.GetProperty("disabled").GetBoolean(),capability=m.GetProperty("caps").EnumerateArray().Any(c=>c.GetString()=="DOWNLOAD")});
        }
        catch{Record("OBSERVER_TARGET_PARSE_UNAVAILABLE");}
    }
    internal static void Call(string id,string function,object[]? arguments)
    {
        if(function!=ObservationScripts.Perform&&function!=ObservationScripts.Meta&&function!="function(){return this.href;}")return;
        Record(function==ObservationScripts.Perform?"PRE_ACTIVATION_PERFORM":"TARGET_CALL",new{objectRef=Alias(id),worldRef=ObjectWorld.GetValueOrDefault(id),functionSha256=Digest(function),functionChars=function.Length,
            argumentCount=arguments?.Length??0,returnByValue=true,awaitPromiseSupplied=false,userGestureSupplied=false});
    }
    internal static void CdpReply(string method,object parameters,JsonElement reply)
    {try{CdpReplyCore(method,parameters,reply);}catch{Record("OBSERVER_CDP_PARSE_UNAVAILABLE");}}
    private static void CdpReplyCore(string method,object parameters,JsonElement reply)
    {
        using var p=JsonDocument.Parse(JsonSerializer.Serialize(parameters));var m=p.RootElement;
        if(method=="Page.createIsolatedWorld")Record("ISOLATED_WORLD",new{worldName=m.GetProperty("worldName").GetString(),contextRef=Alias(reply.GetProperty("executionContextId").GetInt32().ToString()),frameRef=Alias(m.GetProperty("frameId").GetString()!)});
        if(method=="Runtime.evaluate"&&m.TryGetProperty("expression",out var expression)&&expression.GetString()==ObservationScripts.Nodes)
        {
            string id=reply.GetProperty("result").GetProperty("objectId").GetString()!;ObjectWorld[id]=Alias(m.GetProperty("contextId").GetInt32().ToString());
            Record("NODES_ARRAY",new{objectRef=Alias(id),worldRef=ObjectWorld[id],expressionSha256=Digest(ObservationScripts.Nodes),objectGroupPresent=m.TryGetProperty("objectGroup",out _)});
        }
        if(method=="Runtime.getProperties"&&ObjectWorld.TryGetValue(m.GetProperty("objectId").GetString()!,out var world))
            foreach(var row in reply.GetProperty("result").EnumerateArray())
                if(int.TryParse(row.GetProperty("name").GetString(),out _)&&row.TryGetProperty("value",out var v)&&v.TryGetProperty("objectId",out var id))ObjectWorld[id.GetString()!]=world;
    }
}
