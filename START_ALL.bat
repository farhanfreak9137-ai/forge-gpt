@echo off
title ForgeAgent V1 - All-In-One Launcher
cd /d "%~dp0"
:: First run: install everything if it has not been set up on this computer yet
if not exist "backend\.venv\Scripts\python.exe" goto :needs_setup
if not exist "frontend\node_modules" goto :needs_setup
goto :setup_done
:needs_setup
echo First run detected: installing ForgeAgent. This takes a few minutes and needs internet.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1"
if errorlevel 1 (
    echo.
    echo [Error] Setup failed. Read SETUP_GUIDE.md ^(Troubleshooting^) and try again.
    pause
    exit /b 1
)
:setup_done

echo ==========================================================
echo  Launching ForgeAgent V1 (All-in-One: Edge + ChatGPT + Studio)
echo ==========================================================
echo.

:: 1. Launch Microsoft Edge with ChatGPT (Port 9222) if not already open
echo [1/3] Launching Microsoft Edge with ChatGPT (Port 9222)...
netstat -ano | findstr ":9222" >nul
if errorlevel 1 (
    set "EDGE_EXE="
    if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" set "EDGE_EXE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if exist "C:\Program Files\Microsoft\Edge\Application\msedge.exe" set "EDGE_EXE=C:\Program Files\Microsoft\Edge\Application\msedge.exe"

    if "%EDGE_EXE%"=="" (
        start "" msedge --remote-debugging-port=9222 --user-data-dir="%~dp0backend\data\browser_profile" "https://chatgpt.com"
    ) else (
        start "" "%EDGE_EXE%" --remote-debugging-port=9222 --user-data-dir="%~dp0backend\data\browser_profile" "https://chatgpt.com"
    )
    ping 127.0.0.1 -n 3 >nul
) else (
    echo       Microsoft Edge is already running on port 9222.
)

:: 2. Launch FastAPI Backend on Port 8000 if not already running
echo [2/3] Checking ForgeAgent Backend (Port 8000)...
netstat -ano | findstr ":8000" >nul
if errorlevel 1 (
    echo       Starting background Backend server...
    start "ForgeAgent Backend" /min "%~dp0backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir "%~dp0backend"
    ping 127.0.0.1 -n 3 >nul
) else (
    echo       Backend is already running on port 8000.
)

:: 3. Launch Vite Frontend Dev Server on Port 5173
echo [3/3] Starting Frontend Dashboard on http://localhost:5173...
start http://localhost:5173
cd /d "%~dp0frontend"
npm run dev

