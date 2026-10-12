using System.Security.Cryptography;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;
namespace NovaBrowserHost;

internal sealed partial class ObservationRuntime
{
    private readonly string? transferRoot;
    private readonly long transferLimit;
    private bool humanPaused;
    private DownloadSlot? download;
    private readonly List<object> transferEvents=[];
    private void TransferEvent(object record)
    {transferEvents.Add(record);if(transferEvents.Count>32)transferEvents.RemoveAt(0);}
    private void ConfigureOfflineTransferResources(string directory)
    {
        // Trusted offline bootstrap only. Not a network control/broker: a
        // bounded local resource provider for the controlled certification
        // origin, with HTTP metadata. No fixture-specific filenames or values.
        view.AddWebResourceRequestedFilter("https://nova-local.invalid/*",CoreWebView2WebResourceContext.All);
        view.AddWebResourceRequestedFilter("https://nova-second.invalid/*",CoreWebView2WebResourceContext.All);
        view.WebResourceRequested+=(_,e)=>
        {
            var u=new Uri(e.Request.Uri);
            string name=Uri.UnescapeDataString(u.AbsolutePath)[1..];
            bool safe=name.Length>0&&Path.GetFileName(name)==name&&!name.Any(c=>char.IsControl(c)||c is '/' or '\\'||c==':')&&name is not ("." or "..");
            string? path=safe?Path.Combine(directory,name):null;
            bool exists=path is not null&&File.Exists(path)&&(File.GetAttributes(path)&FileAttributes.ReparsePoint)==0&&new FileInfo(path).Length<=64*1024*1024;
            var data=exists?File.ReadAllBytes(path!):Array.Empty<byte>();
            var stream=new MemoryStream(data,false);
            string mime=Path.GetExtension(name).ToLowerInvariant()switch{".html"=>"text/html",".txt"=>"text/plain",".css"=>"text/css",".js"=>"application/javascript",_=>"application/octet-stream"};
            e.Response=view.Environment.CreateWebResourceResponse(stream,exists?200:404,exists?"OK":"Not Found","Content-Type: "+mime+"\r\nContent-Length: "+data.Length+"\r\nCache-Control: no-store\r\n");
        };
        view.SaveFileSecurityCheckStarting+=(_,e)=>TransferEvent(new{kind="FILE_SECURITY_CHECK",extension=secrets.AuditSafe(e.FileExtension),defaultPolicy=!e.SuppressDefaultPolicy,cancelled=e.CancelSave});
    }
    private sealed class DownloadSlot(string uri,string token,long limit,long deadline)
    {
        public readonly string Uri=uri,Token=token;
        public readonly long Limit=limit,Deadline=deadline;
        public readonly TaskCompletionSource<CoreWebView2DownloadOperation> Done=new(TaskCreationOptions.RunContinuationsAsynchronously);
        public CoreWebView2DownloadOperation? Operation;
        public string Suggested="download";
        public bool Consumed;
    }
    private string Scratch(string kind,string token,string? filename=null)
    {
        Protocol.Need(transferRoot is not null&&transferLimit>0,"NOT_SUPPORTED_IN_CURRENT_BLOCK");
        Protocol.Ref(token,kind=="up"?"wvu":"wvd");
        string dir=Path.Combine(transferRoot!,"_nova_transfers",kind);
        if(filename is not null)dir=Path.Combine(dir,token);
        Directory.CreateDirectory(dir);
        for(var parent=new DirectoryInfo(dir);parent is not null&&parent.FullName.StartsWith(transferRoot!,StringComparison.OrdinalIgnoreCase);parent=parent.Parent)
            Protocol.Need((parent.Attributes&FileAttributes.ReparsePoint)==0,"TRANSFER_STALE");
        if(filename is not null)Protocol.Need(filename.Length is >0 and <=255&&Path.GetFileName(filename)==filename&&!filename.Any(c=>char.IsControl(c)||c is '/' or '\\')&&filename is not ("." or ".."),"TRANSFER_STALE");
        return Path.Combine(dir,filename??token+".bin");
    }
    public void PauseHuman(bool paused){guard.Require();humanPaused=paused;Invalidate(false);}
    public async Task<object> Upload(string key,string source,string filename,long size,string mime,string digest,Func<Task> started)
    {
        Ready();busy=true;
        try
        {
            var p=await Proof(key);
            if(p is null||!p.Value.M.GetProperty("caps").EnumerateArray().Any(c=>c.GetString()=="UPLOAD_FILE"))return Report(false,"FAILED_NO_EFFECT_CONFIRMED","STALE_TARGET");
            string path=Scratch("up",source,filename);
            Protocol.Need(File.Exists(path)&&(File.GetAttributes(path)&FileAttributes.ReparsePoint)==0,"TRANSFER_STALE");
            using var file=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.Read);
            Protocol.Need(size>=0&&size<=transferLimit&&file.Length==size&&Convert.ToHexStringLower(SHA256.HashData(file))==digest,"TRANSFER_STALE");
            Protocol.Need(mime.Length is >0 and <=128,"TRANSFER_STALE");
            Invalidate(false);await started();
            try
            {
                var fresh=await Call(p.Value.B.ObjectId,ObservationScripts.Meta);
                if(Fingerprint(fresh.GetRawText())!=p.Value.B.Fingerprint)return Report(true,"FAILED_NO_EFFECT_CONFIRMED","STALE_TARGET");
                await Cdp("DOM.setFileInputFiles",new{files=new[]{path},objectId=p.Value.B.ObjectId});
                TransferEvent(new{kind="UPLOAD_ASSIGNED",size,sha256=digest,mime=secrets.Redact(mime)});
                return Report(true,"SUCCEEDED_OBSERVED",null);
            }
            catch{return Report(true,"UNKNOWN",null);}
        }
        finally{busy=false;}
    }
    private void DownloadStarting(object? sender,CoreWebView2DownloadStartingEventArgs e)
    {
        using var deferral=e.GetDeferral();
        e.Handled=true;
        var slot=download;
        try
        {
            guard.Require();
            if(humanPaused||slot is null||slot.Consumed||DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()>=slot.Deadline||e.DownloadOperation.Uri!=slot.Uri||e.DownloadOperation.TotalBytesToReceive is ulong total&&total>(ulong)slot.Limit)
            {
                e.Cancel=true;TransferEvent(new{kind="DOWNLOAD_DENIED",outcome="DENIED_PRE_EFFECT"});
                slot?.Done.TrySetException(new IpcFailure("TRANSFER_INTERRUPTED"));return;
            }
            slot.Consumed=true;slot.Operation=e.DownloadOperation;
            slot.Suggested=SafeName(secrets.Redact(SafeName(e.ResultFilePath)));
            // Preserve the engine's sanitized filename/type for its unchanged
            // FileTypePolicy checks. The random host token, never this name,
            // selects the owned directory; the page cannot select a path.
            string path=Scratch("down",slot.Token,slot.Suggested);Protocol.Need(!File.Exists(path),"TRANSFER_STALE");
            e.ResultFilePath=path;e.Cancel=false; // one pre-authorized exact URI only
            var op=e.DownloadOperation;
            void Check()
            {
                if(op.BytesReceived>slot.Limit||DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()>=slot.Deadline){op.Cancel();slot.Done.TrySetException(new IpcFailure("TRANSFER_INTERRUPTED"));}
                else if(op.State==CoreWebView2DownloadState.Completed)slot.Done.TrySetResult(op);
                else if(op.State==CoreWebView2DownloadState.Interrupted){op.Cancel();slot.Done.TrySetException(new IpcFailure("TRANSFER_INTERRUPTED"));}
            }
            op.BytesReceivedChanged+=(_,_)=>Check();op.StateChanged+=(_,_)=>Check();Check();
            TransferEvent(new{kind="DOWNLOAD_AUTHORIZED",token=slot.Token,total=op.TotalBytesToReceive});
        }
        catch {e.Cancel=true;slot?.Done.TrySetException(new IpcFailure("TRANSFER_INTERRUPTED"));}
        finally{deferral.Complete();}
    }
    public async Task<object> Download(string key,long maxBytes,long deadline,Func<Task> started)
    {
        Ready();Protocol.Need(download is null,"BUSY");busy=true;
        try
        {
            var p=await Proof(key);
            if(p is null||!p.Value.M.GetProperty("caps").EnumerateArray().Any(c=>c.GetString()=="DOWNLOAD"))return DownloadReport(false,"FAILED_NO_EFFECT_CONFIRMED");
            string uri=(await Call(p.Value.B.ObjectId,"function(){return this.href;}" )).GetString()!;
            // V1.2's exact fresh ref and one-use B5 FILE_DOWNLOAD permit, not
            // the legacy offline fixture map, bind the observed candidate.
            // Canonical HTTP(S) is an action validation, never network proof.
            if(productiveV12)ProductiveProtocol.CanonicalTarget(uri);
            else if(!LocalDestination(uri))return DownloadReport(false,"FAILED_NO_EFFECT_CONFIRMED");
            if(maxBytes<=0||maxBytes>transferLimit)return DownloadReport(false,"FAILED_NO_EFFECT_CONFIRMED");
            Invalidate(false);await started();
            download=new DownloadSlot(uri,"wvd_"+Guid.NewGuid().ToString("N"),maxBytes,deadline);
            try
            {
                var r=await Call(p.Value.B.ObjectId,ObservationScripts.Perform,[new{value=new{expected=p.Value.B.Meta,action="CLICK",payload="",destination=(string?)null}}]);
                if(r.TryGetProperty("stale",out _))return DownloadReport(true,"FAILED_NO_EFFECT_CONFIRMED");
                // Reserve only response-delivery time within the existing
                // operation deadline. Never retry or infer completion by size.
                var op=await download.Done.Task.WaitAsync(TimeSpan.FromMilliseconds(Math.Max(1,deadline-DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()-250)));
                string path=Scratch("down",download.Token,download.Suggested);
                using var file=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.Read);
                Protocol.Need(file.Length==op.BytesReceived&&file.Length<=maxBytes,"TRANSFER_INTERRUPTED");
                string digest=Convert.ToHexStringLower(SHA256.HashData(file));
                TransferEvent(new{kind="DOWNLOAD_COMPLETED",state=op.State.ToString(),size=file.Length,sha256=digest});
                return new{kind="download",started=true,outcome="SUCCEEDED_OBSERVED",fileToken=download.Token,size=file.Length,
                    mime=secrets.Redact(op.MimeType),sha256=digest,suggestedName=download.Suggested,origin=Origin(secrets.PublicUrl(view.Source))};
            }
            catch(Exception error)
            {
                TransferEvent(new{kind="DOWNLOAD_UNCONFIRMED",errorType=error.GetType().Name,state=download.Operation?.State.ToString(),bytes=download.Operation?.BytesReceived,total=download.Operation?.TotalBytesToReceive,reason=download.Operation?.InterruptReason.ToString()});
                download.Operation?.Cancel();return DownloadReport(true,"UNKNOWN");
            }
        }
        finally {download?.Operation?.Cancel();download=null;busy=false;}
    }
    private static string SafeName(string name)
    {name=name.Replace('\\','/').Split('/').Last();name=new string(name.Where(c=>!char.IsControl(c)).Select(c=>"<>:\"|?*".Contains(c)?'_':c).ToArray());return string.IsNullOrEmpty(name)||name is "." or ".."?"download":name[..Math.Min(128,name.Length)];}
    private static object DownloadReport(bool started,string outcome)=>new{kind="download",started,outcome,fileToken=(string?)null,size=0,mime=(string?)null,sha256=(string?)null,suggestedName=(string?)null,origin=(string?)null};
    public object TransferMetadata()
    {
        secrets.Require();
        // This closed event union contains fixed status/control metadata plus
        // explicitly classified page/transfer leaves. Re-redact those leaves at
        // publication in case the session learned a value since the event.
        var events=transferEvents.TakeLast(32).Select(record=>
        {
            var node=JsonSerializer.SerializeToNode(record)!.AsObject();
            foreach(string field in new[]{"extension","mime"})
                if(node[field] is not null)node[field]=secrets.Redact(node[field]!.GetValue<string>());
            return node;
        }).ToArray();
        return new{kind="transfer_metadata",humanPaused,events};
    }
    public void StopTransfers(){download?.Operation?.Cancel();Invalidate(false);}
}
