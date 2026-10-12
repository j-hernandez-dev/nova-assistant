using System.Drawing;
using System.Text.Json;
namespace NovaBrowserHost;

internal sealed partial class WebView2Runtime
{
    private bool takeoverActive,humanFinished,humanAborted;
    private string? takeoverPage;
    private long browserEpoch;
    private Button? returnControl;
    public Task<object> BeginTakeover(string page)=>OnUi<object>(async()=>
    {
        Usable();Protocol.Need(maxTransferBytes>0,"NOT_SUPPORTED_IN_CURRENT_BLOCK");
        Protocol.Need(pages.ContainsKey(page),"OWNERSHIP_MISMATCH");
        guards[page].Require();takeoverPage=page;humanFinished=false;humanAborted=false;
        // Redaction instrumentation is installed before the human UI is
        // exposed, in a private CDP world. Not a host object/page IPC bridge.
        try{foreach(var d in dom.Values)await d.ProtectHumanInput();}
        catch{secrets.Diagnose(SensitiveBoundaryFailureReason.CHECKPOINT_EXCEPTION,SensitiveBoundaryFailureSite.TAKEOVER_BEGIN_WRAPPER);failed=true;throw new IpcFailure("SECRET_BOUNDARY_UNCONFIRMED");}
        foreach(var d in dom.Values)d.PauseHuman(true);
        takeoverActive=true;
        var form=await ready.Task;form.Text="Nova — human browser control";
        form.ClientSize=new Size(960,700);form.StartPosition=FormStartPosition.CenterScreen;
        returnControl=new Button{Text="Return control to Nova",Name="nova-human-complete",Location=new Point(8,8),Size=new Size(230,35)};
        returnControl.Click+=(_,_)=> { humanFinished=true;returnControl.Enabled=false; };
        form.Controls.Add(returnControl);
        foreach(var p in pages.Values)p.IsVisible=false;
        pages[page].Bounds=new Rectangle(0,52,960,640);pages[page].IsVisible=true;
        form.FormClosing+=PreventHumanClose;
        form.Show();form.Activate();pages[page].MoveFocus(Microsoft.Web.WebView2.Core.CoreWebView2MoveFocusReason.Programmatic);
        return new{kind="takeover_begin",humanActive=true,contextEpoch=browserEpoch};
    });
    private void PreventHumanClose(object? sender,FormClosingEventArgs e)
    {if(takeoverActive){e.Cancel=true;humanAborted=true;failed=true;foreach(var p in pages.Values)p.IsVisible=false;ready.Task.Result.Hide();}}
    public Task<object> TakeoverState()=>OnUi<object>(()=>Task.FromResult<object>(new{kind="takeover_state",humanActive=takeoverActive,humanCompleted=humanFinished,humanAborted,contextEpoch=browserEpoch}));
    public Task<object> EndTakeover()=>OnUi<object>(async()=>
    {
        Protocol.Need(started&&!closed&&!failed&&takeoverActive&&humanFinished&&!humanAborted,"HUMAN_CONTROL_INCOMPLETE");
        try
        {
            secrets.RequireTerminalContinuity();
            foreach(var d in dom.Values)await d.RememberSensitive();
            secrets.RequireTerminalContinuity();
        }
        catch{secrets.Diagnose(SensitiveBoundaryFailureReason.CHECKPOINT_EXCEPTION,SensitiveBoundaryFailureSite.TAKEOVER_END_WRAPPER);failed=true;throw new IpcFailure("SECRET_BOUNDARY_UNCONFIRMED");}
        foreach(var g in guards.Values)g.Require();
        foreach(var p in pages.Values)p.IsVisible=false;
        var form=await ready.Task;form.Hide();form.FormClosing-=PreventHumanClose;
        if(returnControl is not null){form.Controls.Remove(returnControl);returnControl.Dispose();returnControl=null;}
        browserEpoch++;journal.ContextEpoch=browserEpoch;
        foreach(var d in dom.Values)d.PauseHuman(false);
        takeoverActive=false;takeoverPage=null;
        return new{kind="takeover_end",humanActive=false,contextEpoch=browserEpoch};
    });
    public Task<object> Upload(string page,JsonElement p,Func<Task> started)=>OnUi(()=>Dom(page).Upload(
        Protocol.Text(p.GetProperty("binding")),Protocol.Text(p.GetProperty("source")),Protocol.Text(p.GetProperty("filename")),
        p.GetProperty("size").GetInt64(),Protocol.Text(p.GetProperty("mime")),Protocol.Text(p.GetProperty("sha256")),started));
    public Task<object> Download(string page,string binding,long maxBytes,long deadline,Func<Task> started)=>OnUi(()=>Dom(page).Download(binding,maxBytes,deadline,started));
    public Task<object> TransferMetadata(string page)=>OnUi(()=>Task.FromResult(dom[page].TransferMetadata()));
}
