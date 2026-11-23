@echo off
title Nova AI Desktop Assistant
cd /d "%~dp0"

set "PY_EXE="
set "PYW_EXE="

if exist "E:\python\pythonw.exe" set "PYW_EXE=E:\python\pythonw.exe"
if exist "E:\python\python.exe" set "PY_EXE=E:\python\python.exe"

if not defined PYW_EXE (
    for /f "delims=" %%i in ('where pythonw 2^>nul') do set "PYW_EXE=%%i"
)
if not defined PY_EXE (
    for /f "delims=" %%i in ('where python 2^>nul') do set "PY_EXE=%%i"
)

if defined PYW_EXE (
    start "" "%PYW_EXE%" "%~dp0main.py"
    exit /b 0
)

if defined PY_EXE (
    "%PY_EXE%" "%~dp0main.py"
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] Nova AI exited with error code %errorlevel%.
        echo Check crash_log.txt for traceback details.
        pause
    )
    exit /b %errorlevel%
)

echo [ERROR] Python not found on system.
pause
