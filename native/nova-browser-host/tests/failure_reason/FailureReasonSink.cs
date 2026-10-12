using System.IO.MemoryMappedFiles;
using System.Runtime.CompilerServices;
using System.Text;

namespace NovaBrowserHost;

// Compiled ONLY by the diagnostic harness MSBuild import, not the product.
// Initializes one bounded file mapping before browser startup. A selected fault
// writes scalar metadata to memory, never Flush/file I/O or CDP/event tracing.
internal static class FailureReasonSink
{
    private static FileStream? file;
    private static MemoryMappedFile? mapping;
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
            file=new FileStream(udf+".failure-reason.bin",FileMode.CreateNew,FileAccess.ReadWrite,FileShare.ReadWrite|FileShare.Delete);
            file.SetLength(256);
            mapping=MemoryMappedFile.CreateFromFile(file,null,256,MemoryMappedFileAccess.ReadWrite,HandleInheritability.None,false);
            view=mapping.CreateViewAccessor(0,256,MemoryMappedFileAccess.ReadWrite);
            view.Write(0,0x4e563036);view.Write(4,1);view.Write(8,Environment.ProcessId);view.Write(12,pid);
            SensitiveBoundaryFailureDiagnostics.HarnessObserver=Selected;
            AppDomain.CurrentDomain.ProcessExit+=(_,_)=>{view?.Dispose();mapping?.Dispose();file?.Dispose();};
        }
        catch { } // Missing diagnostic evidence is INCONCLUSIVE, not a decision.
    }

    private static void Selected(SensitiveBoundaryFailure failure)
    {
        if(view is null||Interlocked.CompareExchange(ref emitted,1,0)!=0)return;
        view.Write(16,(int)failure.Reason);view.Write(20,(int)failure.Site);
        view.Write(24,failure.CurrentLength??-1);
        // This key is host-generated Page/context/control identity, never DOM,
        // label, URI or credential. Only SHORT_COMMITTED_VALUE supplies it.
        var control=Encoding.UTF8.GetBytes(failure.OpaqueControl??"");
        if(control.Length<=160){view.Write(28,control.Length);view.WriteArray(40,control,0,control.Length);}
        view.Write(208,DateTimeOffset.UtcNow.ToUnixTimeMilliseconds());
        Thread.MemoryBarrier();view.Write(36,1); // complete record marker LAST
        // No Flush, await, wait, log, callback to page or additional event.
    }
}
