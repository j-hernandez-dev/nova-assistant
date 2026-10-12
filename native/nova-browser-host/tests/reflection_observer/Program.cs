using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Windows.Automation;

// Read-only certification observer, NOT the human driver/browser-host/product.
// Scope is the HWND owned by the correlated host PID, not the desktop tree.
// Names/text stay in this native process memory; only booleans/counts leave it.
// The existing fixture marker is inspected privately, never required to survive
// redaction in BrowserObservation. No input, script, IPC or authority is added.
if(args.Length!=2||!uint.TryParse(args[0],out uint pid)||args[1] is not("baseline" or "actor"))return 2;
try
{
    using var process=Process.GetProcessById((int)pid);
    bool actor=args[1]=="actor",window=false,document=false,reflection=false;
    var clock=Stopwatch.StartNew();
    do
    {
        var handles=new List<IntPtr>();
        Win.EnumWindows((h,_)=>{Win.GetWindowThreadProcessId(h,out uint owner);if(owner==pid&&Win.IsWindowVisible(h))handles.Add(h);return true;},IntPtr.Zero);
        window=handles.Count>0;
        foreach(var hwnd in handles)
        {
            var root=AutomationElement.FromHandle(hwnd);
            var nodes=root.FindAll(TreeScope.Descendants,Condition.TrueCondition);
            foreach(AutomationElement node in nodes)
            {
                if(node.Current.IsPassword)continue;
                if(node.Current.ControlType==ControlType.Document)document=true;
                // Existing fixture signal, read only at the private native UI
                // boundary. Never print the name or return it to Python/model.
                if(node.Current.Name.Contains("Safe result",StringComparison.Ordinal))reflection=true;
                if(node.Current.ControlType==ControlType.Document&&node.TryGetCurrentPattern(TextPattern.Pattern,out var pattern))
                    if(((TextPattern)pattern).DocumentRange.GetText(8192).Contains("Safe result",StringComparison.Ordinal))reflection=true;
            }
        }
        if(window&&document&&(!actor||reflection)||process.HasExited)break;
        Thread.Sleep(20); // Bounded UI-state acquisition, not a case/quality retry.
    }while(clock.ElapsedMilliseconds<3000);
    Console.WriteLine(JsonSerializer.Serialize(new{hostPid=pid,windowObserved=window,documentObserved=document,reflectionObserved=reflection,rawTextExported=false,readOnly=true}));
    return 0;
}
catch
{
    // No exception data, inaccessible UI text, paths or raw values in output.
    Console.WriteLine("{\"error\":\"NATIVE_FIXTURE_PROOF_UNAVAILABLE\",\"rawTextExported\":false}");return 3;
}
static class Win
{
    public delegate bool EnumProc(IntPtr h,IntPtr value);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc proc,IntPtr value);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h,out uint pid);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
}
