using Microsoft.Web.WebView2.Core;
using NovaBrowserHost;

// Contract-only dependency injection. No product bootstrap flag accepts faults.
if (args.Length != 2) return 1;
string mode = args[0], root = args[1];
if (mode == "version")
{
    foreach (string actual in new[] { "1.0.0.0", "malformed" })
    {
        try { WebView2Runtime.RequireCompatible(actual, "154.0.4258.31"); return 2; }
        catch (IpcFailure e) when (e.Code == "RUNTIME_INCOMPATIBLE") { }
    }
    Console.WriteLine("RUNTIME_INCOMPATIBLE:PASS"); return 0;
}
using var engine = new WebView2Runtime(root, "bhi_" + new string('1',32), new FaultFactory(mode));
string expected = mode switch { "absent" => "RUNTIME_ABSENT", "incompatible" => "RUNTIME_INCOMPATIBLE",
    "environment" => "ENVIRONMENT_CREATION_FAILED", "controller" => "CONTROL_CREATION_FAILED", _ => "INVALID_STATE" };
try
{
    await engine.CreateSession();
    await engine.CreatePage("bwp_" + new string('2',32));
    return 3;
}
catch (IpcFailure e) when (e.Code == expected)
{
    await engine.CloseSession(5000);
    Console.WriteLine(expected + ":PASS"); return 0;
}

sealed class FaultFactory(string mode) : IWebView2Factory
{
    private readonly InstalledWebView2Factory real = new();
    public string AvailableVersion() => mode switch
    { "absent" => throw new WebView2RuntimeNotFoundException(), "incompatible" => "1.0.0.0", _ => real.AvailableVersion() };
    public Task<CoreWebView2Environment> Environment(string udf, CoreWebView2EnvironmentOptions options) =>
        mode == "environment" ? throw new InvalidOperationException("controlled test failure") : real.Environment(udf,options);
    public Task<CoreWebView2Controller> Controller(CoreWebView2Environment environment, IntPtr hwnd, CoreWebView2ControllerOptions options) =>
        throw new InvalidOperationException("controlled test failure");
}
