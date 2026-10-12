using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;

namespace NovaBrowserHost;

internal sealed partial class ObservationRuntime
{
    private sealed record Binding(string ObjectId, string Meta, string Fingerprint, string PublicFingerprint, string Origin, long Epoch, long Version);
    private readonly CoreWebView2 view;
    private readonly ExternalProtocolGuard guard;
    private readonly SensitiveValueRegistry secrets;
    private readonly Dictionary<string,Binding> bindings=[];
    private readonly List<string> dialogs=[];
    private readonly List<string> disclosed=[]; // bounded ephemeral redaction, never audit/UDF
    private string group="nova-observation";
    private long epoch, version;
    private bool busy;
    private readonly bool productiveV12;
    private string? admittedNavigation;
    private string? productiveOwner,productiveWorkspace;
    public string? LocalOrigin { get; private set; }
    public ObservationRuntime(CoreWebView2 view,ExternalProtocolGuard guard,string? udf=null,long maxTransferBytes=0,SensitiveValueRegistry? secrets=null,bool productiveV12=false)
    {
        this.view=view;this.guard=guard;this.secrets=secrets??new SensitiveValueRegistry();
        this.productiveV12=productiveV12;
        transferRoot=udf;transferLimit=maxTransferBytes;view.DownloadStarting+=DownloadStarting;
        view.NavigationStarting+=(_,e)=>
        {
            // Legacy v2-v5 keep the explicit offline mapping. V1.2 permits
            // only one exact Nova top-level navigation accepted over private
            // IPC, or an actual human navigation during takeover. This is an
            // action boundary, NEVER browser network isolation or PUBLIC_ONLY.
            if(Uri.TryCreate(e.Uri,UriKind.Absolute,out var destination)&&destination.Scheme is "http" or "https")
            {
                bool admitted=productiveV12?(humanPaused||admittedNavigation==destination.AbsoluteUri):LocalDestination(e.Uri);
                admittedNavigation=null; // one-use; redirects need new authority
                if(!admitted){e.Cancel=true;Invalidate(false);}else Invalidate(true);
            }
            else
            {
                if(productiveV12&&e.Uri!="about:blank")e.Cancel=true;
                Invalidate(false); // denied protocol attempt is not a new document/origin
            }
        };
        view.SourceChanged+=(_,_)=>Invalidate(true);
        view.NewWindowRequested+=(_,_)=>Invalidate(false); // guard already handles DENY_ALL
        view.FrameCreated+=(_,e)=>e.Frame.NavigationStarting+=(_,_)=>Invalidate(true);
        view.ScriptDialogOpening+=(_,e)=> { dialogs.Add("Dialog suppressed: "+e.Kind); if(dialogs.Count>16)dialogs.RemoveAt(0); Invalidate(false); };
    }
    public void ConfigureLocal(string directory,string host)
    {
        Protocol.Need(LocalOrigin is null && Directory.Exists(directory) && Path.IsPathFullyQualified(directory),"OWNERSHIP_MISMATCH");
        Protocol.Need(host.EndsWith(".invalid",StringComparison.Ordinal) && Uri.CheckHostName(host)==UriHostNameType.Dns);
        LocalOrigin="https://"+host;
        if(transferLimit>0)ConfigureOfflineTransferResources(directory);
        else
        {
            view.SetVirtualHostNameToFolderMapping(host,directory,CoreWebView2HostResourceAccessKind.DenyCors);
            view.SetVirtualHostNameToFolderMapping("nova-second.invalid",directory,CoreWebView2HostResourceAccessKind.DenyCors);
        }
    }
    private bool LocalDestination(string url)=>url=="about:blank"||LocalOrigin is not null&&Uri.TryCreate(url,UriKind.Absolute,out var u)&&(u.GetLeftPart(UriPartial.Authority)==LocalOrigin||u.GetLeftPart(UriPartial.Authority)=="https://nova-second.invalid");
    public void Invalidate(bool navigation){ bindings.Clear();version++;if(navigation)epoch++; }
    private void Ready(){guard.Require();secrets.Require();Protocol.Need(!humanPaused,"TAKEOVER_ACTIVE");Protocol.Need(!busy,"BUSY");}
    private static string Fingerprint(string meta)=>Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(meta)));
    private static string Origin(string url)=>Uri.TryCreate(url,UriKind.Absolute,out var u)&&u.Scheme is "https" or "http"?u.GetLeftPart(UriPartial.Authority):"null";
    private async Task<JsonElement> Cdp(string method,object parameters)
    {
        string json=await view.CallDevToolsProtocolMethodAsync(method,JsonSerializer.Serialize(parameters));
        using var doc=JsonDocument.Parse(json);return doc.RootElement.Clone();
    }
    private async Task<JsonElement> Value(string expression,int context)
    {
        var r=await Cdp("Runtime.evaluate",new{expression,contextId=context,returnByValue=true});
        Protocol.Need(!r.TryGetProperty("exceptionDetails",out _),"STALE_TARGET");
        return r.GetProperty("result").GetProperty("value");
    }
    private async Task<JsonElement> Call(string id,string function,object[]? arguments=null)
    {
        var r=await Cdp("Runtime.callFunctionOn",new{objectId=id,functionDeclaration=function,arguments=arguments??[],returnByValue=true});
        Protocol.Need(!r.TryGetProperty("exceptionDetails",out _),"STALE_TARGET");
        return r.GetProperty("result").GetProperty("value");
    }
    private async Task<List<(int Context,string Origin)>> Worlds()
    {
        await Cdp("Page.enable",new{});
        var tree=(await Cdp("Page.getFrameTree",new{})).GetProperty("frameTree");
        var result=new List<(int,string)>();string top=Origin(view.Source);
        async Task Walk(JsonElement t)
        {
            var f=t.GetProperty("frame");string url=f.GetProperty("url").GetString()!;
            string origin=f.TryGetProperty("securityOrigin",out var security)?security.GetString()!:Origin(url);
            if(origin==top && top!="null")
            {
                var w=await Cdp("Page.createIsolatedWorld",new{frameId=f.GetProperty("id").GetString(),worldName=ObservationScripts.Version,grantUniveralAccess=false});
                result.Add((w.GetProperty("executionContextId").GetInt32(),top));
            }
            if(t.TryGetProperty("childFrames",out var children))foreach(var c in children.EnumerateArray())await Walk(c);
        }
        await Walk(tree);return result;
    }
    public async Task<object> Capture(int maxElements,int maxText,int maxField)
    {
        Ready();busy=true;
        try
        {
            if(trackingInstalled)await SensitiveCheckpoint(false);
            bindings.Clear();version++;long e=epoch,v=version;
            if(Origin(view.Source)=="null")return new{kind="capture",engineEpoch=e,engineVersion=v,url="about:blank",title="",text="",elements=Array.Empty<object>(),dialogs=Array.Empty<string>()};
            try{await Cdp("Runtime.releaseObjectGroup",new{objectGroup=group});}catch(ArgumentException){}
            group="nova-observation-"+Guid.NewGuid().ToString("N");
            var worlds=await Worlds();var rawRows=new List<(string Key,string Fingerprint,JsonElement Meta,string[] Caps)>();var textLeaves=new List<PageDerivedTextLeaf>();string title="",text="";int rawTextChars=0;
            foreach(var w in worlds)
            {
                var summary=await Value(ObservationScripts.Summary,w.Context);
                Protocol.Closed(summary,"title","leaves","truncated");
                Protocol.Need(!summary.GetProperty("truncated").GetBoolean(),"OBSERVATION_LIMIT");
                Protocol.Need(Encoding.UTF8.GetByteCount(summary.GetRawText())<=PageDerivedTextLeaves.MaxPayloadUtf8&&summary.GetProperty("title").GetString()!.Length<=16384,"OBSERVATION_LIMIT");
                if(title.Length==0)title=summary.GetProperty("title").GetString()!;
                var leaves=PageDerivedTextLeaves.Read(summary.GetProperty("leaves"),32768);
                rawTextChars=checked(rawTextChars+leaves.Sum(l=>l.Text.Length));textLeaves.AddRange(leaves);
                Protocol.Need(rawTextChars<=PageDerivedTextLeaves.MaxRawChars&&textLeaves.Count<=PageDerivedTextLeaves.MaxLeaves,"OBSERVATION_LIMIT");
                var list=await Cdp("Runtime.evaluate",new{expression=ObservationScripts.Nodes,contextId=w.Context,returnByValue=false,objectGroup=group});
                string id=list.GetProperty("result").GetProperty("objectId").GetString()!;
                var props=await Cdp("Runtime.getProperties",new{objectId=id,ownProperties=true});
                foreach(var p in props.GetProperty("result").EnumerateArray())
                {
                    if(rawRows.Count>=maxElements+1)break; // AW2 overflow sentinel: whole extra row, no public ref
                    if(!int.TryParse(p.GetProperty("name").GetString(),out _)||!p.TryGetProperty("value",out var node)||!node.TryGetProperty("objectId",out var obj))continue;
                    string objId=obj.GetString()!;var m=await Call(objId,ObservationScripts.Meta);
                    if(!m.GetProperty("visible").GetBoolean()||m.GetProperty("secret").GetBoolean()||m.GetProperty("credentialForm").GetBoolean()||m.GetProperty("name").GetString()!.Length>maxField)continue;
                    string meta=m.GetRawText(),fp=Fingerprint(meta),key="wvb_"+Guid.NewGuid().ToString("N");
                    // Public fingerprint is an opaque incarnation identity, not
                    // a digest of private DOM data/URLs/credentials. Exact stale
                    // proof still uses the unprojected native fingerprint.
                    string publicFp=Convert.ToHexStringLower(RandomNumberGenerator.GetBytes(32));
                    bindings.Add(key,new(objId,meta,fp,publicFp,w.Origin,e,v));
                    var caps=m.GetProperty("caps").EnumerateArray().Select(c=>c.GetString()!).Where(c=>transferLimit>0||c is not ("UPLOAD_FILE" or "DOWNLOAD")).ToArray();
                    rawRows.Add((key,publicFp,m,caps));
                }
            }
            Protocol.Need(epoch==e&&version==v,"STALE_TARGET");
            // Redact BEFORE truncation; never publish a prefix sliced out of a
            // known value. Fence current documents again before IPC admission.
            if(trackingInstalled)await SensitiveCheckpoint(false);
            // Protect exact short transient leaves before host-added separators
            // change equality. Final checkpoint still precedes all redaction.
            title=Redact(title);text=PageDerivedTextLeaves.SafeSummary(textLeaves,Redact);
            // PAGE_DERIVED_DATA only, after the final sensitive checkpoint.
            // Bindings, fingerprints, capabilities, epochs and fixed `kind`
            // are CONTROL_PLANE and never pass through SensitiveRedactor.
            var rows=rawRows.Select(row=>
            {
                var m=row.Meta;
                string safeName=Redact(PageDerivedTextLeaves.SafeSummary(PageDerivedTextLeaves.Read(m.GetProperty("nameLeaves"),16384),Redact).Trim());
                // Host-fixed destination candidate for exact V1.2 approval:
                // a link href or the enclosing form target. Never authority.
                var destination=m.GetProperty("href").ValueKind==JsonValueKind.Null?m.GetProperty("formAction"):m.GetProperty("href");
                return new{binding=row.Key,fingerprint=row.Fingerprint,role=Redact(m.GetProperty("role").GetString()!),name=safeName,kind=Redact(m.GetProperty("kind").GetString()!),capabilities=row.Caps,state=Redact(m.GetProperty("state").GetString()!),href=destination.ValueKind==JsonValueKind.Null?null:secrets.PublicUrl(destination.GetString()!),isForm=m.GetProperty("tag").GetString()=="form"};
            }).ToArray();
            object result=new{kind="capture",engineEpoch=e,engineVersion=v,url=secrets.PublicUrl(view.Source),title=title[..Math.Min(title.Length,maxField+1)],text=text[..Math.Min(text.Length,maxText+1)],elements=rows,dialogs=dialogs.Select(Redact).ToArray()};
            Protocol.Need(epoch==e&&version==v,"STALE_TARGET");
            Protocol.Need(JsonSerializer.SerializeToUtf8Bytes(result).Length<14000,"OBSERVATION_LIMIT");return result;
        }
        finally{busy=false;}
    }
    private static string Sanitize(string url)
    {if(!Uri.TryCreate(url,UriKind.Absolute,out var u)||u.Scheme is not ("https" or "http"))return "about:blank";return new UriBuilder(u){UserName="",Password="",Query="",Fragment=""}.Uri.AbsoluteUri;}
    private string Redact(string value){foreach(string input in disclosed.OrderByDescending(x=>x.Length))value=value.Replace(input,"[INPUT_REDACTED]",StringComparison.Ordinal);return secrets.Redact(value);}
    private async Task<(Binding B,JsonElement M)?> Proof(string key)
    {
        guard.Require();
        if(!bindings.TryGetValue(key,out var b)||b.Epoch!=epoch||b.Version!=version||b.Origin!=Origin(view.Source))return null;
        try
        {
            var m=await Call(b.ObjectId,ObservationScripts.Meta);
            if(!m.GetProperty("connected").GetBoolean()||!m.GetProperty("visible").GetBoolean()||Fingerprint(m.GetRawText())!=b.Fingerprint)return null;
            return(b,m);
        }
        catch(IpcFailure){return null;}
    }
    public async Task<object> Resolve(string key)
    {
        Ready();var p=await Proof(key);
        return new{kind="resolve",found=p is not null,fingerprint=p?.B.PublicFingerprint,origin=p is null?null:Origin(secrets.PublicUrl(p.Value.B.Origin)),capabilities=p?.M.GetProperty("caps"),engineEpoch=epoch,engineVersion=version};
    }
    public async Task<object> Act(string action,string? key,string payload,Func<Task> started,JsonElement fields,int budgetMs)
    {
        Ready();busy=true;
        try
        {
            var proof=key is null?null:await Proof(key);
            var formFields=new List<(Binding B,string Value)>();
            if(action=="FORM_SUBMIT")
                foreach(var f in fields.EnumerateArray())
                {
                    var p=await Proof(f.GetProperty("binding").GetString()!);
                    if(p is null||!p.Value.M.GetProperty("caps").EnumerateArray().Any(c=>c.GetString()=="INPUT_TEXT"))return Report(false,"FAILED_NO_EFFECT_CONFIRMED","STALE_TARGET");
                    formFields.Add((p.Value.B,f.GetProperty("value").GetString()!));
                }
            bool pageAction=action is "SCROLL" or "BACK" or "FORWARD" or "WAIT";
            if(!pageAction&&(proof is null||!proof.Value.M.GetProperty("caps").EnumerateArray().Any(c=>c.GetString()==action)))return Report(false,"FAILED_NO_EFFECT_CONFIRMED","STALE_TARGET");
            if(action=="PRESS_KEY"&&!new[]{"Enter","Tab","Escape","ArrowUp","ArrowDown","ArrowLeft","ArrowRight","Space"}.Contains(payload))return Report(false,"FAILED_NO_EFFECT_CONFIRMED","INVALID_ACTION");
            double wait=0;
            if(action=="SCROLL"&&payload is not ("up" or "down")||action=="WAIT"&&(!double.TryParse(payload,System.Globalization.NumberStyles.Float,System.Globalization.CultureInfo.InvariantCulture,out wait)||!double.IsFinite(wait)||wait<=0||wait>budgetMs/1000.0))return Report(false,"FAILED_NO_EFFECT_CONFIRMED","INVALID_ACTION");
            string? destination=proof?.M.GetProperty("href").ValueKind==JsonValueKind.String?proof?.M.GetProperty("href").GetString():null;
            if(action=="NAVIGATE")
            {
                if(productiveV12)
                {
                    if(destination is null||destination!=payload)return Report(false,"FAILED_NO_EFFECT_CONFIRMED","STALE_TARGET");
                    ProductiveProtocol.CanonicalTarget(destination);admittedNavigation=destination;
                }
                else if(!LocalDestination(destination??""))return Report(false,"FAILED_NO_EFFECT_CONFIRMED","PUBLIC_NAVIGATION_NOT_AVAILABLE");
            }
            // Snapshot removed before engine receipt; exact remote object retained
            // locally for the single dispatch. Never look up a replacement node.
            Invalidate(action is "BACK" or "FORWARD" or "NAVIGATE");
            if(action is "INPUT_TEXT" or "SELECT_OPTION"&&payload.Length>0)disclosed.Add(payload);
            foreach(var f in formFields)if(f.Value.Length>0)disclosed.Add(f.Value);
            if(disclosed.Count>64)throw new IpcFailure("INVALID_ACTION"); // never evict redaction knowledge to publish a value
            await started(); // Engine has accepted a potentially effectful action.
            try
            {
                if(pageAction)
                {
                    if(action=="WAIT")await Task.Delay(TimeSpan.FromSeconds(wait));
                    else if(action=="SCROLL")await view.CallDevToolsProtocolMethodAsync("Runtime.evaluate",JsonSerializer.Serialize(new{expression=payload=="up"?"window.scrollBy(0,-innerHeight)":"window.scrollBy(0,innerHeight)"}));
                    else if(action=="BACK"&&view.CanGoBack)await Navigation(()=>view.GoBack());
                    else if(action=="FORWARD"&&view.CanGoForward)await Navigation(()=>view.GoForward());
                    else return Report(true,"FAILED_NO_EFFECT_CONFIRMED","NO_HISTORY_ENTRY");
                }
                else if(action=="PRESS_KEY")
                {
                    // Revalidate exact object once more, then focus it. Actual
                    // keyboard dispatch is CDP, never page-supplied key/code.
                    var m=await Call(proof!.Value.B.ObjectId,ObservationScripts.Meta);
                    if(Fingerprint(m.GetRawText())!=proof.Value.B.Fingerprint)return Report(true,"FAILED_NO_EFFECT_CONFIRMED","STALE_TARGET");
                    await Cdp("Emulation.setFocusEmulationEnabled",new{enabled=true});
                    await Call(proof.Value.B.ObjectId,"function(){this.focus();return true;}");
                    var fresh=await Call(proof.Value.B.ObjectId,"function(){const m=("+ObservationScripts.Meta+").call(this);return {meta:m,focused:this===document.activeElement};}");
                    if(!fresh.GetProperty("focused").GetBoolean()||Fingerprint(fresh.GetProperty("meta").GetRawText())!=proof.Value.B.Fingerprint)return Report(true,"UNKNOWN",null);
                    var codes=new Dictionary<string,int>{{"Enter",13},{"Tab",9},{"Escape",27},{"ArrowUp",38},{"ArrowDown",40},{"ArrowLeft",37},{"ArrowRight",39},{"Space",32}};
                    await Cdp("Input.dispatchKeyEvent",new{type="keyDown",key=payload=="Space"?" ":payload,windowsVirtualKeyCode=codes[payload]});
                    if(payload=="Enter")await Cdp("Input.dispatchKeyEvent",new{type="char",key="Enter",text="\r",unmodifiedText="\r",windowsVirtualKeyCode=13});
                    await Cdp("Input.dispatchKeyEvent",new{type="keyUp",key=payload=="Space"?" ":payload,windowsVirtualKeyCode=codes[payload]});
                }
                else
                {
                    object[] arguments=[new{value=new{expected=proof!.Value.B.Meta,action,payload,destination}}];
                    string function=ObservationScripts.Perform;
                    if(action=="FORM_SUBMIT")
                    {
                        function=ObservationScripts.Submit;
                        arguments=[new{value=new{expected=proof.Value.B.Meta,fieldMeta=formFields.Select(f=>f.B.Meta).ToArray(),values=formFields.Select(f=>f.Value).ToArray()}},..formFields.Select(f=>(object)new{objectId=f.B.ObjectId})];
                    }
                    JsonElement r=default;
                    if(action=="NAVIGATE")await Navigation((Func<Task>)(async()=>{r=await Call(proof.Value.B.ObjectId,function,arguments);}));
                    else r=await Call(proof.Value.B.ObjectId,function,arguments);
                    if(r.TryGetProperty("partial",out _))return Report(true,"PARTIAL",null);
                    if(r.TryGetProperty("stale",out _)||r.TryGetProperty("noEffect",out _))return Report(true,"FAILED_NO_EFFECT_CONFIRMED","STALE_TARGET");
                }
                return Report(true,"SUCCEEDED_OBSERVED",null);
            }
            catch {return Report(true,"UNKNOWN",null);}
        }
        finally{busy=false;admittedNavigation=null;}
    }
    public async Task<object> NavigateAdmitted(JsonElement fields,Func<Task> started,int budgetMs)
    {
        Ready();Protocol.Need(productiveV12,"NOT_SUPPORTED_IN_CURRENT_BLOCK");busy=true;
        bool dispatched=false;
        object Receipt(string outcome,string? error=null)=>new{kind="navigate_admitted",started=dispatched,outcome,error,engineEpoch=epoch,engineVersion=version};
        try
        {
            string owner=Protocol.Text(fields.GetProperty("ownerSessionId")),workspace=Protocol.Text(fields.GetProperty("workspaceDigest"));
            if(productiveOwner is not null&&(productiveOwner!=owner||productiveWorkspace!=workspace))return Receipt("FAILED_NO_EFFECT_CONFIRMED","OWNERSHIP_MISMATCH");
            string target=ProductiveProtocol.CanonicalTarget(Protocol.Text(fields.GetProperty("canonicalTarget")));
            productiveOwner=owner;productiveWorkspace=workspace;
            Invalidate(true);admittedNavigation=target;
            await started();dispatched=true;
            var done=new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
            EventHandler<CoreWebView2NavigationCompletedEventArgs> finished=(_,e)=>done.TrySetResult(e.IsSuccess);
            view.NavigationCompleted+=finished;
            try
            {
                view.Navigate(target);
                bool completed=await done.Task.WaitAsync(TimeSpan.FromMilliseconds(Math.Min(budgetMs,30000)));
                return Receipt(completed&&view.Source==target?"SUCCEEDED_OBSERVED":"UNKNOWN");
            }
            finally{view.NavigationCompleted-=finished;}
        }
        catch{return Receipt(dispatched?"UNKNOWN":"FAILED_NO_EFFECT_CONFIRMED");}
        finally{busy=false;admittedNavigation=null;}
    }
    private object Report(bool started,string outcome,string? error)=>new{kind="act",started,outcome,error,engineEpoch=epoch,engineVersion=version};
    private async Task Navigation(System.Action action)
    {
        var done=new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        EventHandler<CoreWebView2NavigationCompletedEventArgs> callback=(_,e)=>done.TrySetResult(e.IsSuccess);
        view.NavigationCompleted+=callback;
        try{action();Protocol.Need(await done.Task.WaitAsync(TimeSpan.FromSeconds(5)),"LOCAL_NAVIGATION_FAILED");}
        finally{view.NavigationCompleted-=callback;}
    }
    private async Task Navigation(Func<Task> action)
    {
        var done=new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        EventHandler<CoreWebView2NavigationCompletedEventArgs> callback=(_,e)=>done.TrySetResult(e.IsSuccess);
        view.NavigationCompleted+=callback;
        try{await action();Protocol.Need(await done.Task.WaitAsync(TimeSpan.FromSeconds(5)),"LOCAL_NAVIGATION_FAILED");}
        finally{view.NavigationCompleted-=callback;}
    }
}
