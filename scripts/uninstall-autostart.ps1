$ErrorActionPreference = "SilentlyContinue"
$TaskName = "PersonalAssistantLocal"
$Launcher = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\$TaskName.cmd"
if (Test-Path -LiteralPath $Launcher) {
    Remove-Item -LiteralPath $Launcher -Force
}
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Removed $TaskName autostart"
