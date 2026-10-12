param([Parameter(Mandatory)][string]$HarnessRoot)
$ErrorActionPreference='Stop'
$taskRoot=[IO.Path]::GetFullPath($HarnessRoot)
$taskDist=Join-Path $taskRoot 'dist'
$taskVs='C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat'
if(-not(Test-Path -LiteralPath $taskVs)){throw 'MSVC_UNAVAILABLE'}
if((Get-FileHash -LiteralPath (Join-Path $taskRoot 'cef-minimal.tar.bz2') -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'c81c34d048d87276f4a18f0b000206710a1709bb67dd658948b87100e1a538da'){throw 'DISTRIBUTION_HASH_MISMATCH'}
$taskSource=Join-Path $PSScriptRoot 'probe.cpp'
$taskExe=Join-Path $taskDist 'Release\nova-cef-native-probe.exe'
$taskObject=Join-Path $taskRoot 'probe.obj'
$taskSdk='C:\Program Files (x86)\Windows Kits\10'
$taskSdkVersion='10.0.26100.0'
if(-not(Test-Path -LiteralPath (Join-Path $taskSdk ('Include\'+$taskSdkVersion+'\um\Windows.h')))){throw 'WINDOWS_SDK_UNAVAILABLE'}
$taskSdkIncludes=' /I"'+$taskSdk+'\Include\'+$taskSdkVersion+'\um" /I"'+$taskSdk+'\Include\'+$taskSdkVersion+'\shared" /I"'+$taskSdk+'\Include\'+$taskSdkVersion+'\ucrt"'
$taskSdkLibraries=' /link /LIBPATH:"'+$taskSdk+'\Lib\'+$taskSdkVersion+'\um\x64" /LIBPATH:"'+$taskSdk+'\Lib\'+$taskSdkVersion+'\ucrt\x64"'
$taskSdkLibraries+=' /STACK:8388608'
$taskCommand='call "'+$taskVs+'" -arch=x64 -host_arch=x64 >nul && cl /nologo /std:c++20 /EHsc /MT /O2 /W4 /DUNICODE /D_UNICODE /DNOMINMAX /DCEF_API_VERSION=15400 /I"'+$taskDist+'"'+$taskSdkIncludes+' /Fo"'+$taskObject+'" /Fe"'+$taskExe+'" "'+$taskSource+'" "'+(Join-Path $taskDist 'Release\libcef.lib')+'" kernel32.lib user32.lib shell32.lib'+$taskSdkLibraries
& cmd.exe /d /c $taskCommand
if($LASTEXITCODE -ne 0){throw 'HARNESS_BUILD_FAILED'}
# CEF package resource deployment: ICU is loaded beside the executable even
# when the CEF pak/locales path is supplied separately.
Copy-Item -LiteralPath (Join-Path $taskDist 'Resources\icudtl.dat') -Destination (Join-Path $taskDist 'Release\icudtl.dat')
Get-FileHash -LiteralPath $taskExe -Algorithm SHA256
