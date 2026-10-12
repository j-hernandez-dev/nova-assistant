# nova-browser-host — Infrastructure IPC skeleton

Active Web V1.1 §35.2 block 01 only. C#/.NET 10, Windows x64, local Named Pipes.
No WebView2 SDK, browser engine, content, DOM, JS, selectors, Policy, grants or tools.

The Python-side API is `BrowserHostClient` in
`local_cli/infrastructure/active_web/browser_host.py`. A future BrowserPort adapter
may own one client. Existing BrowserPort/Core/Application and composition roots
remain unchanged. **Host READY is not Active Web available.**

## Protocol and ownership

See the versioned specification at
`docs/active_web_v1/aw8/webview2_remediation/01_host_ipc/protocol.json`.

Frames: uint32 little-endian byte length + strict UTF-8 JSON; maximum 16,384 bytes.
Only handshake, ping, cancel and shutdown are supported. `reserved_browser` has
no navigation/DOM payload and always returns UNSUPPORTED_COMMAND.

The composition generates a private random pipe name and host-instance/session
IDs. It launches only the explicitly supplied absolute dotnet executable and
`nova-browser-host.dll`, without shell, inherited handles or stdio authority.
The host creates a single, first-instance, remote-client-rejecting pipe, with a
protected DACL: NETWORK denied; actual Windows TokenUser allowed. It verifies
the OS-reported client PID equals its owner PID. Python verifies the OS-reported
server PID equals the child it created, then checks the handshake's host identity,
instance, session, protocol and process correlation. The original owner process
handle remains held; owner exit cancels the host. No arbitrary second client or
automatic reconnect/retry of a sent operation is supported.

These are local ownership controls, **not a sandbox**. HOST_UNISOLATED remains;
they do not promise resistance to administrator/debugger/process injection or
host-file replacement. Assembly/executable paths are trusted host composition,
never model/page fields. The pipe name/IDs are not exposed as model capabilities.

## Deadlines, cancellation and failures

Request deadlines are UTC Unix milliseconds, at most 30 seconds ahead. Python
also enforces a monotonic call budget, including lock wait and frame IO. All
fragments share that budget; frames are not retried. Native startup/handshake
has a five-second bound; after READY the host expires a silent/partial reader
after 30 seconds. No keep-alive/polling task prolongs residency.

An Event can cancel startup/IO; pending Win32 IO is canceled and drained before
freeing its buffers. Faulted channels are closed and their owned process is
reaped; late responses cannot become results. Cleanup has a separate bounded
terminate/kill wait (two seconds each); failure to confirm process exit is
CLEANUP_UNCONFIRMED, not a successful shutdown or rollback.

Health operations complete synchronously. A wire cancel for a previously
completed request returns ALREADY_COMPLETED, never a fabricated rollback.
The client cannot request arbitrary browser effects. Cancellation/STARTED/outcome
mapping for future browser operations belongs to later blocks, not this skeleton.

## Offline build and validation

Requires the **already installed** .NET 10 SDK. There are no PackageReferences,
downloads, workloads or WebView2 installation steps. Build/restore output and
NuGet profiles/temporary state must be outside Git. For example, supply an empty
external feed and absolute external BaseIntermediateOutputPath/OutputPath to:

```text
<absolute dotnet.exe> build native/nova-browser-host/nova-browser-host.csproj
  -c Release --source <empty external feed> -p:NuGetAudit=false
  -p:UseAppHost=false -p:BaseIntermediateOutputPath=<external obj>/
  -p:OutputPath=<external bin>/ --nologo
```

Use process-local private TEMP/TMP, HOME/USERPROFILE, APPDATA/LOCALAPPDATA,
DOTNET_CLI_HOME, NUGET_PACKAGES, telemetry disabled and
MSBuildEnableWorkloadResolver=false. Do not alter global configuration.

Explicit pytest suites live in this native project, **outside the historical CI
inventory**; they are not added to normal Actions by this block:

- `tests/test_ipc_contract.py`: IPC_CONTRACT_TEST, deterministic/doubles.
- `tests/test_host_process.py`: HOST_PROCESS_TEST, actual .NET/Windows pipe.

Run with an absolute configured Python, plugin autoload disabled, no cacheprovider,
`--basetemp` and `--junitxml` outside the repository. No skips/xfails are used to
replace missing Windows/.NET evidence. Native tests fail on an unsupported host.
No test certifies WebView2, network egress, ExternalProtocolGuard or AW8 E2E.
