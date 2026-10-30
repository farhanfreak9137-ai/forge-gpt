@echo off
title ForgeAgent V1 - Local Autonomous Development System
cd /d "%~dp0"

echo ==========================================================
echo  Launching ForgeAgent V1 (Backend + Frontend Dashboard)
echo ==========================================================
echo.

powershell -ExecutionPolicy Bypass -File "scripts\start.ps1"

pause
