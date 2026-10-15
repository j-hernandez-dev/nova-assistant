using System.Diagnostics;
using System.Globalization;
using Microsoft.Web.WebView2.Core;

namespace NovaWebViewHost;

internal sealed class WindowsWebViewHost
{
    private readonly HostOptions options;
    private readonly Action<string> stop;
    private readonly Thread ui;
    private readonly TaskCompletionSource<Form> window = new(TaskCreationOptions.RunContinuationsAsynchronously);
    private CoreWebView2Environment? environment;
    private CoreWebView2Controller? controller;
    private Process? browser;
    private Task<object>? startup;
    private bool closing;
    private DownloadTicket? download;
    private System.Windows.Forms.Timer? downloadTimer;
    private sealed class DownloadTicket(string operation, string url, string path, long maxBytes, DateTime deadline)
    {
        internal readonly string Operation = operation, Url = url, Path = path;
        internal readonly long MaxBytes = maxBytes;
        internal readonly DateTime Deadline = deadline;
        internal CoreWebView2DownloadOperation? Engine;
        internal string State = "ARMED";
    }
    internal int BrowserPid { get; private set; }

    internal WindowsWebViewHost(HostOptions options, Action<string> stop)
    {
        this.options = options;
        this.stop = stop;
        ui = new Thread(() =>
        {
            try
            {
                // Changing ShowInTaskbar after controller creation recreates the
                // HWND and disposes WebView2. A hidden form has no taskbar item.
                using var form = new Form { ShowInTaskbar = true, ClientSize = new Size(1280, 800) };
                _ = form.Handle;
                form.FormClosing += (_, e) => { if (!closing) { e.Cancel = true; form.Hide(); } };
                window.TrySetResult(form);
                Application.Run();
            }
            catch (Exception e) { window.TrySetException(e); stop("process-failed"); }
        }) { Name = "nova-webview2-sta", IsBackground = true };
        ui.SetApartmentState(ApartmentState.STA);
        ui.Start();
    }

    internal Task<object> StartAsync(CancellationToken cancellation) => startup = OnUiAsync<object>(async () =>
    {
        cancellation.ThrowIfCancellationRequested();
        string available = CoreWebView2Environment.GetAvailableBrowserVersionString(options.RuntimeDirectory);
        if (string.IsNullOrWhiteSpace(available)) throw new InvalidOperationException("Bundled runtime has no version.");
        if (Directory.Exists(options.ProfileDirectory) || File.Exists(options.ProfileDirectory))
            throw new InvalidOperationException("The new profile path was created before startup.");
        Directory.CreateDirectory(options.ProfileDirectory);
        var configuration = new CoreWebView2EnvironmentOptions(
            "--remote-debugging-port=0 --remote-debugging-address=127.0.0.1")
        {
            ExclusiveUserDataFolderAccess = true
        };
        environment = await CoreWebView2Environment.CreateAsync(
            options.RuntimeDirectory, options.ProfileDirectory, configuration);
        cancellation.ThrowIfCancellationRequested();
        if (closing) throw new OperationCanceledException("Host is closing.");
        if (!string.Equals(Path.GetFullPath(environment.UserDataFolder), options.ProfileDirectory, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("WebView2 selected an unexpected profile.");
        environment.BrowserProcessExited += (_, _) => stop("browser-exited");
        controller = await environment.CreateCoreWebView2ControllerAsync((await window.Task).Handle);
        // Capture ownership before any later validation can fail.
        BrowserPid = checked((int)controller.CoreWebView2.BrowserProcessId);
        browser = Process.GetProcessById(BrowserPid);
        _ = browser.SafeHandle;
        if (closing || cancellation.IsCancellationRequested)
        {
            controller.Close();
            controller = null;
            throw new OperationCanceledException(cancellation);
        }
        string executable = Path.GetFullPath(browser.MainModule?.FileName ??
            throw new InvalidOperationException("Cannot inspect the WebView2 browser process."));
        if (!string.Equals(executable, options.BrowserExecutable, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("WebView2 did not start from the bundled Fixed Version directory.");
        controller.Bounds = new Rectangle(0, 0, 1280, 800);
        controller.IsVisible = false;
        var view = controller.CoreWebView2;
        view.LaunchingExternalUriScheme += (_, e) => e.Cancel = true;
        // This CLI host owns one view. Keep target=_blank/window.open links
        // inside that view, with the same permission/external-URI handlers,
        // rather than creating an unmanaged top-level WebView window.
        view.NewWindowRequested += (_, e) =>
        {
            e.Handled = true;
            if (Uri.TryCreate(e.Uri, UriKind.Absolute, out var destination) &&
                destination.Scheme is "http" or "https")
                view.Navigate(destination.AbsoluteUri);
        };
        view.PermissionRequested += (_, e) => e.State = CoreWebView2PermissionState.Deny;
        view.DownloadStarting += (_, e) =>
        {
            var ticket = download;
            if (ticket is null || ticket.State != "ARMED" || DateTime.UtcNow >= ticket.Deadline || e.DownloadOperation.Uri != ticket.Url)
            { e.Cancel = true; return; }
            ticket.Engine = e.DownloadOperation;
            ticket.State = "STARTED";
            e.ResultFilePath = ticket.Path;
            e.Handled = true;
            ticket.Engine.BytesReceivedChanged += (_, _) =>
            {
                if (ticket.Engine.BytesReceived > ticket.MaxBytes) { ticket.State = "LIMIT"; ticket.Engine.Cancel(); }
            };
            ticket.Engine.StateChanged += (_, _) =>
            {
                if (ticket.State != "STARTED") return;
                ticket.State = ticket.Engine.State == CoreWebView2DownloadState.Completed ? "COMPLETE" :
                    ticket.Engine.State == CoreWebView2DownloadState.Interrupted ? "PARTIAL" : "STARTED";
            };
        };
        downloadTimer = new System.Windows.Forms.Timer { Interval = 100 };
        downloadTimer.Tick += (_, _) =>
        {
            if (download is { } ticket && DateTime.UtcNow >= ticket.Deadline && ticket.State is "ARMED" or "STARTED")
            { ticket.State = "TIMEOUT"; ticket.Engine?.Cancel(); }
        };
        downloadTimer.Start();
        view.ProcessFailed += (_, _) => stop("process-failed");
        view.Settings.AreHostObjectsAllowed = false;
        view.Settings.IsWebMessageEnabled = false;
        if (view.Source != "about:blank") throw new InvalidOperationException("Initial page is not about:blank.");
        int port = await ReadDebuggingPortAsync(cancellation);
        return new
        {
            @event = "ready", token = options.Token, hostPid = Environment.ProcessId,
            browserPid = BrowserPid, runtimeVersion = environment.BrowserVersionString,
            runtimeDirectory = options.RuntimeDirectory, browserExecutable = executable,
            cdpEndpoint = "http://127.0.0.1:" + port.ToString(CultureInfo.InvariantCulture),
            profileDirectory = options.ProfileDirectory
        };
    });

    internal Task<object> ControlAsync(ControlCommand request) => OnUiAsync<object>(() =>
    {
        if (controller is null || closing) throw new InvalidDataException("Host is closed.");
        if (request.Command is "show" or "hide")
        {
            var form = window.Task.Result;
            bool visible = request.Command == "show";
            controller.IsVisible = visible;
            if (visible) { form.Show(); form.Activate(); controller.MoveFocus(CoreWebView2MoveFocusReason.Programmatic); }
            else form.Hide();
            return Task.FromResult<object>(new { @event = "control", token = options.Token, command = request.Command, visible });
        }
        if (request.Command == "download-arm")
        {
            if (download?.State is "ARMED" or "STARTED" || !Guid.TryParseExact(request.Operation, "N", out _) ||
                !Uri.TryCreate(request.Url, UriKind.Absolute, out var uri) || uri.Scheme is not ("http" or "https") ||
                request.MaxBytes is < 1 or > 33554432 || request.TimeoutMs is < 100 or > 30000 || request.Path is null)
                throw new InvalidDataException("Invalid download permit.");
            string path = Path.GetFullPath(request.Path);
            if (Path.GetFileName(path) != "payload.part" || !Directory.Exists(Path.GetDirectoryName(path)) || File.Exists(path))
                throw new InvalidDataException("Invalid owned download path.");
            download = new(request.Operation!, uri.AbsoluteUri, path, request.MaxBytes, DateTime.UtcNow.AddMilliseconds(request.TimeoutMs));
        }
        if (download is null || download.Operation != request.Operation) throw new InvalidDataException("Unknown download operation.");
        if (request.Command == "download-cancel" && download.State is "ARMED" or "STARTED")
        { download.State = "CANCELLED"; download.Engine?.Cancel(); }
        return Task.FromResult<object>(new { @event = "control", token = options.Token, command = request.Command,
            operation = download.Operation, state = download.State, received = download.Engine?.BytesReceived ?? 0,
            mime = download.Engine?.MimeType ?? "" });
    });

    private async Task<int> ReadDebuggingPortAsync(CancellationToken cancellation)
    {
        string[] files =
        [
            Path.Combine(options.ProfileDirectory, "DevToolsActivePort"),
            Path.Combine(options.ProfileDirectory, "EBWebView", "DevToolsActivePort")
        ];
        var deadline = Stopwatch.StartNew();
        while (deadline.Elapsed < TimeSpan.FromSeconds(15))
        {
            cancellation.ThrowIfCancellationRequested();
            foreach (string file in files)
            {
                try
                {
                    if (!File.Exists(file) || new FileInfo(file).Length > 4096) continue;
                    string? line = (await File.ReadAllLinesAsync(file, cancellation)).FirstOrDefault();
                    if (int.TryParse(line, NumberStyles.None, CultureInfo.InvariantCulture, out int port) && port is > 0 and <= 65535)
                        return port;
                }
                catch (IOException) { } // Chromium may still be writing the port file.
            }
            if (browser!.HasExited) throw new InvalidOperationException("WebView2 exited during startup.");
            await Task.Delay(50, cancellation);
        }
        throw new TimeoutException("WebView2 did not publish its CDP port.");
    }

    internal async Task<bool> CloseAsync()
    {
        bool exited = true;
        try
        {
            await OnUiAsync(() =>
            {
                closing = true;
                downloadTimer?.Stop(); downloadTimer?.Dispose();
                if (download?.State is "STARTED") download.Engine?.Cancel();
                return Task.FromResult(true);
            }).WaitAsync(TimeSpan.FromSeconds(3));
            // An in-flight native creation must settle while the STA still pumps.
            // Its continuation captures and closes any controller created after cancellation.
            if (startup is not null)
            {
                try { await startup.WaitAsync(TimeSpan.FromSeconds(8)); }
                catch (Exception) when (startup.IsCompleted) { }
            }
            await OnUiAsync(() =>
            {
                controller?.Close();
                controller = null;
                return Task.FromResult(true);
            }).WaitAsync(TimeSpan.FromSeconds(3));
            if (browser is not null)
                await browser.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(8));
        }
        catch (Exception e) when (e is TimeoutException or InvalidOperationException or System.ComponentModel.Win32Exception)
        {
            Console.Error.WriteLine("WebView2 close was not confirmed: " + e.Message);
            exited = false;
        }
        finally
        {
            if (window.Task.IsCompletedSuccessfully)
            {
                try { window.Task.Result.BeginInvoke((Action)Application.ExitThread); }
                catch (InvalidOperationException) { }
            }
            ui.Join(2000);
            browser?.Dispose();
        }
        return exited;
    }

    private async Task<T> OnUiAsync<T>(Func<Task<T>> action)
    {
        Form form = await window.Task;
        var completion = new TaskCompletionSource<T>(TaskCreationOptions.RunContinuationsAsynchronously);
        form.BeginInvoke((Action)(async () =>
        {
            try { completion.TrySetResult(await action()); }
            catch (Exception e) { completion.TrySetException(e); }
        }));
        return await completion.Task;
    }
}
