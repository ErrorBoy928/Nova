@echo off
title Nova AI Assistant Setup
setlocal enabledelayedexpansion

echo ============================================================
echo            Nova AI Desktop Assistant Setup
echo ============================================================
echo.

:: Detect Python
set "PY_EXE=E:\python\python.exe"
if not exist "!PY_EXE!" (
    for /f "delims=" %%i in ('where python 2^>nul') do (
        set "PY_EXE=%%i"
        goto :found_py
    )
)

for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
    if exist "%%d\python.exe" (
        set "PY_EXE=%%d\python.exe"
        goto :found_py
    )
)

:found_py
if not exist "!PY_EXE!" (
    echo [ERROR] Python not found. Installing Python or running setup...
    call "%~dp0..\Install_Nova_AI.bat"
    exit /b 0
)

echo [OK] Using Python: !PY_EXE!
echo Launching Setup Wizard...

start "" "!PY_EXE!" "%~dp0setup_wizard.py"
exit /b 0
