$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Template = Join-Path $Root "openclaw\openclaw.template.json"
$DestDir = Join-Path $Root ".openclaw"
$Dest = Join-Path $DestDir "openclaw.json"
$RootPosix = ($Root -replace "\\", "/")

New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
$json = Get-Content $Template -Raw
$json = $json.Replace("__ROOT__", $RootPosix)
Set-Content -Path $Dest -Value $json -Encoding UTF8

$agents = @("main", "tasks", "reminders", "learning", "tutor", "meetings")
foreach ($id in $agents) {
    $src = Join-Path $Root "openclaw\agents\$id"
    $dst = Join-Path $DestDir "workspace-$id"
    New-Item -ItemType Directory -Force -Path $dst | Out-Null
    Copy-Item -Path (Join-Path $src "*") -Destination $dst -Recurse -Force
    New-Item -ItemType Directory -Force -Path (Join-Path $DestDir "agents\$id\agent") | Out-Null
}

Write-Host "OpenClaw config written to $Dest"
