@echo off
title ForgeAgent V1 - ChatGPT Edge Interactive Chat
cd /d "%~dp0"

echo ==========================================================
echo  Starting ForgeAgent Microsoft Edge ChatGPT Chat...
echo ==========================================================
echo.

if not exist "backend\.venv\Scripts\python.exe" (
    echo [Error] Python environment not found. Running setup...
    powershell -ExecutionPolicy Bypass -File "scripts\setup.ps1"
)

backend\.venv\Scripts\python.exe scripts\chat_edge.py

pause

