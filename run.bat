@echo off
setlocal EnableExtensions
title Living Assistant
cd /d "%~dp0"

set "HOST=127.0.0.1"
set "PORT=8787"
set "URL=http://%HOST%:%PORT%/dashboard"
set "VENV_DIR=%CD%\.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "REQ_FILE=%TEMP%\living_assistant_runtime_requirements.txt"

echo ========================================================
echo                 LIVING ASSISTANT
echo ========================================================
echo.

if not exist "pyproject.toml" (
    echo [ERROR] pyproject.toml was not found.
    echo Make sure run.bat is inside the project root directory.
    pause
    exit /b 1
)

if not exist "src\living_assistant\api.py" (
    echo [ERROR] Living Assistant source files were not found.
    pause
    exit /b 1
)

if not exist "src\living_assistant\webui\index.html" (
    echo [ERROR] Dashboard files were not found.
    pause
    exit /b 1
)

if not exist "src\living_assistant\webui\vendor\plotly.min.js" (
    echo [ERROR] Plotly dashboard runtime is missing.
    pause
    exit /b 1
)

if not exist "electron-assistant\package.json" (
    echo [ERROR] Desktop companion files were not found.
    pause
    exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js is required for the hovering desktop companion.
    echo Install Node.js 18 or newer and run this file again.
    pause
    exit /b 1
)

where npm.cmd >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm was not found. Reinstall Node.js with npm enabled.
    pause
    exit /b 1
)

set "BOOTSTRAP_PY="
set "BOOTSTRAP_ARGS="

where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "BOOTSTRAP_PY=py"
        set "BOOTSTRAP_ARGS=-3"
    )
)

if not defined BOOTSTRAP_PY (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
        if not errorlevel 1 (
            set "BOOTSTRAP_PY=python"
            set "BOOTSTRAP_ARGS="
        )
    )
)

if not defined BOOTSTRAP_PY (
    echo [ERROR] Python 3.11 or newer is required.
    echo Install Python 3.11+ and make sure Python is added to PATH.
    pause
    exit /b 1
)

if not exist "%VENV_PY%" (
    echo [SETUP] Creating Python virtual environment...
    "%BOOTSTRAP_PY%" %BOOTSTRAP_ARGS% -m venv "%VENV_DIR%"

    if errorlevel 1 (
        echo [ERROR] Could not create the Python virtual environment.
        pause
        exit /b 1
    )
)

echo [SETUP] Checking runtime dependencies...

set "REQ_EXTRACT_CODE=import os,pathlib,tomllib; d=tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8')); pathlib.Path(os.environ['REQ_FILE']).write_text(''.join(x+'\n' for x in d.get('project',{}).get('dependencies',[])),encoding='utf-8')"
"%VENV_PY%" -c "%REQ_EXTRACT_CODE%"
if errorlevel 1 (
    echo [ERROR] Could not parse dependencies from pyproject.toml.
    echo [ERROR] Could not read dependencies from pyproject.toml.
    pause
    exit /b 1
)

"%VENV_PY%" -m pip install --disable-pip-version-check -r "%REQ_FILE%"

if errorlevel 1 (
    echo.
    echo [ERROR] Python dependency installation failed.
    echo Check your internet connection and the error above.
    del /q "%REQ_FILE%" >nul 2>&1
    pause
    exit /b 1
)

del /q "%REQ_FILE%" >nul 2>&1

set "PYTHONPATH=%CD%\src"
set "PYTHONUNBUFFERED=1"

echo.
echo ========================================================
echo Server:    http://%HOST%:%PORT%
echo Dashboard: %URL%
echo ========================================================
echo.
echo Starting Living Assistant...
echo Press CTRL+C to stop the server.
echo.

start "" powershell.exe -NoProfile -WindowStyle Hidden -Command "$u='%URL%'; for($i=0;$i -lt 60;$i++){try{$r=Invoke-RestMethod -Uri $u -TimeoutSec 1; if($r){Start-Process $u; exit}}catch{}; Start-Sleep -Seconds 1}"

if not exist "electron-assistant\node_modules\electron\dist\electron.exe" (
    echo Installing desktop companion dependencies...
    pushd "electron-assistant"
    call npm.cmd install --no-audit --no-fund
    if errorlevel 1 (
        popd
        echo [ERROR] Could not install desktop companion dependencies.
        pause
        exit /b 1
    )
    popd
)

echo Starting hovering desktop companion...
start "" /D "%CD%\electron-assistant" cmd.exe /c "npm.cmd start"

"%VENV_PY%" -m uvicorn living_assistant.api:app --host %HOST% --port %PORT%

set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo [ERROR] Living Assistant stopped with exit code %EXIT_CODE%.
) else (
    echo Living Assistant stopped.
)

pause
exit /b %EXIT_CODE%