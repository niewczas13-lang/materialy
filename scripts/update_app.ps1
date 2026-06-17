param(
    [string]$Branch = "",
    [switch]$KeepConsoleOpen
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    & git @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Git zakonczyl prace kodem $LASTEXITCODE: git $($Args -join ' ')"
    }
}

function Get-CurrentBranch {
    $Current = (& git branch --show-current).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $Current) {
        throw "Nie udalo sie ustalic aktualnej galezi git."
    }
    return $Current
}

try {
    if (-not (Get-Command "git.exe" -ErrorAction SilentlyContinue)) {
        throw "Nie znaleziono git.exe w PATH."
    }

    if (-not (Test-Path -LiteralPath (Join-Path $Root ".git"))) {
        throw "Ten folder nie jest repozytorium git. Sklonuj aplikacje z GitHuba albo uruchom aktualizacje w folderze repo."
    }

    Write-Host "Zatrzymywanie aplikacji..."
    & (Join-Path $PSScriptRoot "stop_app.ps1") -Quiet

    $CurrentBranch = if ($Branch) { $Branch } else { Get-CurrentBranch }
    $TargetRef = "origin/$CurrentBranch"

    Write-Host "Pobieranie zmian z GitHuba..."
    Invoke-Git fetch --prune origin

    $TargetExists = (& git rev-parse --verify --quiet $TargetRef)
    if ($LASTEXITCODE -ne 0) {
        throw "Nie znaleziono zdalnej galezi $TargetRef."
    }

    Write-Host "Aktualizacja plikow aplikacji do $TargetRef..."
    Invoke-Git checkout $CurrentBranch
    Invoke-Git reset --hard $TargetRef

    Write-Host "Uruchamianie aplikacji w tle..."
    & (Join-Path $PSScriptRoot "start_app.ps1")

    Write-Host ""
    Write-Host "Gotowe. Aplikacja dziala w tle: http://127.0.0.1:8787/"
}
catch {
    Write-Host ""
    Write-Host "Aktualizacja nie powiodla sie:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "Probuje ponownie uruchomic aplikacje z aktualnych plikow..."
    try {
        & (Join-Path $PSScriptRoot "start_app.ps1")
    }
    catch {
        Write-Host "Nie udalo sie uruchomic aplikacji: $($_.Exception.Message)" -ForegroundColor Red
    }
    exit 1
}
finally {
    if ($KeepConsoleOpen) {
        Read-Host "Nacisnij Enter, aby zamknac"
    }
}
