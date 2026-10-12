using System.Text.Json;
using Microsoft.Web.WebView2.Core;

namespace NovaBrowserHost;

// Compiled only into Q1 diagnostic derivative. Not a product flag/capability.
internal static class Q1Intervention
{
    private static string Arg(string name)
    {var a=Environment.GetCommandLineArgs();int i=Array.IndexOf(a,name);return i>=0&&i+1<a.Length?a[i+1]:"";}
    internal static void Apply(CoreWebView2 view,string udf)
    {
        using var doc=JsonDocument.Parse(File.ReadAllText(udf+".q1-folder.json"));var c=doc.RootElement;
        if(c.GetProperty("ownerPid").GetInt32()!=int.Parse(Arg("--owner-pid"))||c.GetProperty("hostInstanceRef").GetString()!=Arg("--instance"))throw new InvalidOperationException("Q1_DIAGNOSTIC_OWNER");
        string path=Path.GetFullPath(c.GetProperty("defaultFolder").GetString()!);
        if(!Path.IsPathFullyQualified(path)||path.Length>80||!Directory.Exists(path)||Directory.EnumerateFileSystemEntries(path).Any()||
            path.StartsWith(udf+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase)||
            (File.GetAttributes(path)&FileAttributes.ReparsePoint)!=0)throw new InvalidOperationException("Q1_DIRECTORY_CONTRACT");
        string original=view.Profile.DefaultDownloadFolderPath;
        string profileBefore=view.Profile.ProfileName;
        bool writable=false;
        string marker=Path.Combine(path,"q1-write-"+Guid.NewGuid().ToString("N"));
        using(var f=new FileStream(marker,FileMode.CreateNew,FileAccess.Write,FileShare.None,1,FileOptions.DeleteOnClose))
        {f.WriteByte(0);f.Flush();writable=true;}
        if(Directory.EnumerateFileSystemEntries(path).Any())throw new InvalidOperationException("Q1_DIRECTORY_NOT_EMPTY");
        // The single causal intervention, after product bootstrap assignment
        // and before any content. No UDF/profile/settings/handler change here.
        view.Profile.DefaultDownloadFolderPath=path;
        string getter=view.Profile.DefaultDownloadFolderPath;
        if(Path.GetFullPath(getter)!=path||view.Profile.ProfileName!=profileBefore)throw new InvalidOperationException("Q1_GETTER_OR_PROFILE_CHANGED");
        ContextObserver.Record("Q1_DEFAULT_FOLDER_BEFORE_CONTENT",new{
            udfPath=udf,udfPathLength=udf.Length,
            originalDefaultDownloadFolderPath=original,originalDefaultDownloadFolderPathLength=original.Length,
            q1DefaultDownloadFolderPath=path,q1DefaultDownloadFolderPathLength=path.Length,
            getterAfterSet=getter,directoryExists=Directory.Exists(path),directoryWritable=writable,directoryEmptyAfterWriteProbe=!Directory.EnumerateFileSystemEntries(path).Any(),
            profileNameBefore=profileBefore,profileNameAfter=view.Profile.ProfileName});
    }
}
