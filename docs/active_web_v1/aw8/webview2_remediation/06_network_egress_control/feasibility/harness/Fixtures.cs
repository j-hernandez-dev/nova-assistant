using System.Collections.Concurrent;
using System.Net;
using System.Net.Quic;
using System.Net.Security;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Text;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.AspNetCore.Server.Kestrel.Core;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

internal sealed class Fixtures:IAsyncDisposable
{
    WebApplication? app,bad;
    readonly ConcurrentQueue<object> records=new();
    readonly ConcurrentDictionary<string,int> counts=new();
    internal readonly X509Certificate2 Certificate=Cert();
    readonly X509Certificate2 badCert=Cert();
    internal int HttpPort,TlsPort,BadPort;
    internal int CredentialAtSite;
    internal string Challenge="";
    static X509Certificate2 Cert()
    {
        using var rsa=RSA.Create(2048);var req=new CertificateRequest("CN="+Probe.A,rsa,HashAlgorithmName.SHA256,RSASignaturePadding.Pkcs1);
        var san=new SubjectAlternativeNameBuilder();foreach(var host in new[]{Probe.A,Probe.B,Probe.C})san.AddDnsName(host);
        req.CertificateExtensions.Add(san.Build());req.CertificateExtensions.Add(new X509BasicConstraintsExtension(false,false,0,true));
        req.CertificateExtensions.Add(new X509KeyUsageExtension(X509KeyUsageFlags.DigitalSignature,true));
        req.CertificateExtensions.Add(new X509EnhancedKeyUsageExtension(new System.Security.Cryptography.OidCollection{new("1.3.6.1.5.5.7.3.1")},true));
        return req.CreateSelfSigned(DateTimeOffset.UtcNow.AddMinutes(-5),DateTimeOffset.UtcNow.AddHours(1));
    }
    internal async Task Start()
    {
        var builder=WebApplication.CreateSlimBuilder();builder.Logging.ClearProviders();
        builder.WebHost.ConfigureKestrel(k=>
        {
            k.Listen(IPAddress.Loopback,0,l=>l.Protocols=HttpProtocols.Http1);
            k.Listen(IPAddress.Loopback,0,l=>{l.Protocols=QuicListener.IsSupported?HttpProtocols.Http1AndHttp2AndHttp3:HttpProtocols.Http1AndHttp2;l.UseHttps(Certificate);});
        });
        app=builder.Build();app.Run(Handle);await app.StartAsync();
        var addresses=app.Services.GetRequiredService<IServer>().Features.Get<IServerAddressesFeature>()!.Addresses.Select(s=>new Uri(s)).ToArray();
        HttpPort=addresses.Single(u=>u.Scheme=="http").Port;TlsPort=addresses.Single(u=>u.Scheme=="https").Port;
        var bb=WebApplication.CreateSlimBuilder();bb.Logging.ClearProviders();bb.WebHost.ConfigureKestrel(k=>k.Listen(IPAddress.Loopback,0,l=>l.UseHttps(badCert)));
        bad=bb.Build();bad.Run(Handle);await bad.StartAsync();
        BadPort=new Uri(bad.Services.GetRequiredService<IServer>().Features.Get<IServerAddressesFeature>()!.Addresses.Single()).Port;
    }
    async Task Handle(HttpContext context)
    {
        var request=context.Request;string path=request.Path;
        counts.AddOrUpdate(path,1,(_,n)=>n+1);
        if(request.Headers.ContainsKey("Authorization")||request.Headers.ContainsKey("Proxy-Authorization"))Interlocked.Increment(ref CredentialAtSite);
        records.Enqueue(new{path,hostRole=request.Host.Host switch{Probe.A=>"A",Probe.B=>"B",Probe.C=>"C",_=>"OTHER"},protocol=request.Protocol,connectionRef=Probe.Hash(Encoding.UTF8.GetBytes(context.Connection.Id))[..16],ms=Environment.TickCount64});
        context.Response.Headers.CacheControl="no-store";context.Response.Headers.AccessControlAllowOrigin="*";
        if(path=="/redirect"){context.Response.StatusCode=302;context.Response.Headers.Location="https://"+Probe.C+"/denied-redirect";return;}
        if(path=="/auth-trap"){context.Response.StatusCode=401;context.Response.Headers.WWWAuthenticate=Challenge;return;}
        if(path=="/alt-svc")context.Response.Headers.AltSvc="h3=\":"+TlsPort+"\"; ma=60";
        string data=path switch
        {
            "/index" or "/alt-svc"=>"<!doctype html><title>Controlled native feasibility</title><p>Offline fixture</p>",
            "/sw.js"=>Scripts.Sw,
            "/sw-import.js"=>"self.importWasExecuted=true;",
            "/worker-executed" or "/worker-fetch"=>"Controlled worker response",
            "/pixel"=>"not-an-image",
            _=>"controlled response"
        };
        context.Response.ContentType=path.EndsWith(".js")?"application/javascript":path is "/index" or "/alt-svc"?"text/html":"text/plain";
        await context.Response.WriteAsync(data);
    }
    internal object Snapshot()=>new{counts=counts.OrderBy(p=>p.Key).ToDictionary(p=>p.Key,p=>p.Value),requests=records.ToArray(),http3EndpointCapable=QuicListener.IsSupported,credentialAtSite=CredentialAtSite};
    public async ValueTask DisposeAsync(){if(app is not null){await app.StopAsync();await app.DisposeAsync();}if(bad is not null){await bad.StopAsync();await bad.DisposeAsync();}Certificate.Dispose();badCert.Dispose();}
}

internal sealed class HarnessBroker:IDisposable
{
    readonly TcpListener listener;
    readonly CancellationTokenSource stop=new();
    readonly ConcurrentBag<TcpClient> clients=new();
    readonly ConcurrentBag<Task> tasks=new();
    readonly ConcurrentQueue<object> trace=new();
    readonly Fixtures fixture;
    internal readonly string User="ephemeral-"+Guid.NewGuid().ToString("N"),Password=Convert.ToHexString(RandomNumberGenerator.GetBytes(32));
    internal readonly string Challenge="Basic realm=\"nova-proxy-"+Guid.NewGuid().ToString("N")+"\"";
    internal int Port;
    internal HarnessBroker(Fixtures fixture)
    {this.fixture=fixture;var reserve=new TcpListener(IPAddress.Loopback,0);reserve.Start();Port=((IPEndPoint)reserve.LocalEndpoint).Port;reserve.Stop();listener=new TcpListener(IPAddress.Loopback,Port);fixture.Challenge=Challenge;}
    internal void Start(){listener.Start();tasks.Add(Accept());}
    async Task Accept()
    {try{while(!stop.IsCancellationRequested){var c=await listener.AcceptTcpClientAsync(stop.Token);clients.Add(c);tasks.Add(Serve(c));}}catch(Exception e)when(e is OperationCanceledException or SocketException or ObjectDisposedException){}}
    static async Task<string?> Head(Stream stream,CancellationToken token)
    {
        var data=new List<byte>();byte[] one=new byte[1];
        while(data.Count<32768){int n=await stream.ReadAsync(one,token);if(n==0)return null;data.Add(one[0]);int k=data.Count;if(k>=4&&data[k-4]==13&&data[k-3]==10&&data[k-2]==13&&data[k-1]==10)return Encoding.ASCII.GetString(data.ToArray());}throw new InvalidOperationException("BOUNDED_HEADER");
    }
    async Task Serve(TcpClient c)
    {
        using(c)
        try
        {
            using var deadline=CancellationTokenSource.CreateLinkedTokenSource(stop.Token);deadline.CancelAfter(TimeSpan.FromSeconds(35));
            var stream=c.GetStream();string? head=await Head(stream,deadline.Token);if(head is null)return;
            var lines=head.Split("\r\n");var first=lines[0].Split(' ');
            var headers=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);
            foreach(var line in lines.Skip(1).Where(l=>l.Contains(':'))){int p=line.IndexOf(':');headers[line[..p]]=line[(p+1)..].Trim();}
            string auth="Basic "+Convert.ToBase64String(Encoding.UTF8.GetBytes(User+":"+Password));
            if(!headers.TryGetValue("Proxy-Authorization",out var incoming)||!CryptographicOperations.FixedTimeEquals(Encoding.UTF8.GetBytes(incoming),Encoding.UTF8.GetBytes(auth)))
            {trace.Enqueue(new{kind="AUTH_REQUIRED",ms=Environment.TickCount64});await stream.WriteAsync(Encoding.ASCII.GetBytes("HTTP/1.1 407 Proxy Authentication Required\r\nProxy-Authenticate: "+Challenge+"\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"),deadline.Token);return;}
            string method=first[0],target=first[1];bool connect=method=="CONNECT";
            var uri=new Uri(connect?"https://"+target:target);
            bool permitted=uri.Host is Probe.A or Probe.B or Probe.C or "bad.nova-fixture.test";
            trace.Enqueue(new{kind=permitted?"HARNESS_ADMITTED":"DESTINATION_DENIED",method,hostRole=uri.Host switch{Probe.A=>"A",Probe.B=>"B",Probe.C=>"C","bad.nova-fixture.test"=>"BAD_TLS",_=>"FORBIDDEN"},dnsResolution=permitted?"HARNESS_SYNTHETIC_PUBLIC_TO_LOCAL_TRANSPORT":"NO_RESOLUTION_PRIVATE_DENIED",ms=Environment.TickCount64});
            if(!permitted){await stream.WriteAsync("HTTP/1.1 403 Destination Denied\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"u8.ToArray(),deadline.Token);return;}
            using var upstream=new TcpClient();clients.Add(upstream);await upstream.ConnectAsync(IPAddress.Loopback,connect?uri.Host=="bad.nova-fixture.test"?fixture.BadPort:fixture.TlsPort:fixture.HttpPort,deadline.Token);
            using var us=upstream.GetStream();
            if(connect)
            {
                await stream.WriteAsync("HTTP/1.1 200 Connection Established\r\n\r\n"u8.ToArray(),deadline.Token);
                var outTask=stream.CopyToAsync(us,deadline.Token);var inTask=us.CopyToAsync(stream,deadline.Token);
                await Task.WhenAny(outTask,inTask);deadline.Cancel();
                try{await Task.WhenAll(outTask,inTask);}catch(Exception e)when(e is OperationCanceledException or IOException or SocketException){}
            }
            else
            {
                string filtered=string.Join("\r\n",headers.Where(h=>!h.Key.StartsWith("Proxy-",StringComparison.OrdinalIgnoreCase)&&!h.Key.Equals("Connection",StringComparison.OrdinalIgnoreCase)).Select(h=>h.Key+": "+h.Value));
                await us.WriteAsync(Encoding.ASCII.GetBytes(method+" "+uri.PathAndQuery+" HTTP/1.1\r\n"+filtered+"\r\nConnection: close\r\n\r\n"),deadline.Token);
                await us.CopyToAsync(stream,deadline.Token);
            }
        }
        catch(Exception e)when(e is IOException or SocketException or OperationCanceledException or ObjectDisposedException){trace.Enqueue(new{kind="SOCKET_ENDED",type=e.GetType().Name,ms=Environment.TickCount64});}
    }
    internal object Snapshot()=>new{events=trace.ToArray(),listenerRole="OWNED_PROXY_ONLY",proxyPort=Port,credentialsRecorded=false,mitm=false,syntheticTopology=true};
    internal void Stop(){stop.Cancel();listener.Stop();foreach(var c in clients)c.Dispose();}
    public void Dispose(){Stop();try{Task.WhenAll(tasks).Wait(TimeSpan.FromSeconds(5));}catch(AggregateException){}stop.Dispose();}
}

internal sealed class TcpCanary:IDisposable
{
    readonly TcpListener listener;readonly CancellationTokenSource stop=new();readonly Task worker;
    int count;internal readonly int Port;internal bool Calibrated;internal int Unexpected=>Math.Max(0,count-1);
    internal TcpCanary(IPAddress address){listener=new(address,0);listener.Start();Port=((IPEndPoint)listener.LocalEndpoint).Port;worker=Run();}
    async Task Run(){try{while(!stop.IsCancellationRequested){using var c=await listener.AcceptTcpClientAsync(stop.Token);Interlocked.Increment(ref count);}}catch(Exception e)when(e is OperationCanceledException or SocketException or ObjectDisposedException){}}
    internal async Task Calibrate(){using var c=new TcpClient(listener.Server.AddressFamily);await c.ConnectAsync(((IPEndPoint)listener.LocalEndpoint).Address,Port);var end=Environment.TickCount64+1000;while(count==0&&Environment.TickCount64<end)await Task.Yield();Calibrated=count==1;}
    public void Dispose(){stop.Cancel();listener.Stop();try{worker.Wait(TimeSpan.FromSeconds(1));}catch(AggregateException){}stop.Dispose();}
}
internal sealed class UdpCanary:IDisposable
{
    internal readonly ConcurrentQueue<object> Packets=new();
    readonly UdpClient socket=new(new IPEndPoint(IPAddress.Loopback,0));readonly CancellationTokenSource stop=new();readonly Task worker;
    int count;internal readonly int Port;internal bool Calibrated;internal int Unexpected=>Math.Max(0,count-1);
    internal UdpCanary(){Port=((IPEndPoint)socket.Client.LocalEndPoint!).Port;worker=Run();}
    async Task Run(){try{while(!stop.IsCancellationRequested){var packet=await socket.ReceiveAsync(stop.Token);int n=Interlocked.Increment(ref count);bool stun=packet.Buffer.Length>=20&&packet.Buffer[4]==0x21&&packet.Buffer[5]==0x12&&packet.Buffer[6]==0xa4&&packet.Buffer[7]==0x42;Packets.Enqueue(new{sequence=n,sourcePort=packet.RemoteEndPoint.Port,bytes=packet.Buffer.Length,isStun=stun,ms=Environment.TickCount64});}}catch(Exception e)when(e is OperationCanceledException or SocketException or ObjectDisposedException){}}
    internal async Task Calibrate(){using var c=new UdpClient();await c.SendAsync("calibration"u8.ToArray(),new IPEndPoint(IPAddress.Loopback,Port));var end=Environment.TickCount64+1000;while(count==0&&Environment.TickCount64<end)await Task.Yield();Calibrated=count==1;}
    public void Dispose(){stop.Cancel();socket.Dispose();try{worker.Wait(TimeSpan.FromSeconds(1));}catch(AggregateException){}stop.Dispose();}
}
