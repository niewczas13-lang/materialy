$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

New-Item -ItemType Directory -Path (Join-Path $Root "outputs") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $Root "data") -Force | Out-Null

& (Join-Path $PSScriptRoot "stop_app.ps1") -Quiet

$python = Get-Command "python.exe" -ErrorAction SilentlyContinue
$pythonArgs = @()

if (-not $python) {
    $python = Get-Command "py.exe" -ErrorAction SilentlyContinue
    $pythonArgs = @("-3")
}
if (-not $python) {
    throw "Nie znaleziono Pythona. Zainstaluj Python 3.11/3.12 i zaznacz Add Python to PATH."
}

$args = $pythonArgs + @(
    "web_app.py",
    "--host", "0.0.0.0",
    "--port", "8787",
    "--pid-file", "data\ftth_bom.pid"
)

$stdout = Join-Path $Root "data\ftth_bom.log"
$stderr = Join-Path $Root "data\ftth_bom.err.log"

Start-Process `
    -FilePath $python.Source `
    -ArgumentList $args `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr
