@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Universal Media Downloader Launcher

echo ============================================
echo   Universal Media Downloader v7 - Windows
echo ============================================
echo.

set "PYTHON_EXE="

py -3 -c "import sys; print(sys.executable)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_EXE=py -3"
    goto :python_found
)

python -c "import sys; print(sys.executable)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_EXE=python"
    goto :python_found
)

python3 -c "import sys; print(sys.executable)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_EXE=python3"
    goto :python_found
)

for /d %%D in ("%LocalAppData%\Programs\Python\Python3*") do (
    if exist "%%~fD\python.exe" (
        set "PYTHON_EXE=%%~fD\python.exe"
        goto :python_found
    )
)

for /d %%D in ("C:\Program Files\Python3*") do (
    if exist "%%~fD\python.exe" (
        set "PYTHON_EXE=%%~fD\python.exe"
        goto :python_found
    )
)

for /d %%D in ("C:\Python3*") do (
    if exist "%%~fD\python.exe" (
        set "PYTHON_EXE=%%~fD\python.exe"
        goto :python_found
    )
)

echo Python could not be found from this BAT file.
echo Run this in PowerShell to locate it:
echo   python -c "import sys; print(sys.executable)"
pause
exit /b 1

:python_found
echo Found Python using:
echo   %PYTHON_EXE%
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Creating local Python environment...
    %PYTHON_EXE% -m venv ".venv"
    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

set "VENV_PY=.venv\Scripts\python.exe"
set "VENV_PYW=.venv\Scripts\pythonw.exe"

"%VENV_PY%" -c "import yt_dlp, PIL, plyer, tkinterdnd2" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    "%VENV_PY%" -m pip install --upgrade pip
    "%VENV_PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Failed to install dependencies.
        pause
        exit /b 1
    )
)

where.exe ffmpeg >nul 2>&1
if errorlevel 1 (
    echo.
    echo WARNING: FFmpeg is not installed or not in PATH.
    echo Multi-audio, subtitle embedding, MP3 conversion and compression need FFmpeg.
    echo Install once with:
    echo   winget install --id Gyan.FFmpeg -e
    echo.
)

if exist "%VENV_PYW%" (
    start "" "%VENV_PYW%" "downloader_gui.py"
) else (
    start "" "%VENV_PY%" "downloader_gui.py"
)
exit /b 0
