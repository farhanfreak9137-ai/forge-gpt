@echo off
title ForgeAgent - First-time setup
cd /d "%~dp0"
echo ==========================================================
echo  ForgeAgent: first-time setup
echo  This installs everything it needs. It takes a few minutes
echo  and needs an internet connection. You only do this once.
echo ==========================================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1"
if errorlevel 1 (
    echo.
    echo [Error] Setup did not finish. Read SETUP_GUIDE.md ^(Troubleshooting^) and run SETUP.bat again.
    pause
    exit /b 1
)
echo.
echo Setup finished. Now double-click START_FORGEAGENT.bat to run the app.
pause
