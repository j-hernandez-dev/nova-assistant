using System.Text;
using Microsoft.Web.WebView2.Core;
namespace NovaBrowserHost;

// Diagnostic derivative only. Core response algorithm is microprobe A,
// not a productive resource provider or a future network boundary.
internal static class BisectionProvider
{
    private const string Origin="https://nova-local.invalid";
    private static readonly byte[] Payload=Encoding.UTF8.GetBytes("Local approved download cobalt-631.");
    private const string Html="""
<!doctype html><html><head><title>Local transfer specimen</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'">
<style>body{margin:10px}a{display:block;height:28px;margin:6px 0}</style></head><body>
<a id="download" href="/download.txt" download="../../untrusted-name.txt">Approved specimen download</a>
</body></html>
""";
    internal static void Attach(CoreWebView2 view)
    {
        if(Payload.Length!=35)throw new InvalidOperationException("PAYLOAD_CONTRACT");
        view.AddWebResourceRequestedFilter(Origin+"/*",CoreWebView2WebResourceContext.All);
        view.WebResourceRequested+=(_,e)=>
        {
            bool target=e.Request.Uri==Origin+"/download.txt",index=e.Request.Uri==Origin+"/index.html";
            ContextObserver.ResourceStart(e.Request.Uri);
            byte[] data=target?Payload:index?Encoding.UTF8.GetBytes(Html):[];
            string mime=target?"text/plain":index?"text/html":"application/octet-stream";
            string headers="Content-Type: "+mime+"\r\nContent-Length: "+data.Length+"\r\nCache-Control: no-store\r\n";
            var stream=new MemoryStream(data,false);
            e.Response=view.Environment.CreateWebResourceResponse(stream,target||index?200:404,target||index?"OK":"Not Found",headers);
            ContextObserver.ResourceDone(target?"download.txt":"index.html",target||index?200:404,data.Length);
        };
    }
}
