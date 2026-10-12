using System.ComponentModel;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using System.Security.Principal;
using Microsoft.Win32.SafeHandles;

namespace NovaBrowserHost;

/// <summary>Local, single-owner pipe. Not a host/process sandbox.</summary>
[SupportedOSPlatform("windows")]
internal static class NativePipe
{
    [StructLayout(LayoutKind.Sequential)]
    private struct SecurityAttributes
    {
        public uint Length;
        public IntPtr Descriptor;
        public int Inherit;
    }

    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool ConvertStringSecurityDescriptorToSecurityDescriptorW(
        string text, uint revision, out IntPtr descriptor, out uint size);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern SafePipeHandle CreateNamedPipeW(string name, uint openMode,
        uint pipeMode, uint instances, uint outSize, uint inSize, uint timeout,
        ref SecurityAttributes attributes);

    [DllImport("kernel32.dll")]
    private static extern IntPtr LocalFree(IntPtr memory);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetNamedPipeClientProcessId(SafePipeHandle pipe, out uint pid);

    public static NamedPipeServerStream Create(string name)
    {
        // User SID, not the token's Owner/group SID. Explicit NETWORK deny,
        // protected DACL; no inherited handle. PID binding is an additional gate.
        string sid = WindowsIdentity.GetCurrent().User?.Value ?? throw new IpcFailure("UNAUTHORIZED_CLIENT");
        if (!ConvertStringSecurityDescriptorToSecurityDescriptorW(
            $"D:P(D;;GA;;;NU)(A;;GA;;;{sid})", 1, out var descriptor, out _))
            throw new Win32Exception(Marshal.GetLastWin32Error());
        try
        {
            var attributes = new SecurityAttributes
            {
                Length = (uint)Marshal.SizeOf<SecurityAttributes>(), Descriptor = descriptor, Inherit = 0
            };
            // DUPLEX | OVERLAPPED | FIRST_PIPE_INSTANCE; BYTE | REJECT_REMOTE_CLIENTS.
            var handle = CreateNamedPipeW(@"\\.\pipe\" + name, 0x40080003, 0x8, 1,
                Protocol.MaxFrame, Protocol.MaxFrame, 0, ref attributes);
            if (handle.IsInvalid)
            {
                handle.Dispose();
                throw new Win32Exception(Marshal.GetLastWin32Error());
            }
            try { return new NamedPipeServerStream(PipeDirection.InOut, true, false, handle); }
            catch { handle.Dispose(); throw; }
        }
        finally { LocalFree(descriptor); }
    }

    public static uint ClientPid(NamedPipeServerStream pipe)
    {
        if (!GetNamedPipeClientProcessId(pipe.SafePipeHandle, out uint pid))
            throw new IpcFailure("UNAUTHORIZED_CLIENT");
        return pid;
    }
}
