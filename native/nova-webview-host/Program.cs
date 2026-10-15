using System.Diagnostics;

namespace NovaWebViewHost;

internal static class Program
{
    private static async Task<int> Main(string[] args)
    {
        HostOptions options;
        Process owner;
        try
        {
            options = HostOptions.Parse(args);
            owner = Process.GetProcessById(options.OwnerPid);
            _ = owner.SafeHandle; // Keep the original process object, even if its PID is reused.
            if (owner.HasExited) throw new ArgumentException("The owner process already exited.");
        }
        catch (Exception e) when (e is ArgumentException or IOException or UnauthorizedAccessException or System.ComponentModel.Win32Exception)
        {
            Console.Error.WriteLine("Host configuration failed: " + e.Message);
            return 2;
        }

        using (owner)
        using (var cancellation = new CancellationTokenSource())
        {
            var start = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
            var stop = new TaskCompletionSource<string>(TaskCreationOptions.RunContinuationsAsynchronously);
            void Stop(string reason)
            {
                if (stop.TrySetResult(reason)) cancellation.Cancel();
            }
            _ = WatchOwnerAsync(owner, Stop, cancellation.Token);
            WindowsWebViewHost? host = null;
            _ = PrivateControl.ReadAsync(options.Token, () => start.TrySetResult(), Stop,
                request => host is not null ? host.ControlAsync(request) : throw new InvalidDataException("Host is not ready."), cancellation.Token);
            bool announced = false;
            int exitCode = 0;
            string reason = "startup-failed";
            try
            {
                // The launcher assigns its Windows Job before releasing this gate.
                await start.Task.WaitAsync(TimeSpan.FromSeconds(15), cancellation.Token);
                host = new WindowsWebViewHost(options, Stop);
                var ready = await host.StartAsync(cancellation.Token).WaitAsync(TimeSpan.FromSeconds(30), cancellation.Token);
                cancellation.Token.ThrowIfCancellationRequested();
                await PrivateControl.WriteAsync(ready);
                announced = true;
                reason = await stop.Task;
                if (reason is "invalid-control" or "browser-exited" or "process-failed") exitCode = 2;
            }
            catch (OperationCanceledException) when (cancellation.IsCancellationRequested)
            {
                reason = await stop.Task;
                if (reason is "invalid-control" or "browser-exited" or "process-failed") exitCode = 2;
            }
            catch (Exception e)
            {
                exitCode = 2;
                reason = e is TimeoutException ? "startup-timeout" : "startup-failed";
                Console.Error.WriteLine("WebView2 host failed: " + e.Message);
            }
            finally
            {
                bool browserExited = host is null || await host.CloseAsync();
                if (!browserExited) exitCode = 3;
                if (announced)
                {
                    try
                    {
                        await PrivateControl.WriteAsync(new
                        {
                            @event = "closed", token = options.Token, hostPid = Environment.ProcessId,
                            browserPid = host!.BrowserPid, reason, browserExited
                        });
                    }
                    catch (IOException) { exitCode = 3; }
                }
                cancellation.Cancel();
            }
            return exitCode;
        }
    }

    private static async Task WatchOwnerAsync(Process owner, Action<string> stop, CancellationToken cancellation)
    {
        try
        {
            await owner.WaitForExitAsync(cancellation);
            stop("owner-exited");
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
    }
}
