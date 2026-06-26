$ErrorActionPreference = "Stop"

$TaskName = "FTTH BOM"

$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($Task) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Usunieto autostart: $TaskName"
} else {
    Write-Host "Autostart nie byl ustawiony: $TaskName"
}
