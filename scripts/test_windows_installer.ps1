param(
    [Parameter(Mandatory=$true)][string]$Installer,
    [Parameter(Mandatory=$true)][string]$Output
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$installerPath=(Resolve-Path -LiteralPath $Installer).Path
if(-not [IO.Path]::IsPathRooted($Output)){throw 'Use an absolute, fresh output directory outside the checkout'}
$outputPath=[IO.Path]::GetFullPath($Output)
if($outputPath.StartsWith($root+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or $outputPath -eq $root){throw 'Test output must be outside the checkout'}
if(Test-Path -LiteralPath $outputPath){throw 'Use a fresh output directory'}
New-Item -ItemType Directory -Path "$outputPath\input","$outputPath\output" | Out-Null
$outputPath=(Resolve-Path -LiteralPath $outputPath).Path
if($outputPath.StartsWith((Resolve-Path -LiteralPath $root).Path+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Output resolves inside the checkout'}
Copy-Item -LiteralPath $installerPath -Destination "$outputPath\input"
Copy-Item -LiteralPath "$root\packaging\windows\sandbox_test.ps1" -Destination "$outputPath\input"
(Get-FileHash -Algorithm SHA256 -LiteralPath $installerPath).Hash | Set-Content -Encoding ascii -LiteralPath "$outputPath\input\installer.sha256"
$inputXml=[Security.SecurityElement]::Escape("$outputPath\input")
$outputXml=[Security.SecurityElement]::Escape("$outputPath\output")
@"
<Configuration>
 <Networking>Disable</Networking>
 <ClipboardRedirection>Disable</ClipboardRedirection>
 <MemoryInMB>3072</MemoryInMB>
 <MappedFolders>
  <MappedFolder><HostFolder>$inputXml</HostFolder><SandboxFolder>C:\NovaInput</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>
  <MappedFolder><HostFolder>$outputXml</HostFolder><SandboxFolder>C:\NovaOutput</SandboxFolder><ReadOnly>false</ReadOnly></MappedFolder>
 </MappedFolders>
 <LogonCommand><Command>powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\NovaInput\sandbox_test.ps1</Command></LogonCommand>
</Configuration>
"@ | Set-Content -Encoding utf8 -LiteralPath "$outputPath\test.wsb"
Start-Process -FilePath "$env:SystemRoot\System32\WindowsSandbox.exe" -ArgumentList @("`"$outputPath\test.wsb`"") -WindowStyle Hidden | Out-Null
$receipt="$outputPath\output\result.json"
for($attempt=0;$attempt -lt 450;$attempt++) {
    if(Test-Path -LiteralPath $receipt){break}
    Start-Sleep -Seconds 2
}
if(-not (Test-Path -LiteralPath $receipt)){throw 'Windows Sandbox did not produce a result within 15 minutes'}
$result=Get-Content -Raw -LiteralPath $receipt -Encoding utf8 | ConvertFrom-Json
$result | ConvertTo-Json -Depth 12
if($result.status -ne 'PASS'){throw 'Installed Windows application verification failed; retained logs are in the output directory'}
