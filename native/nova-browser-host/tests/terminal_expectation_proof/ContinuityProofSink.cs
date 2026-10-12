using System.IO.MemoryMappedFiles;
using System.Runtime.CompilerServices;
using System.Text;
namespace NovaBrowserHost;

// Test-only observer of existing scalar diagnostics: no input/CDP taps,
// raw material, authority, product flag or public IPC change.
internal static class ContinuityProofSink
{
    private const int Header=256,Record=128,Limit=64;
    private sealed class Entry(string generation,string control)
    {internal string Generation=generation,Control=control;internal long Revision;internal int Length,Terminals,Commits,Retired;}
    private static readonly Dictionary<(string,string),Entry> entries=[];
    private static MemoryMappedViewAccessor? view;
    private static MemoryMappedFile? map;
    private static FileStream? file;
    [ModuleInitializer]
    internal static void Install()
    {
        var args=Environment.GetCommandLineArgs();string? udf=null;int owner=0;
        for(int i=1;i+1<args.Length;i++)
        {if(args[i]=="--udf")udf=args[i+1];if(args[i]=="--owner-pid")int.TryParse(args[i+1],out owner);}
        if(udf is null||owner<=0)return;
        file=new(udf+".continuity-proof.bin",FileMode.CreateNew,FileAccess.ReadWrite,FileShare.ReadWrite|FileShare.Delete);
        file.SetLength(Header+Record*Limit);
        map=MemoryMappedFile.CreateFromFile(file,null,Header+Record*Limit,MemoryMappedFileAccess.ReadWrite,HandleInheritability.None,false);
        view=map.CreateViewAccessor(0,Header+Record*Limit,MemoryMappedFileAccess.ReadWrite);
        view.Write(0,0x4e564135);view.Write(4,1);view.Write(8,Environment.ProcessId);view.Write(12,owner);
        SensitiveTerminalDiagnostics.HarnessObserver=Observed;
        SensitiveBoundaryFailureDiagnostics.HarnessObserver=Failure;
        AppDomain.CurrentDomain.ProcessExit+=(_,_)=>{view?.Dispose();map?.Dispose();file?.Dispose();};
    }
    private static void Text(int at,string? value,int maximum)
    {
        var bytes=Encoding.UTF8.GetBytes(value??"");
        if(bytes.Length>maximum){view!.Write(164,1);return;}
        view!.WriteArray(at,bytes,0,bytes.Length);
    }
    private static void Observed(SensitiveTerminalDiagnostic data)
    {
        if(view is null||data.Control is null)return;
        var key=(data.Generation,data.Control);
        if(!entries.TryGetValue(key,out var entry))
        {if(entries.Count>=Limit){view.Write(164,1);return;}entry=new(data.Generation,data.Control);entries.Add(key,entry);}
        if(data.Kind==SensitiveTerminalDiagnosticKind.TERMINAL_CREATED)entry.Terminals++;
        if(data.Kind==SensitiveTerminalDiagnosticKind.COMMIT_ACCEPTED)entry.Commits++;
        if(data.Kind==SensitiveTerminalDiagnosticKind.RETIRE_CONTROL)
        {entry.Retired++;entry.Revision=data.Revision??0;entry.Length=data.CurrentLength??0;}
        int index=0;
        foreach(var item in entries.Values)
        {
            int at=Header+index++*Record;Text(at,item.Generation,32);Text(at+32,item.Control,64);
            view.Write(at+96,item.Revision);view.Write(at+104,item.Length);
            view.Write(at+108,item.Terminals);view.Write(at+112,item.Commits);view.Write(at+116,item.Retired);
        }
        Thread.MemoryBarrier();view.Write(160,entries.Count);
    }
    private static void Failure(SensitiveBoundaryFailure data)
    {
        if(view is null||view.ReadInt32(168)!=0)return;
        view.Write(16,(int)data.Reason);Text(20,data.Generation,32);Text(64,data.OpaqueControl,64);
        view.Write(128,data.CurrentRevision??-1);view.Write(136,(int?)data.TerminalReason??-1);
        Thread.MemoryBarrier();view.Write(168,1);
    }
}
