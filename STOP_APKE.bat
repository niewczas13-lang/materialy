@echo off
cd /d "%~dp0"

set "STOP_ARGS="
if /I "%~1"=="/quiet" set "STOP_ARGS=-Quiet"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_app.ps1" %STOP_ARGS%
if /I "%~1"=="/quiet" exit /b 0
powershell -NoProfile -Command "Start-Sleep -Seconds 2"
