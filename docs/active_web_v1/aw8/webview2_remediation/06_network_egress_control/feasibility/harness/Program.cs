using System.Collections.Concurrent;
using System.Diagnostics;
using System.Net;
using System.Net.Quic;
using System.Net.Security;
using System.Net.Sockets;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Security.Principal;
using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Server.Kestrel.Core;
using Microsoft.Extensions.Logging;
using Microsoft.Web.WebView2.Core;
using NovaBrowserHost;

// Standalone feasibility only. No product host/IPC/tools or Application authority.
internal static class Probe
{
    internal const string Runtime="154.0.4258.62",Sdk="1.0.4258.31";
    internal const string A="a.nova-fixture.test",B="b.nova-fixture.test",C="c.nova-fixture.test";
    static readonly Stopwatch Clock=Stopwatch.StartNew();
    static readonly List<object> Trace=[];
    static readonly Dictionary<string,object?> Results=[];
    static string root="",mode="";
    static CoreWebView2? view;
    static bool admission,suppressWorker,invalidated;
    static readonly HashSet<int> EnginePids=[];
    static int blockedWorker,allowedProxyAuth,deniedSiteAuth,pinnedTls,deniedTls;
    static string phase="BOOT";
    static void Record(string kind,object? data=null)
    {if(Trace.Count>=2048)throw new InvalidOperationException("TRACE_LIMIT");Trace.Add(new{seq=Trace.Count+1,ms=Clock.Elapsed.TotalMilliseconds,phase,kind,data});}
    static string Label(string uri)
    {if(!Uri.TryCreate(uri,UriKind.Absolute,out var u))return "UNPARSEABLE";return u.Host switch {A=>"A",B=>"B",C=>"C","127.0.0.1"=>"LOOPBACK4","[::1]" or "::1"=>"LOOPBACK6",_=>"OTHER"}+":"+u.AbsolutePath;}
    internal static void NativeRecord(string kind,object data)=>Record(kind,data);
    public static int Main(string[] args)
    {
        if(args.Length!=2||args[0] is not ("candidate" or "worker-control" or "broker-absent" or "secure-suppression"))return 2;
        mode=args[0];root=Path.GetFullPath(args[1]);
        if(!Directory.Exists(root)||Directory.EnumerateFileSystemEntries(root).Any())return 3;
        Private(root);int exit=0;
        var thread=new Thread(()=>
        {
            using var form=new Form{ShowInTaskbar=false};_=form.Handle;
            form.BeginInvoke(async()=>
            {
                try{await Run(form.Handle);}
                catch(Exception e){Record("PROBE_FAILURE",new{type=e.GetType().Name,code=e is InvalidOperationException?e.Message:"TYPED_EXCEPTION",hresult=e.HResult});Results["probeError"]=e.GetType().Name;exit=4;}
                finally
                {
                    using var file=new FileStream(Path.Combine(root,"native.json"),FileMode.CreateNew,FileAccess.Write,FileShare.Read);
                    JsonSerializer.Serialize(file,new{schemaVersion=1,mode,hostPid=Environment.ProcessId,startedUtc=DateTimeOffset.UtcNow.AddMilliseconds(-Clock.Elapsed.TotalMilliseconds),endedUtc=DateTimeOffset.UtcNow,results=Results,trace=Trace},new JsonSerializerOptions{WriteIndented=true});
                    System.Windows.Forms.Application.ExitThread();
                }
            });System.Windows.Forms.Application.Run();
        });thread.SetApartmentState(ApartmentState.STA);thread.Start();thread.Join();return exit;
    }
    static void Private(string path)
    {
        if((File.GetAttributes(path)&FileAttributes.ReparsePoint)!=0)throw new InvalidOperationException("REPARSE_REJECTED");
        var acl=new DirectorySecurity();acl.SetAccessRuleProtection(true,false);
        var sid=WindowsIdentity.GetCurrent().User??throw new InvalidOperationException("OWNER_UNKNOWN");
        acl.AddAccessRule(new FileSystemAccessRule(sid,FileSystemRights.FullControl,InheritanceFlags.ContainerInherit|InheritanceFlags.ObjectInherit,PropagationFlags.None,AccessControlType.Allow));
        new DirectoryInfo(path).SetAccessControl(acl);
    }
    static bool NoOverrides()
    {
        int env=Environment.GetEnvironmentVariables().Keys.Cast<string>().Count(k=>k.StartsWith("WEBVIEW2_",StringComparison.OrdinalIgnoreCase));
        int registry=0;
        foreach(var hive in new[]{Microsoft.Win32.RegistryHive.CurrentUser,Microsoft.Win32.RegistryHive.LocalMachine})
        foreach(var rv in new[]{Microsoft.Win32.RegistryView.Registry64,Microsoft.Win32.RegistryView.Registry32})
        {
            using var key=Microsoft.Win32.RegistryKey.OpenBaseKey(hive,rv).OpenSubKey(@"SOFTWARE\Policies\Microsoft\Edge\WebView2",false);
            if(key is not null)registry+=key.GetSubKeyNames().Length+key.GetValueNames().Length;
        }
        Record("OVERRIDE_PREFLIGHT",new{webviewEnvironmentKeys=env,policyOverrideEntries=registry,registryReadOnly=true});return env==0&&registry==0;
    }
    static async Task Run(IntPtr hwnd)
    {
        if(!NoOverrides())throw new InvalidOperationException("OVERRIDES_UNCONFIRMED");
        string available=CoreWebView2Environment.GetAvailableBrowserVersionString();
        if(available.Split(' ')[0]!=Runtime)throw new InvalidOperationException("RUNTIME_DRIFT");
        await using var fixture=new Fixtures();await fixture.Start();
        using var broker=new HarnessBroker(fixture);
        if(mode!="broker-absent")broker.Start();
        using var canary4=new TcpCanary(IPAddress.Loopback);
        using var canary6=new TcpCanary(IPAddress.IPv6Loopback);
        using var stun=new UdpCanary();using var dns=new UdpCanary();
        await canary4.Calibrate();await canary6.Calibrate();await stun.Calibrate();await dns.Calibrate();
        Results["canaryCalibration"]=new{tcp4=canary4.Calibrated,tcp6=canary6.Calibrated,stun=stun.Calibrated,dns=dns.Calibrated};
        // Known candidate switches only. No fictional disable-webrtc flag.
        string netlog=Path.Combine(root,"network-private.tmp");
        string requested="--disable-background-networking --disable-component-update --disable-sync --no-first-run "+
            "--proxy-server=http://127.0.0.1:"+broker.Port+" --proxy-bypass-list=<-loopback> "+
            "--host-resolver-rules=\"MAP * ~NOTFOUND, EXCLUDE 127.0.0.1\" --disable-quic "+
            "--force-webrtc-ip-handling-policy=disable_non_proxied_udp --enable-automation "+
            "--log-net-log="+netlog+" --net-log-capture-mode=Default";
        string udf=Path.Combine(root,"udf");Directory.CreateDirectory(udf);Private(udf);
        var options=new CoreWebView2EnvironmentOptions(requested){ExclusiveUserDataFolderAccess=true};
        CoreWebView2Environment? environment=null;CoreWebView2Controller? controller=null;ExternalProtocolGuard? guard=null;
        using var journal=new GuardJournal("bws_"+Guid.NewGuid().ToString("N"),"bhi_"+Guid.NewGuid().ToString("N"),new DurableGuardAudit(Path.Combine(root,"guard.jsonl")));
        var exited=new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        try
        {
            environment=await CoreWebView2Environment.CreateAsync(null,udf,options);
            if(environment.BrowserVersionString.Split(' ')[0]!=Runtime||Path.GetFullPath(environment.UserDataFolder)!=udf)throw new InvalidOperationException("EFFECTIVE_IDENTITY_MISMATCH");
            environment.BrowserProcessExited+=(_,_)=>exited.TrySetResult(true);
            var co=environment.CreateCoreWebView2ControllerOptions();co.IsInPrivateModeEnabled=true;
            controller=await environment.CreateCoreWebView2ControllerAsync(hwnd,co);controller.IsVisible=false;view=controller.CoreWebView2;
            guard=new ExternalProtocolGuard(view,journal,"bwp_"+Guid.NewGuid().ToString("N"),()=>invalidated=true);guard.Require();
            var s=view.Settings;s.IsWebMessageEnabled=false;s.AreHostObjectsAllowed=false;s.AreDevToolsEnabled=false;s.IsPasswordAutosaveEnabled=false;s.IsGeneralAutofillEnabled=false;s.AreDefaultScriptDialogsEnabled=false;
            view.DownloadStarting+=(_,e)=>{e.Cancel=true;e.Handled=true;Record("DOWNLOAD_DENIED");};
            view.ServerCertificateErrorDetected+=(_,e)=>
            {
                e.Action=CoreWebView2ServerCertificateErrorAction.Cancel;
                using var cert=e.ServerCertificate.ToX509Certificate2();
                bool exact=Uri.TryCreate(e.RequestUri,UriKind.Absolute,out var u)&&u.Scheme=="https"&&u.Port==443&&u.Host is A or B or C&&cert.RawData.AsSpan().SequenceEqual(fixture.Certificate.RawData)&&e.ErrorStatus==CoreWebView2WebErrorStatus.CertificateIsInvalid;
                if(exact){e.Action=CoreWebView2ServerCertificateErrorAction.AlwaysAllow;pinnedTls++;}else deniedTls++;
                Record("TLS_FIXTURE_PIN",new{exactFixturePin=exact,globalTrustChanged=false,status=e.ErrorStatus.ToString(),decision=exact?"ALLOW_EXACT_TEST_FIXTURE":"DENY"});
            };
            view.BasicAuthenticationRequested+=(_,e)=>
            {
                e.Cancel=true;
                bool owned=Uri.TryCreate(e.Uri,UriKind.Absolute,out var u)&&u.Scheme=="http"&&u.Host=="127.0.0.1"&&u.Port==broker.Port&&e.Challenge==broker.Challenge;
                if(owned){e.Response.UserName=broker.User;e.Response.Password=broker.Password;e.Cancel=false;allowedProxyAuth++;}else deniedSiteAuth++;
                Record("AUTH_CHALLENGE",new{exactOwnedProxy=owned,credentialProvided=owned,credentialRecorded=false});
            };
            view.NavigationStarting+=(_,e)=>{if(admission&&!Allowed(e.Uri))e.Cancel=true;Record("NAVIGATION",new{urlLabel=Label(e.Uri),e.Cancel,e.IsRedirected});};
            view.FrameCreated+=(_,e)=>e.Frame.NavigationStarting+=(_,f)=>{if(admission&&!Allowed(f.Uri))f.Cancel=true;Record("FRAME_NAVIGATION",new{urlLabel=Label(f.Uri),f.Cancel});};
            view.AddWebResourceRequestedFilter("*",CoreWebView2WebResourceContext.All,CoreWebView2WebResourceRequestSourceKinds.All);
            view.WebResourceRequested+=(_,e)=>
            {
                bool sw=e.Request.Headers.Contains("Service-Worker")||e.RequestedSourceKind==CoreWebView2WebResourceRequestSourceKinds.ServiceWorker;
                bool deny=suppressWorker&&sw||admission&&!Allowed(e.Request.Uri);
                if(deny){e.Response=view.Environment.CreateWebResourceResponse(new MemoryStream([],false),403,"Denied","Content-Length: 0\r\n");if(sw)blockedWorker++;}
                Record("URL_ADMISSION",new{urlLabel=Label(e.Request.Uri),context=e.ResourceContext.ToString(),source=e.RequestedSourceKind.ToString(),workerScriptOrSource=sw,denied=deny});
            };
            view.NavigationCompleted+=(_,e)=>Record("NAVIGATION_COMPLETED",new{e.IsSuccess,status=e.WebErrorStatus.ToString()});
            view.ProcessFailed+=(_,e)=>{invalidated=true;Record("PROCESS_FAILED",new{kind=e.ProcessFailedKind.ToString()});};
            await Cdp("Page.enable",new{});
            var command=await Cdp("Browser.getBrowserCommandLine",new{});
            var effective=command.GetProperty("arguments").EnumerateArray().Select(a=>a.GetString()!).ToArray();
            var securityArgs=new[]{"--proxy-server=http://127.0.0.1:"+broker.Port,"--proxy-bypass-list=<-loopback>","--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1","--disable-quic","--force-webrtc-ip-handling-policy=disable_non_proxied_udp"};
            bool exactArgs=securityArgs.All(a=>effective.Count(x=>x.Split('=')[0]==a.Split('=')[0])==1&&effective.Contains(a))&&!effective.Any(a=>a.StartsWith("--proxy-pac-url")||a=="--no-proxy-server");
            using var browser=Process.GetProcessById((int)view.BrowserProcessId);
            string exe=browser.MainModule!.FileName;
            Record("IDENTITY_BEFORE_CONTENT",new{sdk=Sdk,runtime=environment.BrowserVersionString,architecture="X64",runtimeBinarySha256=Hash(File.ReadAllBytes(exe)),sdkAssemblySha256=Hash(File.ReadAllBytes(typeof(CoreWebView2).Assembly.Location)),requestedArgumentsSha256=Hash(Encoding.UTF8.GetBytes(requested)),securityArgumentsEffective=exactArgs,browserPid=view.BrowserProcessId,udfLength=udf.Length,inPrivate=view.Profile.IsInPrivateModeEnabled,guardInstalled=guard.Installed,contentStillBlank=view.Source=="about:blank"});
            Results["identityAttestedBeforeControlledContent"]=exactArgs;
            if(!exactArgs)throw new InvalidOperationException("ENGINE_ARGUMENTS_AMBIGUOUS");
            // Flags/readback are identity evidence only; probes below establish behavior.
            foreach(var p in environment.GetProcessInfos()){EnginePids.Add(p.ProcessId);Record("OWNED_PROCESS",new{pid=p.ProcessId,kind=p.Kind.ToString()});}
            if(mode=="broker-absent")
            {
                phase="BROKER_ABSENT_STARTUP";
                Results["startupHttp"]=await Navigate("http://"+A+"/index");
                Results["startupHttps"]=await Navigate("https://"+A+"/index");
                Results["startupLoopback4"]=await Navigate("http://127.0.0.1:"+canary4.Port+"/forbidden");
                Results["startupLoopback6"]=await Navigate("http://[::1]:"+canary6.Port+"/forbidden");
            }
            else
            {
                if(mode!="secure-suppression"){phase="HTTP_PROXY";Results["httpAllowed"]=await Navigate("http://"+A+"/index");}
                if(mode=="candidate")
                {
                    phase="PROXY_NEGATIVES_NO_LOGICAL_DENIAL";
                    Results["loopback4"]=await Navigate("http://127.0.0.1:"+canary4.Port+"/forbidden");
                    Results["loopback6"]=await Navigate("http://[::1]:"+canary6.Port+"/forbidden");
                    Results["private"]=await Navigate("http://10.23.45.67/forbidden");
                    Results["linkLocal"]=await Navigate("http://169.254.169.254/forbidden");
                }
                phase="HTTPS_PINNED_FIXTURE";admission=true;
                if(mode!="secure-suppression"){Results["httpsAllowed"]=await Navigate("https://"+A+"/index");Results["secureContext"]=await Eval("({secure:isSecureContext,origin:location.origin==='https://a.nova-fixture.test'})");}
                suppressWorker=mode is "candidate" or "secure-suppression";phase=suppressWorker?"SW_SUPPRESSION":"SW_POSITIVE_CONTROL";
                // Service-worker execution is evaluated in a native mapped secure
                // context, not one with a TLS error exception. Separate from the
                // CONNECT/TLS evidence above; mapping is not network enforcement.
                string swRoot=Path.Combine(root,"sw-fixture");Directory.CreateDirectory(swRoot);Private(swRoot);
                File.WriteAllText(Path.Combine(swRoot,"index.html"),"<!doctype html><title>Controlled worker context</title>");
                File.WriteAllText(Path.Combine(swRoot,"sw.js"),Scripts.Sw);
                File.WriteAllText(Path.Combine(swRoot,"sw-import.js"),"self.importWasExecuted=true;");
                foreach(var name in new[]{"worker-executed","worker-fetch","cached"})File.WriteAllText(Path.Combine(swRoot,name),"controlled response");
                view.SetVirtualHostNameToFolderMapping(A,swRoot,CoreWebView2HostResourceAccessKind.DenyCors);
                Results["workerSecureDocument"]=await Navigate("https://"+A+"/index.html");
                Results["workerAttempt"]=await Eval(Scripts.Worker);
                Results["workerNetworkBeforeReload"]=fixture.Snapshot();
                Results["workerReload"]=await Navigate("https://"+A+"/index.html");
                Results["workerAfterReload"]=await Eval(Scripts.WorkerAfterReload);
                Results["nativeWorkerRegistrations"]=(await view.Profile.ServiceWorkerManager.GetServiceWorkerRegistrationsAsync()).Count;
                if(mode!="secure-suppression"){view.ClearVirtualHostNameToFolderMapping(A);Results["afterWorkerPhysicalDocument"]=await Navigate("https://"+A+"/index");}
                if(mode=="secure-suppression")
                {
                    phase="RTC_SECURE_CONTEXT";
                    Results["webRtc"]=await Eval(Scripts.Rtc(stun.Port));
                    Results["secureContext"]=await Eval("({secure:isSecureContext,origin:location.origin==='https://a.nova-fixture.test'})");
                }
                if(mode=="candidate")
                {
                    phase="RTC_SECURE_CONTEXT";
                    Results["webRtc"]=await Eval(Scripts.Rtc(stun.Port));
                    phase="LOGICAL_ADMISSION";
                    Results["logicalResources"]=await Eval(Scripts.Logical);
                    Results["logicalRedirect"]=await Navigate("https://"+A+"/redirect");
                    Results["afterRedirectCounters"]=fixture.Snapshot();
                    Results["backToA"]=await Navigate("https://"+A+"/index");
                    Results["secondOrigin"]=await Eval(Scripts.SecondOrigin);
                    phase="DESTINATION_AUTH_TRAP";
                    Results["siteAuthTrap"]=await Navigate("https://"+A+"/auth-trap");
                    phase="TLS_NEGATIVE";
                    Results["wrongCertificate"]=await Navigate("https://bad.nova-fixture.test/index");
                    phase="H3_ALTSVC";Results["altSvc"]=await Navigate("https://"+A+"/alt-svc");
                    Results["quicListenerSupported"]=QuicListener.IsSupported;
                    Results["h3Requests"]=await Eval(Scripts.RepeatedFetch);
                    phase="BROKER_DEAD";broker.Stop();
                    Results["deadHttp"]=await Navigate("http://"+A+"/index?dead=1");
                    Results["deadHttps"]=await Navigate("https://"+A+"/index?dead=1");
                    Results["deadLoopback4"]=await Navigate("http://127.0.0.1:"+canary4.Port+"/forbidden");
                }
            }
            Results["canaryUnexpected"]=new{tcp4=canary4.Unexpected,tcp6=canary6.Unexpected,stun=stun.Unexpected,dns=dns.Unexpected,dnsCanaryNotSystemResolver=true};
            Results["stunCanaryPackets"]=stun.Packets.ToArray();
            Results["proxy"]=broker.Snapshot();Results["fixture"]=fixture.Snapshot();
            Results["nativeAuth"]=new{allowedProxyAuth,deniedSiteAuth,credentialsSentToSite=fixture.CredentialAtSite};
            Results["tls"]=new{pinnedTls,deniedTls,testOnlyExactPin=true,globalCertificateBypass=false,caStoreChanged=false};
            Results["workerBlocks"]=blockedWorker;Results["guardStillInstalled"]=guard.Installed&&!invalidated;
            foreach(var p in environment.GetProcessInfos()){EnginePids.Add(p.ProcessId);Record("OWNED_PROCESS_FINAL",new{pid=p.ProcessId,kind=p.Kind.ToString()});}
        }
        finally
        {
            phase="CLEANUP";
            if(view is not null){try{await view.ClearServerCertificateErrorActionsAsync();Record("TLS_TEST_PIN_CACHE_CLEARED");}catch(Exception e){Record("TLS_CLEAR_FAILURE",new{type=e.GetType().Name});}}
            controller?.Close();guard?.RetireAfterControlClosed();
            bool stopped=environment is null;
            if(environment is not null){try{await exited.Task.WaitAsync(TimeSpan.FromSeconds(15));stopped=true;}catch(TimeoutException){Record("ENGINE_EXIT_UNCONFIRMED");}}
            Results["engineExitConfirmed"]=stopped;
            if(stopped)
            {
                foreach(var pid in EnginePids){bool gone;try{using var p=Process.GetProcessById(pid);gone=p.HasExited;}catch(ArgumentException){gone=true;}Record("OWNED_PROCESS_EXIT",new{pid,gone});}
                if(Directory.Exists(udf)){DeleteOwned(udf,root);Results["udfDeleted"]=!Directory.Exists(udf);}
                if(File.Exists(netlog))
                {
                    string raw=File.ReadAllText(netlog);
                    bool credentialAbsent=!raw.Contains(broker.User,StringComparison.Ordinal)&&!raw.Contains(broker.Password,StringComparison.Ordinal);
                    Results["privateNetlogCredentialAbsent"]=credentialAbsent;
                    Results["networkTrace"]=SummarizeNetlog(raw,broker.Port,canary4.Port,canary6.Port);
                    File.Delete(netlog);Results["rawNetlogDeleted"]=true;
                }
            }
        }
    }
    static bool Allowed(string uri)=>Uri.TryCreate(uri,UriKind.Absolute,out var u)&&u.Scheme is "http" or "https"&&(u.Host is A or B || phase=="TLS_NEGATIVE"&&u.Host=="bad.nova-fixture.test");
    static async Task<object> Navigate(string url)
    {
        if(view is null)throw new InvalidOperationException("NO_CONTROL");
        var done=new TaskCompletionSource<object>(TaskCreationOptions.RunContinuationsAsynchronously);
        EventHandler<CoreWebView2NavigationCompletedEventArgs> handler=(_,e)=>
        {if(e.IsSuccess||e.WebErrorStatus!=CoreWebView2WebErrorStatus.CertificateIsInvalid)done.TrySetResult(new{success=e.IsSuccess,status=e.WebErrorStatus.ToString()});};
        view.NavigationCompleted+=handler;
        try{view.Navigate(url);return await done.Task.WaitAsync(TimeSpan.FromSeconds(6));}
        catch(TimeoutException){return new{success=false,status="PROBE_NAVIGATION_TIMEOUT"};}
        finally{view.NavigationCompleted-=handler;}
    }
    static async Task<JsonElement> Eval(string expression)
    {
        var result=await Cdp("Runtime.evaluate",new{expression,awaitPromise=true,returnByValue=true});
        if(result.TryGetProperty("exceptionDetails",out _))return JsonSerializer.SerializeToElement(new{scriptException=true});
        return result.GetProperty("result").TryGetProperty("value",out var value)?value.Clone():JsonSerializer.SerializeToElement(new{noValue=true});
    }
    static async Task<JsonElement> Cdp(string method,object parameters)
    {string value=await view!.CallDevToolsProtocolMethodAsync(method,JsonSerializer.Serialize(parameters)).WaitAsync(TimeSpan.FromSeconds(12));using var j=JsonDocument.Parse(value);return j.RootElement.Clone();}
    internal static string Hash(byte[] data)=>Convert.ToHexStringLower(SHA256.HashData(data));
    static object SummarizeNetlog(string raw,int proxyPort,int p4,int p6)
    {
        using var doc=JsonDocument.Parse(raw);var names=new Dictionary<int,string>();
        foreach(var e in doc.RootElement.GetProperty("constants").GetProperty("logEventTypes").EnumerateObject())names[e.Value.GetInt32()]=e.Name;
        var counts=new Dictionary<string,int>();var connects=new List<object>();
        foreach(var e in doc.RootElement.GetProperty("events").EnumerateArray())
        {
            string name=names.GetValueOrDefault(e.GetProperty("type").GetInt32(),"UNKNOWN");
            if(name.Contains("DNS")||name.Contains("HOST_RESOLVER")||name.Contains("TCP_CONNECT")||name.Contains("UDP_CONNECT")||name.Contains("QUIC")||name.Contains("HTTP2_SESSION"))counts[name]=counts.GetValueOrDefault(name)+1;
            if((name.Contains("TCP_CONNECT")||name=="UDP_CONNECT"||name=="UDP_BYTES_SENT"||name=="HOST_RESOLVER_MANAGER_REQUEST")&&e.TryGetProperty("params",out var p))
            {
                var addresses=new List<string>();
                if(p.TryGetProperty("address_list",out var list))foreach(var a in list.EnumerateArray())if(a.ValueKind==JsonValueKind.String)addresses.Add(a.GetString()!);
                foreach(var key in new[]{"address","remote_address","host"})if(p.TryGetProperty(key,out var a)&&a.ValueKind==JsonValueKind.String)addresses.Add(a.GetString()!);
                connects.Add(new{eventKind=name,parameterKeys=p.EnumerateObject().Select(x=>x.Name).ToArray(),endpointRoles=addresses.Select(addr=>addr.EndsWith(":"+proxyPort)?"OWNED_PROXY":addr.EndsWith(":"+p4)||addr.EndsWith(":"+p6)?"FORBIDDEN_CANARY":addr.Contains(A)||addr.Contains(B)||addr.Contains(C)?"FIXTURE_HOST":addr.Contains("127.0.0.1")?"LOOPBACK":"OTHER").ToArray(),sourceId=e.GetProperty("source").GetProperty("id").GetInt32(),error=p.TryGetProperty("net_error",out var error)?error.GetInt32():(int?)null});
            }
        }
        return new{nativeLogEvents=counts,tcpConnects=connects,scope="Chromium native network-service log, not universal OS packet capture",eventCount=doc.RootElement.GetProperty("events").GetArrayLength()};
    }
    static void DeleteOwned(string path,string ownerRoot)
    {
        string absolute=Path.GetFullPath(path);
        if(!absolute.StartsWith(Path.GetFullPath(ownerRoot)+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase)||(File.GetAttributes(path)&FileAttributes.ReparsePoint)!=0)throw new InvalidOperationException("OWNED_CLEANUP_ONLY");
        foreach(var p in Directory.EnumerateFileSystemEntries(path)){if((File.GetAttributes(p)&FileAttributes.ReparsePoint)!=0)throw new InvalidOperationException("CLEANUP_UNCONFIRMED");if(Directory.Exists(p))DeleteOwned(p,ownerRoot);else File.Delete(p);}Directory.Delete(path);
    }
}

// Compile the accepted guard byte-for-byte; only its exception/check helper is
// supplied by this standalone executable. No production bootstrap/IPC is added.
namespace NovaBrowserHost
{
    internal sealed class IpcFailure(string code):Exception(code);
    internal static class Protocol{internal static void Need(bool valid,string code="INVALID_STATE"){if(!valid)throw new IpcFailure(code);}}
}
