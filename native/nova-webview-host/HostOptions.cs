using System.Globalization;

namespace NovaWebViewHost;

internal sealed record HostOptions(string RuntimeDirectory, string ProfileDirectory, int OwnerPid, string Token)
{
    internal string BrowserExecutable => Path.Combine(RuntimeDirectory, "msedgewebview2.exe");

    internal static HostOptions Parse(string[] args)
    {
        var fields = new Dictionary<string, string>(StringComparer.Ordinal);
        if (args.Length != 8) throw new ArgumentException("Expected the four private launcher options.");
        for (int i = 0; i < args.Length; i += 2)
        {
            if (args[i] is not ("--runtime-directory" or "--user-data-directory" or "--owner-pid" or "--token") ||
                !fields.TryAdd(args[i], args[i + 1]))
                throw new ArgumentException("Invalid or duplicate launcher option.");
        }

        string runtime = Path.GetFullPath(fields["--runtime-directory"]);
        string profile = Path.GetFullPath(fields["--user-data-directory"]);
        if (!Directory.Exists(runtime) || !File.Exists(Path.Combine(runtime, "msedgewebview2.exe")))
            throw new ArgumentException("The bundled Fixed Version runtime is missing.");
        if (Directory.Exists(profile) || File.Exists(profile) ||
            Path.GetDirectoryName(profile) is not { } parent || !Directory.Exists(parent))
            throw new ArgumentException("The profile must be a new directory under an existing parent.");
        if (!int.TryParse(fields["--owner-pid"], NumberStyles.None, CultureInfo.InvariantCulture, out int owner) ||
            owner <= 0 || owner == Environment.ProcessId)
            throw new ArgumentException("Invalid owner process.");
        string token = fields["--token"];
        if (token.Length is < 16 or > 256 || token.Any(c => !char.IsAsciiLetterOrDigit(c) && c is not ('-' or '_')))
            throw new ArgumentException("Invalid private control token.");
        if (!Console.IsInputRedirected || !Console.IsOutputRedirected)
            throw new ArgumentException("The host requires redirected private stdin and stdout.");
        return new HostOptions(runtime, profile, owner, token);
    }
}
