@echo off
title Nova AI Desktop Assistant
cd /d "%~dp0"

:: 1. Check local python
if exist "E:\python\pythonw.exe" (
    start "" "E:\python\pythonw.exe" "%~dp0main.py"
    exit /b 0
)

:: 2. Check PATH pythonw
for /f "delims=" %%i in ('where pythonw 2^>nul') do (
    start "" "%%i" "%~dp0main.py"
    exit /b 0
)

:: 3. Check AppData python
for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
    if exist "%%d\pythonw.exe" (
        start "" "%%d\pythonw.exe" "%~dp0main.py"
        exit /b 0
    )
)

:: 4. Fallback to python.exe
python main.py
