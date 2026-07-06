param(
    [switch]$Quiet,
    [int]$Port = 8787
)

$ErrorActionPreference = "SilentlyContinue"

$Root = Split-Path -Parent $PSScriptRoot
$PidFile = Join-Path $Root "data\ftth_bom.pid"
$Stopped = $false

function Stop-AppPid {
    param(
        [int]$AppPid,
        [string]$Reason = ""
    )

    if ($AppPid -eq $PID) {
        return $false
    }

    $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $AppPid"
    if ($proc) {
        Stop-Process -Id $AppPid -Force
        if (-not $Quiet -and $Reason) {
            Write-Host "Zatrzymano PID $AppPid ($($proc.Name)): $Reason"
        }
        return $true
    }
    return $false
}

function Get-ListeningPids {
    param([int]$LocalPort)

    Get-NetTCPConnection -LocalPort $LocalPort -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
}

if (Test-Path -LiteralPath $PidFile) {
    $pidText = (Get-Content -LiteralPath $PidFile -Raw).Trim()
    $pidValue = 0
    if ([int]::TryParse($pidText, [ref]$pidValue)) {
        $Stopped = Stop-AppPid -AppPid $pidValue -Reason "plik PID"
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
        if (Stop-AppPid -AppPid $candidate.ProcessId -Reason "web_app.py/port 8787") {
            $Stopped = $true
        }
    }
}

$listenerPids = @(Get-ListeningPids -LocalPort $Port)
foreach ($listenerPid in $listenerPids) {
    if (Stop-AppPid -AppPid $listenerPid -Reason "proces nasluchujacy na porcie $Port") {
        $Stopped = $true
    }
}

Start-Sleep -Milliseconds 500
$remainingListeners = @(Get-ListeningPids -LocalPort $Port)

if (-not $Quiet) {
    if ($Stopped) {
        Write-Host "Zatrzymano FTTH BOM."
    } else {
        Write-Host "FTTH BOM nie byl uruchomiony."
    }
    if ($remainingListeners.Count -eq 0) {
        Write-Host "Port 8787 jest wolny."
    } else {
        Write-Host "Port 8787 nadal jest zajety przez PID: $($remainingListeners -join ', ')."
    }
}
