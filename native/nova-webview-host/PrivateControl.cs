using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace NovaWebViewHost;

// Private lifecycle, visibility and one-shot download control. DOM actions stay in Playwright.
internal sealed record ControlCommand(string Command, string? Url = null, string? Path = null,
    string? Operation = null, long MaxBytes = 0, int TimeoutMs = 0);
internal static class PrivateControl
{
    internal const int MaxFrameBytes = 16 * 1024;

    internal static async Task ReadAsync(string token, Action start, Action<string> stop,
        Func<ControlCommand, Task<object>> control, CancellationToken cancellation)
    {
        bool started = false;
        using Stream input = Console.OpenStandardInput();
        byte[] buffer = new byte[4096];
        using var frame = new MemoryStream();
        try
        {
            while (true)
            {
                int count = await input.ReadAsync(buffer, cancellation);
                if (count == 0) { stop("stdin-eof"); return; }
                for (int i = 0; i < count; i++)
                {
                    if (buffer[i] != (byte)'\n')
                    {
                        if (frame.Length >= MaxFrameBytes) throw new InvalidDataException("Control frame is too large.");
                        frame.WriteByte(buffer[i]);
                        continue;
                    }
                    ControlCommand request = Parse(frame.ToArray(), token);
                    string command = request.Command;
                    frame.SetLength(0);
                    if (command == "start" && !started)
                    {
                        started = true;
                        start();
                    }
                    else if (command == "shutdown" && started) { stop("shutdown"); return; }
                    else if (started && command is "show" or "hide" or "download-arm" or "download-status" or "download-cancel")
                        await WriteAsync(await control(request));
                    else throw new InvalidDataException("Unexpected control command.");
                }
            }
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (Exception e) when (e is IOException or JsonException or InvalidDataException or InvalidOperationException or ArgumentException)
        {
            Console.Error.WriteLine("Invalid private control input: " + e.Message);
            stop("invalid-control");
        }
    }

    private static ControlCommand Parse(byte[] frame, string token)
    {
        using var document = JsonDocument.Parse(frame, new JsonDocumentOptions { MaxDepth = 4 });
        var root = document.RootElement;
        if (root.ValueKind != JsonValueKind.Object) throw new InvalidDataException("Expected a control object.");
        var fields = root.EnumerateObject().ToArray();
        if (fields.Select(p => p.Name).Distinct().Count() != fields.Length || fields.Count(p => p.NameEquals("command")) != 1 ||
            fields.Count(p => p.NameEquals("token")) != 1 ||
            !root.TryGetProperty("command", out var command) || command.ValueKind != JsonValueKind.String ||
            !root.TryGetProperty("token", out var credential) || credential.ValueKind != JsonValueKind.String ||
            !CryptographicOperations.FixedTimeEquals(Encoding.UTF8.GetBytes(credential.GetString()!), Encoding.UTF8.GetBytes(token)))
            throw new InvalidDataException("Invalid control credentials or fields.");
        string name = command.GetString()!;
        string[] allowed = name == "download-arm" ? ["command", "token", "url", "path", "operation", "maxBytes", "timeoutMs"] :
            name is "download-status" or "download-cancel" ? ["command", "token", "operation"] : ["command", "token"];
        if (fields.Length != allowed.Length || fields.Any(p => !allowed.Contains(p.Name)))
            throw new InvalidDataException("Invalid control fields.");
        if (name == "download-arm")
            return new(name, root.GetProperty("url").GetString(), root.GetProperty("path").GetString(),
                root.GetProperty("operation").GetString(), root.GetProperty("maxBytes").GetInt64(), root.GetProperty("timeoutMs").GetInt32());
        return new(name, Operation: name is "download-status" or "download-cancel" ? root.GetProperty("operation").GetString() : null);
    }

    internal static async Task WriteAsync(object receipt)
    {
        byte[] frame = JsonSerializer.SerializeToUtf8Bytes(receipt);
        if (frame.Length > MaxFrameBytes) throw new InvalidDataException("Host receipt is too large.");
        Stream output = Console.OpenStandardOutput();
        await output.WriteAsync(frame);
        await output.WriteAsync(new byte[] { (byte)'\n' });
        await output.FlushAsync();
    }
}
