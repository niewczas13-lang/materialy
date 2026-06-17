param(
    [switch]$Quiet
)

$ErrorActionPreference = "SilentlyContinue"

$Root = Split-Path -Parent $PSScriptRoot
$PidFile = Join-Path $Root "data\ftth_bom.pid"
$Stopped = $false

function Stop-AppPid {
    param([int]$AppPid)

    $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $AppPid"
    if ($proc -and $proc.CommandLine -match "web_app\.py") {
        Stop-Process -Id $AppPid -Force
        return $true
    }
    return $false
}

if (Test-Path -LiteralPath $PidFile) {
    $pidText = (Get-Content -LiteralPath $PidFile -Raw).Trim()
    $pidValue = 0
    if ([int]::TryParse($pidText, [ref]$pidValue)) {
        $Stopped = Stop-AppPid -AppPid $pidValue
    }
    Remove-Item -LiteralPath $PidFile -Force
}

if (-not $Stopped) {
    $candidates = Get-CimInstance Win32_Process |
        Where-Object {
            $_.CommandLine -match "web_app\.py" -and
            $_.CommandLine -match "8787"
        }

    foreach ($candidate in $candidates) {
        Stop-Process -Id $candidate.ProcessId -Force
        $Stopped = $true
    }
}

if (-not $Quiet) {
    if ($Stopped) {
        Write-Host "Zatrzymano FTTH BOM."
    } else {
        Write-Host "FTTH BOM nie byl uruchomiony."
    }
}
