# Nova WebView2 host

Windows x64 lifetime host for the bundled WebView2 Fixed Version runtime.
Playwright connects through CDP and performs page operations. The host has no
page action, evaluation, model, Policy, or historical protocol implementation.

Publish with the .NET 10 SDK:

```powershell
dotnet publish native/nova-webview-host/nova-webview-host.csproj -c Release -r win-x64 --self-contained true -o build/browser/host
```

Distribute the **whole publish directory**, including its .NET runtime and
WebView2 loader, alongside the separately bundled WebView2 Fixed Version
directory. End users do not need a .NET installation.

The private launcher supplies four required options:

```text
--runtime-directory <fixed-version-folder-containing-msedgewebview2.exe>
--user-data-directory <new-profile-path-under-an-existing-parent>
--owner-pid <launcher-process-id>
--token <random-alphanumeric-or-base64url-token>
```

The profile path must not exist. The host creates it; the launcher deletes it
after all owned processes exit. The launcher redirects stdin/stdout and assigns
the host to its Windows Job before sending `{"command":"start","token":"..."}`.
The start deadline is 15 seconds. WebView2 is never created before that message.

Stdout contains UTF-8 JSON lines only, with a 16 KiB frame limit. Successful
startup emits one `ready` object containing `token`, `hostPid`, `browserPid`,
`runtimeVersion`, `runtimeDirectory`, `browserExecutable`, `cdpEndpoint`, and
`profileDirectory`. The executable is checked against the explicit runtime
directory; installed Evergreen runtimes are not used as a fallback. The CDP
endpoint uses loopback and an ephemeral port.

The only subsequent command is `{"command":"shutdown","token":"..."}`.
After closing the controller and waiting for the browser process, the host emits
`closed` with `token`, `hostPid`, `browserPid`, `reason`, and `browserExited`.
Owner exit or stdin EOF also closes the host. Diagnostics go to stderr; exit
code 2 reports invalid control/startup/process failure and 3 reports unconfirmed
cleanup. The launcher retains responsibility for its Job and profile cleanup.

The initial page is `about:blank` in a hidden owned window. External application
launches are canceled, and site permissions are denied by default. This initial
host does not provide a human browser window or a site permission prompt.
Downloads are canceled until owned transfer support is implemented in Block 5.
