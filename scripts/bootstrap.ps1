$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Have($name) { return [bool](Get-Command $name -ErrorAction SilentlyContinue) }

Write-Host "== Personal Assistant bootstrap =="
Write-Host "Root: $Root"

if (-not (Have "py")) { throw "Python launcher 'py' not found. Install Python 3.12." }
if (-not (Have "node")) { throw "Node.js not found." }
if (-not (Have "npm")) { throw "npm not found." }

if (-not (Have "ollama")) {
    Write-Host "Installing Ollama..."
    winget install --id Ollama.Ollama -e --accept-package-agreements --accept-source-agreements
}
if (-not (Have "ffmpeg")) {
    Write-Host "Installing FFmpeg..."
    winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
}
if (-not (Have "espeak-ng")) {
    Write-Host "Installing eSpeak NG (needed by Kokoro TTS)..."
    winget install --id eSpeak-NG.eSpeakNG -e --accept-package-agreements --accept-source-agreements
}

$venv = Join-Path $Root ".venv"
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
    Write-Host "Creating Python 3.12 venv..."
    py -3.12 -m venv $venv
}

& "$venv\Scripts\python.exe" -m pip install --upgrade pip
Write-Host "Installing CPU PyTorch so Kokoro does not steal GPU from Ollama..."
& "$venv\Scripts\python.exe" -m pip install torch --index-url https://download.pytorch.org/whl/cpu
& "$venv\Scripts\python.exe" -m pip install -r (Join-Path $Root "backend\requirements.txt")
& "$venv\Scripts\python.exe" -m pip install -r (Join-Path $Root "backend\requirements-ml.txt")

Push-Location (Join-Path $Root "dashboard")
npm install
npm run build
Pop-Location

if (-not (Have "openclaw")) {
    Write-Host "Installing OpenClaw CLI..."
    npm install -g openclaw
}

& (Join-Path $Root "scripts\sync-openclaw.ps1")

if (Have "ollama") {
    Write-Host "Pulling Qwen 2.5 7B (best 8GB fit)..."
    ollama pull qwen2.5:7b
}

New-Item -ItemType Directory -Force -Path (Join-Path $Root "data") | Out-Null
Write-Host ""
Write-Host "Bootstrap done."
Write-Host "1. Start:  powershell -File scripts\start.ps1"
Write-Host "2. Pair WhatsApp: powershell -File scripts\pair-whatsapp.ps1"
Write-Host "3. Optional autostart: powershell -File scripts\install-autostart.ps1"
Write-Host "Dashboard: http://127.0.0.1:8787"
