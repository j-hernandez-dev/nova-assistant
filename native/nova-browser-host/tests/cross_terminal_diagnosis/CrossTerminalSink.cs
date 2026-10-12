using System.Runtime.CompilerServices;
using System.Text.Json;
using NovaBrowserHost;

// Certification harness only. Metadata held in memory and saved AFTER the
// native runner exits its test/lifecycle; never values, URLs, DOM or hashes.
internal static class CrossTerminalSink
{
    private static readonly object Gate=new();
    private static readonly List<object> Rows=[];
    private static readonly Dictionary<string,string> Generations=[],Controls=[];
    private static bool overflow;
    private static long sequence;
    [ModuleInitializer]
    internal static void Install()
    {
        var args=Environment.GetCommandLineArgs();
        if(args.Length!=3||args[1]!="native-cross")return;
        string file=args[2]+".cross-terminal-metadata.json";
        SensitiveTerminalDiagnostics.HarnessObserver=Observe;
        AppDomain.CurrentDomain.ProcessExit+=(_,_)=>
        {
            try{lock(Gate)File.WriteAllText(file,JsonSerializer.Serialize(new{schemaVersion=1,records=Rows,overflow,rawValueRecorded=false,credentialHashRecorded=false}));}
            catch{ } // Delivery gaps are INCONCLUSIVE, not fake success.
        };
    }
    private static string Alias(Dictionary<string,string> map,string key,string prefix)
    {if(!map.TryGetValue(key,out var value)){value=prefix+"_"+(map.Count+1);map.Add(key,value);}return value;}
    private static void Observe(SensitiveTerminalDiagnostic d)
    {
        lock(Gate)
        {
            if(Rows.Count>=1024){overflow=true;return;}
            string generation=Alias(Generations,d.Generation,"document");
            string? control=d.Control is null?null:Alias(Controls,d.Generation+":"+d.Control,"control");
            Rows.Add(new{sequence=++sequence,eventKind=d.Kind.ToString(),documentGeneration=generation,controlOpaqueId=control,
                revision=d.Revision,terminalReason=d.Reason?.ToString(),snapshotLength=d.SnapshotLength,currentLength=d.CurrentLength,
                accepted=d.Accepted,rejectionReason=d.Rejection.ToString()});
        }
    }
}
