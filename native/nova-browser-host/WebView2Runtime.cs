using System.Diagnostics;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;

namespace NovaBrowserHost;

internal interface IWebView2Factory
{
    string AvailableVersion();
    Task<CoreWebView2Environment> Environment(string udf, CoreWebView2EnvironmentOptions options);
    Task<CoreWebView2Controller> Controller(CoreWebView2Environment environment, IntPtr hwnd, CoreWebView2ControllerOptions options);
}
internal sealed class InstalledWebView2Factory : IWebView2Factory
{
    public string AvailableVersion() => CoreWebView2Environment.GetAvailableBrowserVersionString();
    public Task<CoreWebView2Environment> Environment(string udf, CoreWebView2EnvironmentOptions options) => CoreWebView2Environment.CreateAsync(null, udf, options);
    public Task<CoreWebView2Controller> Controller(CoreWebView2Environment environment, IntPtr hwnd, CoreWebView2ControllerOptions options) => environment.CreateCoreWebView2ControllerAsync(hwnd, options);
}

/// <summary>Offline lifecycle only. STA/COM are confined to Infrastructure.</summary>
internal sealed partial class WebView2Runtime : IDisposable
{
    public const string SdkVersion = "1.0.4258.31";
    public const string Arguments = "--disable-background-networking --disable-component-update --disable-sync --no-first-run";
    private readonly string udf, instance;
    private readonly IWebView2Factory factory;
    private readonly TaskCompletionSource<Form> ready = new(TaskCreationOptions.RunContinuationsAsynchronously);
    private readonly Thread ui;
    private readonly Dictionary<string, CoreWebView2Controller> pages = [];
    private readonly Dictionary<string, ExternalProtocolGuard> guards = [];
    private readonly Dictionary<string,ObservationRuntime> dom=[];
    private readonly string? localContentRoot;
    private readonly long maxTransferBytes;
    private readonly bool productiveV12;
    private readonly GuardJournal journal;
    private readonly SensitiveValueRegistry secrets=new();
    private readonly Func<CoreWebView2, GuardJournal, string, Action, ExternalProtocolGuard> guardFactory;
    private readonly HashSet<string> retiredPages = [];
    private CoreWebView2Environment? environment;
    private readonly TaskCompletionSource<bool> exited = new(TaskCreationOptions.RunContinuationsAsynchronously);
    private readonly List<Process> observedProcesses = [];
    private bool failed, started, closed;
    private string? target;

    public WebView2Runtime(string directory, string hostInstance, IWebView2Factory? factory = null,
        string? browserSession = null, IGuardAudit? audit = null,
        Func<CoreWebView2, GuardJournal, string, Action, ExternalProtocolGuard>? guardFactory = null,
        string? localContentRoot = null,long maxTransferBytes=0,bool productiveV12=false)
    {
        udf = Path.GetFullPath(directory); instance = hostInstance; this.factory = factory ?? new InstalledWebView2Factory();
        journal = new GuardJournal(browserSession ?? "bws_" + Guid.NewGuid().ToString("N"), instance,
            audit ?? new DurableGuardAudit(udf + ".guard-audit.jsonl"));
        journal.SensitiveSanitize=secrets.AuditSafe;
        this.guardFactory = guardFactory ?? ((v,j,p,f) => new ExternalProtocolGuard(v,j,p,f));
        this.localContentRoot=localContentRoot;
        this.maxTransferBytes=maxTransferBytes;
        this.productiveV12=productiveV12;
        if(maxTransferBytes>0)journal.ContextEpoch=0;
        ui = new Thread(() =>
        {
            try
            {
                var form = new Form { ShowInTaskbar = false, FormBorderStyle = FormBorderStyle.Sizable };
                _ = form.Handle; // Owned hidden HWND; never show a window or load content.
                ready.SetResult(form);
                System.Windows.Forms.Application.Run();
                form.Dispose();
            }
            catch (Exception e) { ready.TrySetException(e); }
        }) { IsBackground = true, Name = "nova-webview2-sta" };
        ui.SetApartmentState(ApartmentState.STA); ui.Start();
    }
    private async Task<T> OnUi<T>(Func<Task<T>> work)
    {
        var form = await ready.Task;
        var done = new TaskCompletionSource<T>(TaskCreationOptions.RunContinuationsAsynchronously);
        form.BeginInvoke(async () =>
        {
            try { done.SetResult(await work()); }
            catch (Exception e) { done.SetException(e); }
        });
        return await done.Task;
    }
    private void Usable()
    {secrets.Require();Protocol.Need(started && !closed && !failed && !takeoverActive,
        takeoverActive ? "TAKEOVER_ACTIVE" :
        journal.Gap ? "GUARD_AUDIT_FAILED" : guardFailed ? "GUARD_UNAVAILABLE" : failed ? "WEBVIEW2_PROCESS_FAILED" : "INVALID_STATE");}
    private bool guardFailed;
    private object Receipt(string kind) => new { kind, hostInstanceRef = instance, contextEpoch = maxTransferBytes>0?browserEpoch:1, state = "READY" };
    internal static void RequireCompatible(string actual, string required)
    {
        if (!Version.TryParse(actual.Split(' ')[0], out var version) || !Version.TryParse(required.Split(' ')[0], out var minimum) || version < minimum)
            throw new IpcFailure("RUNTIME_INCOMPATIBLE");
    }
    public Task<object> CreateSession() => OnUi<object>(async () =>
    {
        Protocol.Need(!started && !closed);
        string available;
        try { available = factory.AvailableVersion(); }
        catch (WebView2RuntimeNotFoundException) { throw new IpcFailure("RUNTIME_ABSENT"); }
        catch (Exception e) when (e is DllNotFoundException or BadImageFormatException) { throw new IpcFailure("RUNTIME_INCOMPATIBLE"); }
        var options = new CoreWebView2EnvironmentOptions(Arguments) { ExclusiveUserDataFolderAccess = true };
        target = options.TargetCompatibleBrowserVersion;
        RequireCompatible(available, target);
        // Trusted bootstrap path, not IPC/model input. Never reuse an existing folder.
        Protocol.Need(!Directory.Exists(udf) && !File.Exists(udf), "OWNERSHIP_MISMATCH");
        var parent = Directory.GetParent(udf)!;
        Protocol.Need(parent.Exists && (parent.Attributes & FileAttributes.ReparsePoint) == 0, "OWNERSHIP_MISMATCH");
        started = true;
        try
        {
            var directory = Directory.CreateDirectory(udf);
            var acl = new DirectorySecurity(); acl.SetAccessRuleProtection(true, false);
            var sid = WindowsIdentity.GetCurrent().User ?? throw new IpcFailure("OWNERSHIP_MISMATCH");
            acl.AddAccessRule(new FileSystemAccessRule(sid, FileSystemRights.FullControl,
                InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit, PropagationFlags.None, AccessControlType.Allow));
            directory.SetAccessControl(acl);
            using (var marker = new FileStream(Path.Combine(udf, ".nova-owner"), FileMode.CreateNew, FileAccess.Write, FileShare.None))
                marker.Write(Encoding.UTF8.GetBytes(instance));
            environment = await factory.Environment(udf, options);
            RequireCompatible(environment.BrowserVersionString, target);
            Protocol.Need(Path.GetFullPath(environment.UserDataFolder) == udf, "OWNERSHIP_MISMATCH");
            environment.BrowserProcessExited += (_, _) => exited.TrySetResult(true);
            return Receipt("session_create");
        }
        catch (WebView2RuntimeNotFoundException) { failed = true; throw new IpcFailure("RUNTIME_ABSENT"); }
        catch (IpcFailure) { failed = true; throw; }
        catch (Exception) { failed = true; throw new IpcFailure("ENVIRONMENT_CREATION_FAILED"); }
    });
    public Task<object> CreatePage(string page) => OnUi<object>(async () =>
    {
        Usable(); Protocol.Need(!pages.ContainsKey(page) && !retiredPages.Contains(page) && pages.Count < 3, "OWNERSHIP_MISMATCH");
        CoreWebView2Controller? controller = null;
        try
        {
            var options = environment!.CreateCoreWebView2ControllerOptions(); options.IsInPrivateModeEnabled = true;
            controller = await factory.Controller(environment, (await ready.Task).Handle, options);
            controller.IsVisible = false;
            // Even an installation failure owns live engine resources. Capture
            // them before the guard can throw so CloseSession waits for exit.
            ObserveProcesses();
            // Controller is still about:blank. No content operation can obtain
            // it before both native subscriptions are installed successfully.
            ExternalProtocolGuard guard;
            try { guard = guardFactory(controller.CoreWebView2, journal, page, InvalidateGuard); }
            catch { InvalidateGuard(); throw new IpcFailure("GUARD_UNAVAILABLE"); }
            guards.Add(page, guard); guard.Require();
            var settings = controller.CoreWebView2.Settings;
            settings.IsWebMessageEnabled = false; settings.AreHostObjectsAllowed = false;
            settings.AreDevToolsEnabled = false; settings.IsPasswordAutosaveEnabled = false; settings.IsGeneralAutofillEnabled = false;
            settings.AreDefaultScriptDialogsEnabled=false;
            Protocol.Need(controller.CoreWebView2.Profile.IsInPrivateModeEnabled, "CONTROL_CREATION_FAILED");
            if(maxTransferBytes>0)
            {
                // A native pre-download default must never point at the
                // user's Downloads directory. This is per ephemeral profile,
                // not an OS/profile policy change or download authorization.
                string pending=Path.Combine(udf,"_nova_transfers","pending");
                Directory.CreateDirectory(pending);
                controller.CoreWebView2.Profile.DefaultDownloadFolderPath=pending;
            }
            controller.CoreWebView2.ProcessFailed += (_, _) => failed = true;
            Protocol.Need(controller.CoreWebView2.Source == "about:blank", "CONTROL_CREATION_FAILED");
            pages.Add(page, controller);
            var observationRuntime=new ObservationRuntime(controller.CoreWebView2,guard,udf,maxTransferBytes,secrets,productiveV12);dom.Add(page,observationRuntime);
            if(maxTransferBytes>0)await observationRuntime.InstallSensitiveTracking();
            if(localContentRoot is not null)observationRuntime.ConfigureLocal(localContentRoot,"nova-local.invalid");
            ObserveProcesses();
            return Receipt("page_create");
        }
        catch (IpcFailure) { controller?.Close(); failed = true; throw; }
        catch (Exception) { controller?.Close(); failed = true; throw new IpcFailure("CONTROL_CREATION_FAILED"); }
    });
    public Task<object> PageMetadata(string page) => OnUi<object>(() =>
    { Usable(); Protocol.Need(pages.ContainsKey(page), "OWNERSHIP_MISMATCH"); guards[page].Require(); return Task.FromResult(Receipt("page_metadata")); });
    private void InvalidateGuard()
    {
        failed = true; guardFailed = true;
        // Close every owned controller before yielding the STA back to page JS.
        foreach (var c in pages.Values) { try { c.Close(); } catch (InvalidOperationException) { } }
    }
    public Task<object> GuardMetadata() => OnUi(() => Task.FromResult(journal.Metadata(started && !closed && !failed && pages.Count > 0 && guards.Values.All(g => g.Installed))));
    private ObservationRuntime Dom(string page)
    { Usable();Protocol.Need(pages.ContainsKey(page),"OWNERSHIP_MISMATCH");guards[page].Require();return dom[page]; }
    public Task<object> Capture(string page,int elements,int text,int field)=>OnUi(()=>Dom(page).Capture(elements,text,field));
    public Task<object> Resolve(string page,string binding)=>OnUi(()=>Dom(page).Resolve(binding));
    public Task<object> Act(string page,string action,string? binding,string payload,Func<Task> started,JsonElement fields,int budgetMs)=>OnUi(()=>Dom(page).Act(action,binding,payload,started,fields,budgetMs));
    public Task<object> NavigateAdmitted(string page,JsonElement fields,Func<Task> started,int budgetMs)=>OnUi(()=>
    {Protocol.Need(fields.GetProperty("browserContextEpoch").GetInt64()==browserEpoch,"STALE_TARGET");return Dom(page).NavigateAdmitted(fields,started,budgetMs);});
    public Task<object> NavigateLocal(string page,string path)=>OnUi<object>(async()=>
    {
        var d=Dom(page);Protocol.Need(d.LocalOrigin is not null,"NOT_SUPPORTED_IN_CURRENT_BLOCK");
        Protocol.Need(path is "index.html" or "other.html" or "frame.html","INVALID_ACTION");
        var v=pages[page].CoreWebView2;var done=new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        EventHandler<CoreWebView2NavigationCompletedEventArgs> finished=(_,e)=>done.TrySetResult(e.IsSuccess);
        v.NavigationCompleted+=finished;
        try{v.Navigate(d.LocalOrigin+"/"+path);Protocol.Need(await done.Task.WaitAsync(TimeSpan.FromSeconds(5)),"LOCAL_NAVIGATION_FAILED");}
        finally{v.NavigationCompleted-=finished;}
        return new{kind="navigate_local",localOnly=true};
    });
    private void ObserveProcesses()
    {
        foreach (var info in environment!.GetProcessInfos())
        {
            if (observedProcesses.All(p => p.Id != info.ProcessId))
            {
                try { observedProcesses.Add(Process.GetProcessById(info.ProcessId)); }
                catch (ArgumentException) { } // Already exited; cannot become a live resource.
            }
        }
    }
    private static string Hash(string text) => Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(text)));
    public Task<object> Metadata() => OnUi<object>(() =>
    {
        Usable(); Protocol.Need(pages.Count > 0); ObserveProcesses();
        var view = pages.Values.First().CoreWebView2;
        var processInfos = environment!.GetProcessInfos().Select(p =>
        {
            using var process = Process.GetProcessById(p.ProcessId);
            string image = process.MainModule?.FileName ?? throw new IpcFailure("INVALID_STATE");
            return new { pid = p.ProcessId, kind = p.Kind.ToString(), imageIdentity = Hash(image + "|" + FileVersionInfo.GetVersionInfo(image).FileVersion) };
        }).ToArray();
        object value = new { kind = "runtime_metadata", engine = "WINDOWS_WEBVIEW2", sdkVersion = SdkVersion,
            runtimeVersion = environment.BrowserVersionString, architecture = System.Runtime.InteropServices.RuntimeInformation.ProcessArchitecture.ToString(),
            platform = "win32", hostInstanceRef = instance, contextEpoch = maxTransferBytes>0?browserEpoch:1, udfIdentity = Hash(udf), processes = processInfos,
            configuration = new { additionalBrowserArguments = Arguments, exclusiveUserDataFolderAccess = true,
                // Every owned controller was verified about:blank before any
                // content. This is INITIAL configuration, not its current URL
                // (which belongs only in the bounded observation contract).
                targetCompatibleBrowserVersion = target, initialContent = "about:blank", webMessageEnabled = view.Settings.IsWebMessageEnabled,
                hostObjectsAllowed = view.Settings.AreHostObjectsAllowed, devToolsEnabled = view.Settings.AreDevToolsEnabled,
                inPrivate = view.Profile.IsInPrivateModeEnabled },
            requiredApiMetadata = new { environment = true, controller = true, processInfos = true, browserProcessExited = true,
                launchingExternalUriSchemeSdk = typeof(CoreWebView2).GetEvent("LaunchingExternalUriScheme") is not null,
                externalProtocolGuardCertified = false } };
        return Task.FromResult(value);
    });
    public Task<object> ClosePage(string page) => OnUi<object>(() =>
    {
        Protocol.Need(started && !closed); Protocol.Need(pages.Remove(page, out var controller), "OWNERSHIP_MISMATCH");
        controller!.Close(); retiredPages.Add(page);
        // Remove only after closing. Other owned pages remain guarded.
        guards.Remove(page, out var guard); guard?.RetireAfterControlClosed();
        dom.Remove(page);
        return Task.FromResult<object>(new { kind = "page_close", closed = true, cleanupConfirmed = false });
    });
    public async Task<object> CloseSession(int budget)
    {
        await OnUi(() =>
        {
            if (environment is not null) ObserveProcesses();
            foreach (var controller in pages.Values) controller.Close();
            foreach(var d in dom.Values)d.StopTransfers();
            secrets.Dispose();dom.Clear();
            foreach (var guard in guards.Values) guard.RetireAfterControlClosed(); guards.Clear();
            pages.Clear(); closed = true;
            return Task.FromResult(true);
        });
        // No controller ever created means there is no WebView2 browser process.
        if (observedProcesses.Count > 0)
        {
            await exited.Task.WaitAsync(TimeSpan.FromMilliseconds(budget));
            await Task.WhenAll(observedProcesses.Select(p => p.WaitForExitAsync())).WaitAsync(TimeSpan.FromMilliseconds(budget));
        }
        if (Directory.Exists(udf))
        {
            try { DeleteTree(udf); }
            catch (Exception e) when (e is IOException or UnauthorizedAccessException) { throw new IpcFailure("CLEANUP_UNCONFIRMED"); }
        }
        Protocol.Need(!Directory.Exists(udf), "CLEANUP_UNCONFIRMED");
        return new { kind = "session_close", closed = true, cleanupConfirmed = true };
    }
    private static void DeleteTree(string root)
    {
        // Refuse links; never follow a reparse point into an unrelated profile.
        foreach (var path in Directory.EnumerateFileSystemEntries(root).OrderBy(p => Path.GetFileName(p) == ".nova-owner" ? 1 : 0))
        {
            try
            {
                var attributes = File.GetAttributes(path);
                Protocol.Need((attributes & FileAttributes.ReparsePoint) == 0, "CLEANUP_UNCONFIRMED");
                if ((attributes & FileAttributes.Directory) != 0) DeleteTree(path); else File.Delete(path);
            }
            catch (FileNotFoundException) { } // Delete-on-close entry already gone after process exit.
        }
        Directory.Delete(root);
    }
    public void Dispose()
    {
        if (ready.Task.IsCompletedSuccessfully)
            ready.Task.Result.BeginInvoke(() => { foreach (var c in pages.Values) c.Close(); foreach (var g in guards.Values) g.RetireAfterControlClosed(); System.Windows.Forms.Application.ExitThread(); });
        ui.Join(2000);
        foreach (var p in observedProcesses) p.Dispose();
        journal.Dispose();
        secrets.Dispose();
    }
}
