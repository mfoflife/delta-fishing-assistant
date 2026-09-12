$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskCache = Join-Path $PSScriptRoot '.cache'
New-Item -ItemType Directory -Path (Join-Path $taskCache 'tmp'),(Join-Path $taskCache 'pip') -Force | Out-Null
$env:TEMP = Join-Path $taskCache 'tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $taskCache 'pip'
$env:PYTHONUTF8 = '1'
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    if (Test-Path -LiteralPath 'D:\python3.13.7\python.exe') {
        & 'D:\python3.13.7\python.exe' -m venv .venv
    } else {
        & py -3 -m venv .venv
    }
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required.' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
Write-Host 'Ready. Double-click start.cmd.'
