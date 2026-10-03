$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Start = Join-Path $Root "scripts\start.ps1"
$TaskName = "PersonalAssistantLocal"
$StartupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$Launcher = Join-Path $StartupDir "$TaskName.cmd"

if (-not (Test-Path -LiteralPath $Start)) {
    throw "Missing start script: $Start"
}

New-Item -ItemType Directory -Force -Path $StartupDir | Out-Null
@(
    "@echo off"
    "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Start`""
) | Set-Content -LiteralPath $Launcher -Encoding ASCII

$taskOk = $false
try {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Start`""
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
    $taskOk = $true
} catch {
    Write-Host "Scheduled task was skipped (Windows blocked it). Using the Startup folder instead."
}

Write-Host "Enabled logon autostart via $Launcher"
if ($taskOk) {
    Write-Host "Also created logon task $TaskName"
}
Write-Host "The dashboard will open at http://127.0.0.1:8787 after you sign in."
