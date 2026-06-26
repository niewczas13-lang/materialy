$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$TaskName = "FTTH BOM"
$PowerShell = (Get-Command "powershell.exe" -ErrorAction Stop).Source
$StartScript = Join-Path $PSScriptRoot "start_app.ps1"
$Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$StartScript`""

if (-not (Test-Path -LiteralPath $StartScript)) {
    throw "Nie znaleziono skryptu startowego: $StartScript"
}

$Action = New-ScheduledTaskAction `
    -Execute $PowerShell `
    -Argument $Arguments `
    -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Uruchamia lokalna aplikacje FTTH BOM po zalogowaniu uzytkownika." `
    -Force | Out-Null

Write-Host "Dodano autostart: $TaskName"
Write-Host "Aplikacja bedzie startowac po zalogowaniu uzytkownika Windows."
Write-Host "Uruchamiam aplikacje teraz..."
& (Join-Path $PSScriptRoot "start_app.ps1")
Write-Host "Gotowe: http://127.0.0.1:8787/"
