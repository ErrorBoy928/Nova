@echo off
title Nova AI - Coding Assistant Edition - Clean Installer
setlocal enabledelayedexpansion

echo ============================================================
echo      NOVA AI - CODING ASSISTANT EDITION - INSTALLER
echo ============================================================
echo.
echo [1/4] Detecting Python Environment...

set "PY_EXE="
:: 1. Check local environment on Drive E:
if exist "E:\python\python.exe" (
    set "PY_EXE=E:\python\python.exe"
    set "PYW_EXE=E:\python\pythonw.exe"
    goto :python_found
)

:: 2. Check system PATH python
for /f "delims=" %%i in ('where python 2^>nul') do (
    set "PY_EXE=%%i"
    set "PYW_EXE=%%~dpi\pythonw.exe"
    goto :python_found
)

:: 3. Check Windows Python Launcher (py.exe)
for /f "delims=" %%i in ('where py 2^>nul') do (
    set "PY_EXE=%%i"
    set "PYW_EXE=%%~dpi\pythonw.exe"
    goto :python_found
)

:: 4. Check user AppData Python installs
for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
    if exist "%%d\python.exe" (
        set "PY_EXE=%%d\python.exe"
        set "PYW_EXE=%%d\pythonw.exe"
        goto :python_found
    )
)

:python_not_found
echo.
echo [NOTICE] Python was not found on this computer.
echo Nova AI requires Python 3.10+ to run.
echo.
echo Downloading official Python installer from python.org...
set "TEMP_PY=%TEMP%\python_installer.exe"
curl -s -L "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe" -o "%TEMP_PY%"

if not exist "%TEMP_PY%" (
    echo [ERROR] Could not download Python. Please install Python 3.10+ manually from https://python.org
    pause
    exit /b 1
)

echo Installing Python silently (please wait ~1 minute)...
"%TEMP_PY%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
del /f /q "%TEMP_PY%" >nul 2>&1

:: Re-check PATH
for /f "delims=" %%i in ('where python 2^>nul') do (
    set "PY_EXE=%%i"
    set "PYW_EXE=%%~dpi\pythonw.exe"
    goto :python_found
)

for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
    if exist "%%d\python.exe" (
        set "PY_EXE=%%d\python.exe"
        set "PYW_EXE=%%d\pythonw.exe"
        goto :python_found
    )
)

echo [ERROR] Python installation incomplete. Please install Python from https://python.org and re-run.
pause
exit /b 1

:python_found
if not exist "!PYW_EXE!" set "PYW_EXE=!PY_EXE!"
echo [OK] Python detected: !PY_EXE!

echo.
echo [2/4] Verifying and installing required packages...
cd /d "%~dp0"
"!PY_EXE!" -m pip install --quiet --upgrade pip >nul 2>&1
"!PY_EXE!" -m pip install --quiet -r requirements.txt

echo.
echo [3/4] Creating Windows Desktop & Start Menu Shortcuts...
set "APP_DIR=%~dp0"
set "APP_DIR=%APP_DIR:~0,-1%"

:: PowerShell shortcut creation (100% safe, clean, no antivirus alert)
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; " ^
  "$desk = [Environment]::GetFolderPath('Desktop'); " ^
  "$sc = $ws.CreateShortcut(\"$desk\Nova AI Coding Assistant.lnk\"); " ^
  "$sc.TargetPath = '!PYW_EXE!'; " ^
  "$sc.Arguments = '\"%APP_DIR%\main.py\"'; " ^
  "$sc.WorkingDirectory = '%APP_DIR%'; " ^
  "$sc.IconLocation = 'shell32.dll,14'; " ^
  "$sc.Description = 'Nova AI - Elite Coding & Desktop Assistant'; " ^
  "$sc.Save(); " ^
  "$sm = [Environment]::GetFolderPath('Programs'); " ^
  "$sc2 = $ws.CreateShortcut(\"$sm\Nova AI Coding Assistant.lnk\"); " ^
  "$sc2.TargetPath = '!PYW_EXE!'; " ^
  "$sc2.Arguments = '\"%APP_DIR%\main.py\"'; " ^
  "$sc2.WorkingDirectory = '%APP_DIR%'; " ^
  "$sc2.IconLocation = 'shell32.dll,14'; " ^
  "$sc2.Description = 'Nova AI - Elite Coding & Desktop Assistant'; " ^
  "$sc2.Save();"

echo [OK] Desktop Shortcut created: 'Nova AI Coding Assistant'

echo.
echo [4/4] Launching Nova AI Coding Assistant...
start "" "!PYW_EXE!" "%APP_DIR%\main.py"

echo.
echo ============================================================
echo   INSTALLATION COMPLETED! Nova AI is now running.
echo   Press Ctrl + Shift + N anywhere on Windows to toggle Nova.
echo ============================================================
timeout /t 3 >nul
exit /b 0
