$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:PA_ROOT = $Root
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$PidFile = Join-Path $Root "data\supervisor.pid"

if (-not (Test-Path $VenvPython)) {
    Write-Error "Run scripts\bootstrap.ps1 first."
}

New-Item -ItemType Directory -Force -Path (Join-Path $Root "data") | Out-Null
Set-Location $Root
$proc = Start-Process -FilePath $VenvPython -ArgumentList "`"$Root\scripts\supervisor.py`"" -WorkingDirectory $Root -WindowStyle Hidden -PassThru
Set-Content -Path $PidFile -Value $proc.Id
Start-Sleep -Seconds 2
Start-Process "http://127.0.0.1:8787"
Write-Host "Dashboard: http://127.0.0.1:8787"
