using NovaBrowserHost;
// Certification-only outer wrapper; linked product source is unchanged.
// This is diagnostic evidence, NEVER the final product test executable.
var options=new Dictionary<string,string>();
for(int i=0;i<args.Length;i+=2)options.Add(args[i],args[i+1]);
try{return await LifecycleServer.Run(options);}
catch(Exception e)
{
    var methods=new System.Diagnostics.StackTrace(e,true).GetFrames().Select(f=>f.GetMethod()?.DeclaringType?.Name+"."+f.GetMethod()?.Name+":line="+f.GetFileLineNumber());
    File.WriteAllLines(options["--udf"]+".safe-exception.txt",new[]{e.GetType().Name}.Concat(methods));
    return 16;
}
