using System.Diagnostics;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;

// Isolated diagnostic executable. No Nova references, host IPC, Policy,
// Approval, ToolRuntime, staging, page bridge or model-facing capability.
internal static class Program
{
    private const string ExpectedRuntime="154.0.4258.62",Sdk="1.0.4258.31";
    private const string Host="nova-local.invalid",Origin="https://nova-local.invalid";
    private const string Arguments="--disable-background-networking --disable-component-update --disable-sync --no-first-run";
    private const int WindowMs=25000;
    private static readonly byte[] Payload=Encoding.UTF8.GetBytes("Local approved download cobalt-631.");
    private const string Html="""
<!doctype html><html><head><title>Local transfer specimen</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'">
<style>body{margin:10px}a{display:block;height:28px;margin:6px 0}</style></head><body>
<a id="download" href="/download.txt" download="../../untrusted-name.txt">Approved specimen download</a>
</body></html>
""";
    private static readonly List<object> Events=[];
    private static readonly Stopwatch Clock=Stopwatch.StartNew();
    private static string variant="",stage="BOOT",root="";
    private static bool activated,received,operationCreated,resourceObserved,targetNavigation;
    private static bool cleanupConfirmed;
    private static int activationCount,requestCount;
    private static string? available,effective,reportedError;
    private static double? activationAt;
    private static CoreWebView2? view;
    private static void Record(string kind,object? metadata=null)
    {if(Events.Count>=128)throw new InvalidOperationException("BOUNDED_TRACE_LIMIT");Events.Add(new{sequence=Events.Count+1,milliseconds=Clock.Elapsed.TotalMilliseconds,kind,metadata});}
    private static string Kind(string uri)=>uri==Origin+"/download.txt"?"DOWNLOAD_TARGET":uri==Origin+"/index.html"?"INDEX":"OTHER";
    public static int Main(string[] args)
    {
        if(args.Length!=2||args[0] is not("A" or "B" or "C"))return 2;
        variant=args[0];root=Path.GetFullPath(args[1]);
        if(!Directory.Exists(root)||Directory.EnumerateFileSystemEntries(root).Any())return 3;
        int exit=4;
        var ui=new Thread(()=>
        {
            using var form=new Form{ShowInTaskbar=false,FormBorderStyle=FormBorderStyle.Sizable};
            _=form.Handle; // Same hidden HWND/controller type as the current runtime.
            form.BeginInvoke(async()=>
            {
                try{exit=await Run(form.Handle);}
                catch(Exception e){reportedError=e.GetType().Name;Record("PROBE_ERROR",new{stage,errorType=reportedError,hresult=e.HResult});exit=5;}
                finally{Save();Application.ExitThread();}
            });
            Application.Run();
        }){Name="engine-download-probe-sta",IsBackground=false};
        ui.SetApartmentState(ApartmentState.STA);ui.Start();ui.Join();return exit;
    }
    private static async Task<int> Run(IntPtr hwnd)
    {
        stage="RUNTIME_IDENTITY";
        available=CoreWebView2Environment.GetAvailableBrowserVersionString();
        if(available.Split(' ')[0]!=ExpectedRuntime)throw new InvalidOperationException("RUNTIME_DRIFT");
        if(Payload.Length!=35)throw new InvalidOperationException("PAYLOAD_CONTRACT");
        string udf=Path.Combine(root,"udf"),content=Path.Combine(root,"content");
        Directory.CreateDirectory(content);
        File.WriteAllBytes(Path.Combine(content,"index.html"),Encoding.UTF8.GetBytes(Html));
        File.WriteAllBytes(Path.Combine(content,"download.txt"),Payload);
        var directory=Directory.CreateDirectory(udf);
        var acl=new DirectorySecurity();acl.SetAccessRuleProtection(true,false);
        var sid=WindowsIdentity.GetCurrent().User??throw new InvalidOperationException("OWNER_IDENTITY");
        acl.AddAccessRule(new FileSystemAccessRule(sid,FileSystemRights.FullControl,InheritanceFlags.ContainerInherit|InheritanceFlags.ObjectInherit,PropagationFlags.None,AccessControlType.Allow));directory.SetAccessControl(acl);
        var options=new CoreWebView2EnvironmentOptions(Arguments){ExclusiveUserDataFolderAccess=true};
        CoreWebView2Environment? environment=null;CoreWebView2Controller? controller=null;
        var exited=new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        var begun=new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        try
        {
            stage="ENVIRONMENT";environment=await CoreWebView2Environment.CreateAsync(null,udf,options);
            effective=environment.BrowserVersionString;
            if(effective.Split(' ')[0]!=ExpectedRuntime)throw new InvalidOperationException("RUNTIME_DRIFT");
            environment.BrowserProcessExited+=(_,_)=>exited.TrySetResult(true);
            stage="CONTROLLER";
            var controllerOptions=environment.CreateCoreWebView2ControllerOptions();controllerOptions.IsInPrivateModeEnabled=true;
            controller=await environment.CreateCoreWebView2ControllerAsync(hwnd,controllerOptions);controller.IsVisible=false;view=controller.CoreWebView2;
            var settings=view.Settings;settings.IsWebMessageEnabled=false;settings.AreHostObjectsAllowed=false;settings.AreDevToolsEnabled=false;
            settings.IsPasswordAutosaveEnabled=false;settings.IsGeneralAutofillEnabled=false;settings.AreDefaultScriptDialogsEnabled=false;
            string pending=Path.Combine(root,"private-pending");Directory.CreateDirectory(pending);view.Profile.DefaultDownloadFolderPath=pending;
            Record("IDENTITY",new{sdkPackage=Sdk,runtimeAvailable=available,runtimeEffective=effective,architecture="x64",coreType=typeof(CoreWebView2).FullName,
                controllerType=controller.GetType().FullName,inPrivate=view.Profile.IsInPrivateModeEnabled,additionalBrowserArguments=Arguments,
                webMessage=false,hostObjects=false,devToolsUi=false,controllerVisible=false,
                sdkAssemblySha256=Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(typeof(CoreWebView2).Assembly.Location)))});
            // The identical native event primitive is installed before content.
            // DENY_ALL immediately: probe measures initiation, not file effects.
            view.DownloadStarting+=(_,e)=>
            {
                e.Cancel=true;using var deferral=e.GetDeferral();e.Handled=true;
                received=true;operationCreated=e.DownloadOperation is not null;
                Record("DOWNLOAD_STARTING",new{cancel=true,handled=true,operationCreated,resource=Kind(e.DownloadOperation!.Uri)});
                deferral.Complete();begun.TrySetResult(true);
            };
            Record("DOWNLOAD_HANDLER_SUBSCRIBED_BEFORE_CONTENT");
            view.NavigationStarting+=(_,e)=>
            {string kind=Kind(e.Uri);if(activated&&kind=="DOWNLOAD_TARGET")targetNavigation=true;Record("NAVIGATION_STARTING",new{resource=kind,e.IsUserInitiated});};
            view.SourceChanged+=(_,e)=>Record("SOURCE_CHANGED",new{resource=Kind(view.Source),e.IsNewDocument});
            view.NavigationCompleted+=(_,e)=>Record("NAVIGATION_COMPLETED",new{resource=Kind(view.Source),e.IsSuccess,webError=e.WebErrorStatus.ToString()});
            view.WebResourceResponseReceived+=(_,e)=>
            {if(Kind(e.Request.Uri)=="DOWNLOAD_TARGET"){resourceObserved=true;Record("DOWNLOAD_RESPONSE_RECEIVED",new{status=e.Response.StatusCode});}};
            if(variant is "A" or "B")
            {
                view.AddWebResourceRequestedFilter(Origin+"/*",CoreWebView2WebResourceContext.All);
                view.WebResourceRequested+=(_,e)=>
                {
                    string kind=Kind(e.Request.Uri);bool target=kind=="DOWNLOAD_TARGET",index=kind=="INDEX";
                    if(target){resourceObserved=true;requestCount++;Record("DOWNLOAD_REQUEST_OBSERVED");}
                    byte[] data=target?Payload:index?Encoding.UTF8.GetBytes(Html):[];
                    string mime=target?"text/plain":index?"text/html":"application/octet-stream";
                    string headers="Content-Type: "+mime+"\r\nContent-Length: "+data.Length+"\r\nCache-Control: no-store\r\n";
                    if(target&&variant=="B")headers+="Content-Disposition: attachment; filename=\"download.txt\"\r\n";
                    var stream=new MemoryStream(data,false);
                    e.Response=view.Environment.CreateWebResourceResponse(stream,target||index?200:404,target||index?"OK":"Not Found",headers);
                    if(target)Record("DOWNLOAD_RESPONSE_PROVIDED",new{status=200,contentType="text/plain",contentLength=35,contentDisposition=variant=="B"?"ATTACHMENT":"ABSENT"});
                };
                Record("WEBRESOURCE_REQUESTED_HOST_PROVIDER_INSTALLED");
            }
            else
            {
                view.SetVirtualHostNameToFolderMapping(Host,content,CoreWebView2HostResourceAccessKind.DenyCors);
                Record("ENGINE_RESOLVED_FOLDER_MAPPING_INSTALLED",new{downloadUsesWebResourceRequested=false});
            }
            stage="INITIAL_DOCUMENT";
            var loaded=new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
            EventHandler<CoreWebView2NavigationCompletedEventArgs> done=(_,e)=>loaded.TrySetResult(e.IsSuccess);
            view.NavigationCompleted+=done;
            try{view.Navigate(Origin+"/index.html");if(!await loaded.Task.WaitAsync(TimeSpan.FromSeconds(5)))throw new InvalidOperationException("INDEX_NOT_LOADED");}
            finally{view.NavigationCompleted-=done;}
            stage="SINGLE_ANCHOR_ACTIVATION";
            await Cdp("Page.enable",new{});
            var tree=(await Cdp("Page.getFrameTree",new{})).GetProperty("frameTree").GetProperty("frame");
            var world=await Cdp("Page.createIsolatedWorld",new{frameId=tree.GetProperty("id").GetString(),worldName="nova-wv2-observation-4-leaves",grantUniveralAccess=false});
            var node=await Cdp("Runtime.evaluate",new{expression="document.getElementById('download')",contextId=world.GetProperty("executionContextId").GetInt32(),returnByValue=false});
            string binding=node.GetProperty("result").GetProperty("objectId").GetString()!;
            activated=true;activationCount++;activationAt=Clock.Elapsed.TotalMilliseconds;Record("ANCHOR_ACTIVATION_DISPATCHED",new{method="CDP isolated-world object click",userGestureFlagSupplied=false});
            var called=await Cdp("Runtime.callFunctionOn",new{objectId=binding,functionDeclaration="function(){this.click();return true;}",arguments=Array.Empty<object>(),returnByValue=true});
            if(called.TryGetProperty("exceptionDetails",out _)||!called.GetProperty("result").GetProperty("value").GetBoolean())throw new InvalidOperationException("ACTIVATION_FAILED");
            Record("ANCHOR_ACTIVATION_ACCEPTED");
            stage="OBSERVE_NATIVE_BOUNDARY";
            await Task.WhenAny(begun.Task,Task.Delay(WindowMs));
            Record("OBSERVATION_WINDOW_ENDED",new{downloadStarting=received,operationCreated,windowLimitMilliseconds=WindowMs});
            return 0; // Completed measurement; FAIL/PASS belongs to the event matrix.
        }
        finally
        {
            // Ordinary disposal of this fresh probe only. No post-boundary
            // diagnostics of transfers, staging, IPC, authority or lifecycle.
            controller?.Close();controller=null;
            if(environment is not null&&view is not null)await exited.Task.WaitAsync(TimeSpan.FromSeconds(15));
            string absolute=Path.GetFullPath(udf);
            if(absolute!=Path.Combine(root,"udf")||!absolute.StartsWith(root+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))throw new InvalidOperationException("OWNED_PATH_ONLY");
            if(Directory.Exists(udf))
            {
                DeleteOwnedTree(udf);
            }
            cleanupConfirmed=!Directory.Exists(udf);
        }
    }
    private static async Task<JsonElement> Cdp(string method,object parameters)
    {string value=await view!.CallDevToolsProtocolMethodAsync(method,JsonSerializer.Serialize(parameters));using var d=JsonDocument.Parse(value);return d.RootElement.Clone();}
    private static void DeleteOwnedTree(string directory)
    {
        // Validate each entry before descending; never follow a reparse point.
        if((File.GetAttributes(directory)&FileAttributes.ReparsePoint)!=0)throw new InvalidOperationException("CLEANUP_UNCONFIRMED");
        foreach(string path in Directory.EnumerateFileSystemEntries(directory))
        {
            var attributes=File.GetAttributes(path);
            if((attributes&FileAttributes.ReparsePoint)!=0)throw new InvalidOperationException("CLEANUP_UNCONFIRMED");
            if((attributes&FileAttributes.Directory)!=0)DeleteOwnedTree(path);else File.Delete(path);
        }
        Directory.Delete(directory);
    }
    private static void Save()
    {
        string treatment=received?"download":targetNavigation?"normal navigation":resourceObserved?"resource load":"ignored activation";
        object result=new{schemaVersion=1,variant,hostPid=Environment.ProcessId,sdkPackage=Sdk,runtimeAvailable=available,runtimeEffective=effective,
            runtimeMatchesExpected=effective?.Split(' ')[0]==ExpectedRuntime,activationCount,activationAtMilliseconds=activationAt,
            anchorActivationAccepted=activated,requestObserved=resourceObserved,requestCount,downloadStarting=received,downloadOperation=operationCreated,
            treatment,treatmentScope="Native signals during one bounded observation window; no response-completion inference from a supplied response",
            result=reportedError is not null?"PROBE_ERROR":received&&operationCreated?"PASS":"FAIL",errorType=reportedError,cleanupConfirmed,
            htmlSha256=Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(Html))),payloadLength=Payload.Length,
            payloadSha256=Convert.ToHexStringLower(SHA256.HashData(Payload)),handler="CoreWebView2.DownloadStarting; immediate Cancel=true",postDownloadStartingDiagnosis=false,events=Events};
        using var file=new FileStream(Path.Combine(root,"probe.json"),FileMode.CreateNew,FileAccess.Write,FileShare.Read);
        JsonSerializer.Serialize(file,result,new JsonSerializerOptions{WriteIndented=true});
        Console.WriteLine("Variant="+variant+";downloadStarting="+received+";operationCreated="+operationCreated+";treatment="+treatment+";rawContentRecorded=false");
    }
}
