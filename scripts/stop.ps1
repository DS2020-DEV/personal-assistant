$ErrorActionPreference = "SilentlyContinue"
$Root = Split-Path -Parent $PSScriptRoot
$PidFile = Join-Path $Root "data\supervisor.pid"
$Runtime = Join-Path $Root "data\runtime.json"

function Stop-Pid([int]$ProcId) {
    if ($ProcId -gt 0) {
        taskkill /PID $ProcId /T /F | Out-Null
    }
}

if (Test-Path $PidFile) {
    Stop-Pid ([int](Get-Content $PidFile))
    Remove-Item $PidFile -Force
}

if (Test-Path $Runtime) {
    $data = Get-Content $Runtime | ConvertFrom-Json
    if ($data.openclawPid) { Stop-Pid ([int]$data.openclawPid) }
}

Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and (
        $_.CommandLine -like "*scripts\supervisor.py*" -or
        $_.CommandLine -like "*app.main:app*" -or
        $_.CommandLine -like "*openclaw gateway*"
    )
} | ForEach-Object { Stop-Pid $_.ProcessId }

if (Get-Command ollama -ErrorAction SilentlyContinue) {
    ollama stop qwen2.5:7b 2>$null
    ollama stop qwen3:8b 2>$null
}

Write-Host "Assistants and dashboard stopped."
