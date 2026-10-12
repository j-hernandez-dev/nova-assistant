using System.Diagnostics;
using System.Drawing;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;
using NovaBrowserHost;

// Certification executable only. Not a host IPC command, frontend, or tool.
// Native click/visibility below exercises the guard, not block04 actions or
// block05's future Application takeover integration.
if (args.Length == 3 && args[0] == "--canary")
{
    File.AppendAllText(args[1], Environment.ProcessId + "\n"); return 0;
}
if (args.Length != 6) return 2;
string mode=args[0], root=args[1], scheme=args[2], report=args[3], session=args[4], instance=args[5];
Protocol.Ref(session,"bws"); Protocol.Ref(instance,"bhi");
string first="bwp_"+Guid.NewGuid().ToString("N"), second="bwp_"+Guid.NewGuid().ToString("N");
int registrations=0;
using var engine=new WebView2Runtime(root,instance,browserSession:session,
    audit: mode=="audit-failure" ? new BrokenAudit() : null,
    guardFactory: (v,j,p,f) =>
    {
        registrations++;
        if(mode=="registration-failure" || (mode=="secondary-failure" && registrations==2)) throw new InvalidOperationException("controlled installation failure");
        return new ExternalProtocolGuard(v,j,p,f);
    });
var stages=new List<string>();
try
{
    await engine.CreateSession(); stages.Add("SESSION_CREATED");
    await engine.CreatePage(first); stages.Add("CONTROL_CREATED_GUARD_INSTALLED");
    if(mode is "secondary" or "secondary-failure")
    { await engine.CreatePage(second); stages.Add("SECONDARY_GUARD_INSTALLED"); }
    if(mode is "lost-guard" or "unexpected-dispose")
    {
        await Access.Ui(engine,()=> { if(mode=="lost-guard") Access.Guards(engine)[first].Revoke(); else Access.Guards(engine)[first].Dispose(); return Task.FromResult(true); });
        try { await engine.PageMetadata(first); return 3; }
        catch(IpcFailure e) when(e.Code=="GUARD_UNAVAILABLE") { stages.Add("LOST_GUARD_INVALIDATED"); }
    }
    else if(mode is not "health")
    {
        string uri=mode=="mailto" ? "mailto:guard-test@example.invalid" : scheme+"://synthetic-attempt";
        string html=mode switch
        {
            "click" or "takeover" => "<html><body style='margin:0'><a style='display:block;width:260px;height:140px' href='"+uri+"'>Controlled link</a></body></html>",
            "frame" => "<html><body style='margin:0'><iframe style='border:0;width:280px;height:160px' srcdoc=\"<body style='margin:0'><a style='display:block;width:260px;height:140px' href='"+uri+"'>frame link</a></body>\"></iframe></body></html>",
            "popup" => "<script>setTimeout(()=>window.open('"+uri+"','_blank'),150)</script>",
            _ => "<script>setTimeout(()=>location.href='"+uri+"',150)</script>"
        };
        var before=JsonSerializer.SerializeToElement(await engine.GuardMetadata());
        if(before.GetProperty("externalProtocolGuard").GetString()!="HOST_PRE_EFFECT_DENY") return 4;
        stages.Add("GUARD_VERIFIED_BEFORE_CONTENT");
        await Access.Load(engine,first,html);
        stages.Add("CONTROLLED_CONTENT_LOADED");
        if(mode is "click" or "takeover" or "frame")
        {
            await Access.Click(engine,first); stages.Add(mode=="takeover" ? "HUMAN_INTERACTION_EQUIVALENT_WHILE_GUARD_INSTALLED" : "NATIVE_MOUSE_CLICK");
        }
        if(mode=="secondary") await Access.Load(engine,second,html);
        // Wait for exactly the asynchronous native event, never retry a case.
        var until=Stopwatch.StartNew();
        while(until.ElapsedMilliseconds<5000)
        {
            var m=JsonSerializer.SerializeToElement(await engine.GuardMetadata());
            int count=m.GetProperty("receipts").GetArrayLength();
            if(count >= (mode=="secondary" ? 2 : 1)) break;
            await Task.Delay(25);
        }
    }
    var metadata=await engine.GuardMetadata();
    string runtime=mode is "lost-guard" or "unexpected-dispose" or "audit-failure" ? "failed-after-real-control" : JsonSerializer.SerializeToElement(await engine.Metadata()).GetProperty("runtimeVersion").GetString()!;
    var nativePids=Access.Processes(engine);
    await engine.CloseSession(10000);
    File.WriteAllText(report,JsonSerializer.Serialize(new { mode,session,instance,first,second,stages,metadata,runtime,
        hostPid=Environment.ProcessId,nativePids,cleanupConfirmed=!Directory.Exists(root),scheme,
        evidenceClass="EXTERNAL_PROTOCOL_GUARD_NATIVE_TEST",publicOnly="UNKNOWN",available="UNKNOWN" },new JsonSerializerOptions{WriteIndented=true}));
    return 0;
}
catch(IpcFailure e) when(mode is "registration-failure" or "secondary-failure")
{
    var metadata=await engine.GuardMetadata();
    await engine.CloseSession(10000);
    File.WriteAllText(report,JsonSerializer.Serialize(new { mode,session,instance,stages,error=e.Code,metadata,
        usable=false,cleanupConfirmed=!Directory.Exists(root),evidenceClass="EXTERNAL_PROTOCOL_GUARD_CONTRACT_TEST" }));
    return e.Code=="GUARD_UNAVAILABLE" ? 0 : 5;
}

sealed class BrokenAudit : IGuardAudit
{
    public void Append(object record) => throw new IOException("controlled sink failure");
    public void Dispose() { }
}
static class Access
{
    private static readonly BindingFlags Flags=BindingFlags.NonPublic|BindingFlags.Instance;
    public static Dictionary<string,CoreWebView2Controller> Pages(WebView2Runtime e)=>(Dictionary<string,CoreWebView2Controller>)typeof(WebView2Runtime).GetField("pages",Flags)!.GetValue(e)!;
    public static Dictionary<string,ExternalProtocolGuard> Guards(WebView2Runtime e)=>(Dictionary<string,ExternalProtocolGuard>)typeof(WebView2Runtime).GetField("guards",Flags)!.GetValue(e)!;
    public static int[] Processes(WebView2Runtime e)=>((List<Process>)typeof(WebView2Runtime).GetField("observedProcesses",Flags)!.GetValue(e)!).Select(p=>p.Id).ToArray();
    public static Task<T> Ui<T>(WebView2Runtime e,Func<Task<T>> work)=>(Task<T>)typeof(WebView2Runtime).GetMethod("OnUi",Flags)!.MakeGenericMethod(typeof(T)).Invoke(e,[work])!;
    public static async Task Load(WebView2Runtime e,string page,string html)
    {
        var done=new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        await Ui(e,()=>
        {
            Guards(e)[page].Require();
            var v=Pages(e)[page].CoreWebView2;
            v.NavigationCompleted+=(_,a)=> { if(a.IsSuccess) done.TrySetResult(true); };
            v.NavigateToString(html); return Task.FromResult(true);
        });
        await done.Task.WaitAsync(TimeSpan.FromSeconds(5));
    }
    public static async Task Click(WebView2Runtime e,string page)
    {
        await Ui(e,()=>
        {
            Guards(e)[page].Require();
            var form=((TaskCompletionSource<Form>)typeof(WebView2Runtime).GetField("ready",Flags)!.GetValue(e)!).Task.Result;
            form.ClientSize=new Size(300,200); form.Location=new Point(40,40);
            var controller=Pages(e)[page]; controller.Bounds=new Rectangle(0,0,300,200);
            form.Show(); controller.IsVisible=true; controller.MoveFocus(CoreWebView2MoveFocusReason.Programmatic);
            return Task.FromResult(true);
        });
        await Task.Delay(200);
        await Ui(e,()=>
        {
            // Deliver a trusted WM mouse interaction to WebView's owned child
            // window; no page .click() masquerading as a user gesture.
            var form=((TaskCompletionSource<Form>)typeof(WebView2Runtime).GetField("ready",Flags)!.GetValue(e)!).Task.Result;
            var windows=new List<IntPtr>();
            EnumChildWindows(form.Handle,(h,_)=> { windows.Add(h); return true; },IntPtr.Zero);
            foreach(var hwnd in windows)
            {
                SendMessage(hwnd,0x200,IntPtr.Zero,new IntPtr(40|(40<<16)));
                SendMessage(hwnd,0x201,new IntPtr(1),new IntPtr(40|(40<<16)));
                SendMessage(hwnd,0x202,IntPtr.Zero,new IntPtr(40|(40<<16)));
            }
            return Task.FromResult(true);
        });
    }
    private delegate bool EnumProc(IntPtr hwnd,IntPtr value);
    [DllImport("user32.dll")] private static extern bool EnumChildWindows(IntPtr hwnd,EnumProc proc,IntPtr value);
    [DllImport("user32.dll")] private static extern IntPtr SendMessage(IntPtr hwnd,uint msg,IntPtr w,IntPtr l);
}
