$ErrorActionPreference = 'Stop'
$output = 'C:\NovaOutput'
$root = 'C:\Nova QA'
$install = Join-Path $root 'App'
$result = [ordered]@{schema='NOVA_WINDOWS_INSTALL_SMOKE_V1';status='FAIL';checks=@();externalModelInference=$false}
$application = $null
$socket = $null
$script:serial = 0
function Check($name, $condition) {
    if (-not $condition) { throw ('Check failed: ' + $name) }
    $result.checks += $name
    @{phase=$name} | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath "$output\phase.json"
}
function Run-Owned($file, $arguments, $label, $timeout=120000) {
    $process = Start-Process -FilePath $file -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput "$root\$label.stdout.log" -RedirectStandardError "$root\$label.stderr.log"
    if (-not $process.WaitForExit($timeout)) { Stop-Process -Id $process.Id; throw ($label + ' timed out') }
    $process.Refresh()
    Check ($label + ' exits successfully') ($process.ExitCode -eq 0)
}
function Cdp($method, $parameters) {
    $script:serial++
    $message = @{id=$script:serial;method=$method;params=$parameters} | ConvertTo-Json -Compress -Depth 20
    $bytes = [Text.Encoding]::UTF8.GetBytes($message)
    $cancellation = New-Object Threading.CancellationTokenSource(30000)
    try {
        $socket.SendAsync([ArraySegment[byte]]::new($bytes),[Net.WebSockets.WebSocketMessageType]::Text,$true,$cancellation.Token).GetAwaiter().GetResult() | Out-Null
        do {
            $stream = New-Object IO.MemoryStream
            do {
                $buffer = New-Object byte[] 65536
                $received = $socket.ReceiveAsync([ArraySegment[byte]]::new($buffer),$cancellation.Token).GetAwaiter().GetResult()
                $stream.Write($buffer,0,$received.Count)
            } until ($received.EndOfMessage)
            $frame = [Text.Encoding]::UTF8.GetString($stream.ToArray()) | ConvertFrom-Json
            $stream.Dispose()
        } until ($frame.id -eq $script:serial)
        if ($frame.error) { throw ('CDP failed: ' + $method) }
        return $frame.result
    } finally { $cancellation.Dispose() }
}
function Eval($expression) {
    $value = Cdp 'Runtime.evaluate' @{expression=$expression;returnByValue=$true;awaitPromise=$true}
    if ($value.exceptionDetails) { throw 'Renderer evaluation failed' }
    return $value.result.value
}
function Wait-Renderer($expression) {
    for($attempt=0;$attempt -lt 90;$attempt++) {
        if (Eval $expression) { return }
        Start-Sleep -Milliseconds 500
    }
    throw ('Renderer state not observed: ' + $expression)
}
try {
    New-Item -ItemType Directory -Path $root | Out-Null
    # No Python, Node, .NET SDK or developer tools are supplied to the application.
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot;$env:SystemRoot\System32\WindowsPowerShell\v1.0"
    Remove-Item Env:PYTHONPATH,Env:PYTHONHOME,Env:VIRTUAL_ENV,Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue
    $env:LOCAL_CLI_STATE_DIR = "$root\UserState"
    $source = Get-ChildItem -LiteralPath 'C:\NovaInput' -Filter '*-windows-x64-setup.exe' -File
    Check 'one installer supplied' (@($source).Count -eq 1)
    $expected = Get-Content -Raw -LiteralPath 'C:\NovaInput\installer.sha256'
    Check 'installer SHA256 matches host build' ((Get-FileHash -Algorithm SHA256 -LiteralPath $source.FullName).Hash -eq $expected.Trim())
    Check 'no developer Python or Node on PATH' (-not (Get-Command python.exe,node.exe,dotnet.exe -ErrorAction SilentlyContinue))
    $localInstaller = Join-Path $root 'NovaSetup.exe'
    Copy-Item -LiteralPath $source.FullName -Destination $localInstaller
    Check 'local installer copy preserves SHA256' ((Get-FileHash -Algorithm SHA256 -LiteralPath $localInstaller).Hash -eq $expected.Trim())
    Run-Owned $localInstaller @('/S',('/D=' + $install)) 'install'
    $appExe = Join-Path $install 'Nova.exe'
    $backend = Join-Path $install 'resources\backend\nova-backend.exe'
    Check 'installed Electron and frozen backend exist' ((Test-Path -LiteralPath $appExe) -and (Test-Path -LiteralPath $backend))
    Run-Owned $backend @('--runtime-info') 'runtime'
    $runtime = Get-Content -Raw -LiteralPath "$root\runtime.stdout.log" | ConvertFrom-Json
    Check 'bundled Python, NumPy, PDF and SQLite work without an interpreter installation' ($runtime.status -eq 'PASS' -and $runtime.frozen -and $runtime.pdfRoundTrip -and $runtime.numpyNativeMath -and $runtime.sqlite -and $runtime.browserPresent)
    $result.runtime = $runtime
    Run-Owned $backend @('--check-browser') 'browser'
    $browser = Get-Content -Raw -LiteralPath "$root\browser.stdout.log" | ConvertFrom-Json
    Check 'packaged WebView2 navigates and edits only its owned loopback fixture' ($browser.status -eq 'PASS' -and $browser.ownedLoopbackNavigation -and $browser.formRoundTrip -and $browser.profileRemoved -and $browser.jobEmpty -and $browser.hostExited)
    $result.browser = $browser
    $application = Start-Process -FilePath $appExe -ArgumentList @('--remote-debugging-port=9317','--remote-debugging-address=127.0.0.1') -PassThru -RedirectStandardOutput "$root\app.stdout.log" -RedirectStandardError "$root\app.stderr.log"
    $target = $null
    for($attempt=0;$attempt -lt 90;$attempt++) {
        try { $target = @(Invoke-RestMethod -Uri 'http://127.0.0.1:9317/json/list' -TimeoutSec 2 | Where-Object type -eq 'page')[0] } catch {}
        if ($target.webSocketDebuggerUrl) { break }
        Start-Sleep -Milliseconds 500
    }
    Check 'installed application renderer starts' ([bool]$target.webSocketDebuggerUrl)
    $socket = New-Object Net.WebSockets.ClientWebSocket
    $socket.ConnectAsync([Uri]$target.webSocketDebuggerUrl,[Threading.CancellationToken]::None).GetAwaiter().GetResult()
    Wait-Renderer '!!window.api && !document.getElementById("nova-startup")'
    Eval 'window.api.onSessionView(v=>window.__installView=v);window.api.signalReady();true' | Out-Null
    Wait-Renderer '!!window.__installView?.sessionId && window.__installView.status.connected'
    Check 'real frozen backend exchanges JSONL with Electron' (Eval '!!window.__installView.sessionId && window.__installView.status.connected')
    $version = Eval 'window.api.getAppVersion()'
    Check 'installed version matches release' ($version -eq '0.13.0')
    $result.version = $version
    $projects = Eval 'window.api.getProjects()'
    $documents = [Environment]::GetFolderPath('MyDocuments')
    Check 'default workspace uses writable documents outside installation' ($projects.defaultPath -eq "$documents\Nova\workspace")
    Check 'no Python interpreter process is needed' (-not (Get-Process -Name python,pythonw -ErrorAction SilentlyContinue))
    Check 'frozen backend process is alive' ([bool](Get-Process -Name nova-backend -ErrorAction SilentlyContinue))
    Check 'preferences can be saved through production IPC' (Eval '(async()=>{const r=await window.api.setDesktopGeneral({language:"es",autoSwitchView:false,transitionsEnabled:false,showFiles:true,collapsibleSourceContext:false});return r.success})()')
    Eval 'document.querySelector(".nova-rail [data-icon=settings]").closest("button").click();true' | Out-Null
    Wait-Renderer '!!document.querySelector("[data-settings-section=about]")'
    Eval 'document.querySelector("[data-settings-section=about]").click();true' | Out-Null
    Wait-Renderer 'document.querySelector(".nova-settings-dialog").textContent.includes("v0.13.0")'
    $image = Cdp 'Page.captureScreenshot' @{format='png'}
    [IO.File]::WriteAllBytes("$output\installed-about.png",[Convert]::FromBase64String($image.data))
    $profile = Join-Path $env:APPDATA 'nova-desktop'
    Set-Content -LiteralPath "$profile\qa-preserve.txt" -Value 'owned profile marker'
    Set-Content -LiteralPath "$documents\Nova\workspace\qa-preserve.txt" -Value 'owned document marker'
    $socket.Dispose();$socket=$null
    $application.Refresh()
    Check 'normal application close is accepted' ($application.CloseMainWindow())
    Check 'application exits normally' ($application.WaitForExit(30000))
    $application=$null
    for($attempt=0;$attempt -lt 40;$attempt++) { if(-not (Get-Process -Name nova-backend -ErrorAction SilentlyContinue)){break};Start-Sleep -Milliseconds 250 }
    Check 'backend exits with the application' (-not (Get-Process -Name nova-backend -ErrorAction SilentlyContinue))
    $preferences = Get-Content -Raw -LiteralPath "$profile\desktop-preferences.json" | ConvertFrom-Json
    Check 'saved preferences persisted' ($preferences.language -eq 'es')
    Run-Owned "$install\Uninstall Nova.exe" @('/S') 'uninstall'
    for($attempt=0;$attempt -lt 90;$attempt++) { if(-not (Test-Path -LiteralPath $appExe)){break};Start-Sleep -Milliseconds 500 }
    Check 'uninstaller removes application and bundled runtime' (-not (Test-Path -LiteralPath $appExe) -and -not (Test-Path -LiteralPath $backend))
    Check 'uninstall preserves profile preferences and user documents' ((Test-Path -LiteralPath "$profile\qa-preserve.txt") -and (Test-Path -LiteralPath "$profile\desktop-preferences.json") -and (Test-Path -LiteralPath "$documents\Nova\workspace\qa-preserve.txt"))
    $result.status = 'PASS'
} catch {
    $result.error = $_.Exception.Message
    try { Get-WinEvent -LogName 'Microsoft-Windows-CodeIntegrity/Operational' -MaxEvents 12 | Select-Object Id,Message | ConvertTo-Json -Depth 3 | Set-Content -Encoding UTF8 -LiteralPath "$output\code-integrity.json" } catch {}
} finally {
    if($socket){$socket.Dispose()}
    if($application -and -not $application.HasExited){$application.CloseMainWindow() | Out-Null}
    $result | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 -LiteralPath "$output\result.json"
    foreach($name in @('install','runtime','browser','app','uninstall')) {
        foreach($stream in @('stdout','stderr')) {
            $file="$root\$name.$stream.log"
            if(Test-Path -LiteralPath $file){Copy-Item -LiteralPath $file -Destination $output}
        }
    }
    Start-Process -FilePath "$env:SystemRoot\System32\shutdown.exe" -ArgumentList @('/s','/t','3') -WindowStyle Hidden
}
