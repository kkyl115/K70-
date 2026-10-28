$ErrorActionPreference = 'Stop'
$windowsScript = ($PSScriptRoot + '\scripts\build-baseline.sh').Replace('\', '/')
$converted = wsl -d Ubuntu -- wslpath -a $windowsScript
if ($LASTEXITCODE -ne 0) { throw 'WSL Ubuntu or path conversion unavailable' }
$linuxScript = $converted.Trim()
wsl -d Ubuntu -- bash $linuxScript
if ($LASTEXITCODE -ne 0) { throw "Baseline build failed; see evidence/baseline-build.log (exit $LASTEXITCODE)" }
