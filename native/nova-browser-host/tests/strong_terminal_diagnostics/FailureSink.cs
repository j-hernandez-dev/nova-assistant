using System.IO.MemoryMappedFiles;
using System.Runtime.CompilerServices;
using System.Text;
namespace NovaBrowserHost;

// Test-only import, absent from productive build. One selected failure, scalar
// MMF stores only. No CDP taps, writes/Flush per input, waits or authority IPC.
internal static class StrongTerminalFailureSink
{
    private static FileStream? file;
    private static MemoryMappedFile? map;
    private static MemoryMappedViewAccessor? view;
    private static int emitted;
    [ModuleInitializer]
    internal static void Install()
    {
        try
        {
            var args=Environment.GetCommandLineArgs();var options=new Dictionary<string,string>();
            for(int i=1;i+1<args.Length;i++)if(args[i].StartsWith("--",StringComparison.Ordinal))options[args[i]]=args[++i];
            if(!options.TryGetValue("--udf",out var udf)||!options.TryGetValue("--owner-pid",out var owner)||!int.TryParse(owner,out var pid))return;
            file=new FileStream(udf+".strong-terminal-failure.bin",FileMode.CreateNew,FileAccess.ReadWrite,FileShare.ReadWrite|FileShare.Delete);
            file.SetLength(512);map=MemoryMappedFile.CreateFromFile(file,null,512,MemoryMappedFileAccess.ReadWrite,HandleInheritability.None,false);
            view=map.CreateViewAccessor(0,512,MemoryMappedFileAccess.ReadWrite);
            view.Write(0,0x4e564134);view.Write(4,1);view.Write(8,Environment.ProcessId);view.Write(12,pid);
            SensitiveBoundaryFailureDiagnostics.HarnessObserver=Selected;
            AppDomain.CurrentDomain.ProcessExit+=(_,_)=>{view?.Dispose();map?.Dispose();file?.Dispose();};
        }
        catch{}
    }
    private static void Text(int offset,string? text,int maximum)
    {
        var bytes=Encoding.UTF8.GetBytes(text??"");
        if(bytes.Length>maximum)return;
        view!.Write(offset,bytes.Length);view.WriteArray(offset+4,bytes,0,bytes.Length);
    }
    private static void Selected(SensitiveBoundaryFailure f)
    {
        if(view is null||Interlocked.CompareExchange(ref emitted,1,0)!=0)return;
        view.Write(16,(int)f.Reason);view.Write(20,(int)f.Site);view.Write(24,(int?)f.TerminalReason??-1);
        view.Write(32,f.SnapshotRevision??-1);view.Write(40,f.CurrentRevision??-1);
        Text(56,f.CommitCaller,64);Text(128,f.Generation,128);
        view.Write(272,DateTimeOffset.UtcNow.ToUnixTimeMilliseconds());
        Thread.MemoryBarrier();view.Write(28,1);
    }
}
