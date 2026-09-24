@echo off
setlocal EnableExtensions
title Living Assistant
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

set "HOST=127.0.0.1"
set "PORT=8787"
set "URL=http://%HOST%:%PORT%/dashboard"
set "VENV_DIR=%PROJECT_ROOT%.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "TEMP_DIR=%TEMP%\LivingAssistant"
if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%" >nul 2>&1
set "REQ_FILE=%TEMP_DIR%\requirements-%RANDOM%-%RANDOM%.txt"
set "TOKEN_FILE=%TEMP_DIR%\api-token-%RANDOM%-%RANDOM%.txt"
set "ELECTRON_RUNTIME_DIR=%TEMP_DIR%\electron-runtime"
set "ELECTRON_EXE=%ELECTRON_RUNTIME_DIR%\node_modules\electron\dist\electron.exe"

echo ========================================================
echo                 LIVING ASSISTANT
echo ========================================================
echo.

if not exist "%PROJECT_ROOT%pyproject.toml" (
    echo [ERROR] pyproject.toml was not found.
    echo Make sure run.bat is inside the project root directory.
    pause
    exit /b 1
)

if not exist "%PROJECT_ROOT%src\living_assistant\api.py" (
    echo [ERROR] Living Assistant source files were not found.
    pause
    exit /b 1
)

if not exist "%PROJECT_ROOT%src\living_assistant\webui\index.html" (
    echo [ERROR] Dashboard files were not found.
    pause
    exit /b 1
)

if not exist "%PROJECT_ROOT%src\living_assistant\webui\vendor\plotly.min.js" (
    echo [ERROR] Plotly dashboard runtime is missing.
    pause
    exit /b 1
)

if not exist "%PROJECT_ROOT%electron-assistant\package.json" (
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

set "PYTHONPATH=%PROJECT_ROOT%src"
set "PYTHONUNBUFFERED=1"

if not defined ASSISTANT_API_TOKEN (
    "%VENV_PY%" -c "from living_assistant.security.api_auth import get_api_token; print(get_api_token())" > "%TOKEN_FILE%"
    if errorlevel 1 (
        echo [ERROR] Could not create the local assistant access token.
        del /q "%TOKEN_FILE%" >nul 2>&1
        pause
        exit /b 1
    )
    set /p ASSISTANT_API_TOKEN=<"%TOKEN_FILE%"
    del /q "%TOKEN_FILE%" >nul 2>&1
)

echo.

powershell.exe -NoProfile -Command "try { $null = (New-Object System.Net.Sockets.TcpClient).Connect('%HOST%', %PORT%); exit 0 } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 (
    echo Living Assistant is already running.
    echo Opening dashboard in your browser...
    start "" "%URL%"
    pause
    exit /b 0
)

echo ========================================================
echo Server:    http://%HOST%:%PORT%
echo Dashboard: %URL%
echo Local Ollama: no provider API key required
echo ========================================================
echo.
echo Starting Living Assistant...
echo Press CTRL+C to stop the server.
echo.

start "" powershell.exe -NoProfile -WindowStyle Hidden -Command "$u='%URL%'; for($i=0;$i -lt 60;$i++){try{$r=Invoke-RestMethod -Uri $u -TimeoutSec 1; if($r){Start-Process $u; exit}}catch{}; Start-Sleep -Seconds 1}"

if not exist "%ELECTRON_EXE%" (
    echo Installing desktop companion runtime...
    if not exist "%ELECTRON_RUNTIME_DIR%" mkdir "%ELECTRON_RUNTIME_DIR%" >nul 2>&1
    pushd "%ELECTRON_RUNTIME_DIR%"
    if not exist "package.json" (
        >package.json echo {"private":true,"dependencies":{"electron":"26.6.10"}}
    )
    call npm.cmd install --no-audit --no-fund --package-lock=false
    if errorlevel 1 (
        popd
        echo [ERROR] Could not install the desktop companion runtime.
        pause
        exit /b 1
    )
    popd
)

echo Starting hovering desktop companion...
start "" "%ELECTRON_EXE%" "%PROJECT_ROOT%electron-assistant"

"%VENV_PY%" -m uvicorn living_assistant.api:app --host %HOST% --port %PORT%

set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    if "%EXIT_CODE%"=="3" (
        echo [ERROR] Living Assistant could not start - port %PORT% may already be in use.
        echo         If another instance is running, close it first and try again.
    ) else (
        echo [ERROR] Living Assistant stopped with exit code %EXIT_CODE%.
    )
) else (
    echo Living Assistant stopped.
)

pause
exit /b %EXIT_CODE%