$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:PA_ROOT = $Root
$env:OPENCLAW_STATE_DIR = Join-Path $Root ".openclaw"
$env:OPENCLAW_CONFIG_PATH = Join-Path $Root ".openclaw\openclaw.json"
$env:Path = "$env:APPDATA\npm;$env:LOCALAPPDATA\Programs\Ollama;$env:LOCALAPPDATA\Microsoft\WinGet\Links;$env:Path"

if (-not (Get-Command openclaw -ErrorAction SilentlyContinue)) {
    Write-Error "OpenClaw is not installed. Re-run scripts\bootstrap.ps1"
}

Write-Host "Scan the QR with WhatsApp -> Linked devices."
# --agent must come before login. This install has several agents; WhatsApp belongs to main.
openclaw --no-color channels --agent main login --channel whatsapp
