using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;

// Certification-only native UI driver. No connection to Nova model/IPC. The
// secret exists only in memory: no CLI argument, file, raw stdout or receipt.
if(args.Length!=2||!uint.TryParse(args[0],out uint pid))return 2;
IntPtr form=IntPtr.Zero;
Win.EnumWindows((h,_)=>{Win.GetWindowThreadProcessId(h,out uint p);if(p==pid&&Win.IsWindowVisible(h))form=h;return true;},IntPtr.Zero);
if(form==IntPtr.Zero)return 3;
var children=new List<IntPtr>();Win.EnumChildWindows(form,(h,_)=>{children.Add(h);return true;},IntPtr.Zero);
if(args[1]=="done")
{
    foreach(var h in children){var text=new StringBuilder(256);Win.GetWindowText(h,text,256);if(text.ToString()=="Return control to Nova"){Win.SendMessage(h,0xf5,IntPtr.Zero,IntPtr.Zero);Console.WriteLine("HOST_UI_COMPLETE:PASS");return 0;}}
    return 4;
}
string secret="test-only-"+Convert.ToHexStringLower(RandomNumberGenerator.GetBytes(16));
int y=args[1]=="external"?142:20;
foreach(var h in children)
{
    Win.SendMessage(h,0x200,IntPtr.Zero,new IntPtr(30|(y<<16)));
    Win.SendMessage(h,0x201,new IntPtr(1),new IntPtr(30|(y<<16)));
    Win.SendMessage(h,0x202,IntPtr.Zero,new IntPtr(30|(y<<16)));
    if(args[1]=="sensitive")foreach(char c in secret)Win.SendMessage(h,0x102,new IntPtr(c),IntPtr.Zero);
}
Console.WriteLine(args[1]=="sensitive"?"SECRET_SHA256:"+Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(secret))):"NATIVE_EXTERNAL_GESTURE_SENT:PASS");
return 0;
static class Win
{
    public delegate bool EnumProc(IntPtr h,IntPtr value);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc proc,IntPtr value);
    [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr h,EnumProc proc,IntPtr value);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h,out uint pid);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll",CharSet=CharSet.Unicode)]public static extern int GetWindowText(IntPtr h,StringBuilder text,int count);
    [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h,uint message,IntPtr w,IntPtr l);
}
