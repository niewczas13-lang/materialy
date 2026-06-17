@echo off
cd /d "%~dp0"

where python >nul 2>nul
if %ERRORLEVEL%==0 (
  set PYTHON_CMD=python
) else (
  set PYTHON_CMD=py -3
)

%PYTHON_CMD% -m pip install --upgrade pip
%PYTHON_CMD% -m pip install -r requirements.txt

echo.
echo Gotowe. Teraz uruchom URUCHOM_APKE.bat
pause
