@echo off
title Testing Real ChatGPT via Microsoft Edge
cd /d "%~dp0"

echo =========================================================
echo  ForgeAgent - Live Microsoft Edge + ChatGPT Test
echo =========================================================
echo.

:: 1. Check if Edge is listening on port 9222
netstat -ano | findstr ":9222" >nul
if errorlevel 1 (
    echo [1/2] Launching Microsoft Edge on port 9222...
    call START_EDGE.bat
    ping 127.0.0.1 -n 4 >nul
) else (
    echo [1/2] Microsoft Edge is already running on port 9222.
)

:: 2. Run the live Edge test
echo.
echo [2/2] Connecting Playwright to Edge and testing ChatGPT...
backend\.venv\Scripts\python.exe scripts\run_live_test.py

echo.
echo =========================================================
echo  Test finished successfully!
echo =========================================================
