@echo off
title ForgeAgent - Microsoft Edge for ChatGPT
cd /d "%~dp0"

echo ==========================================================
echo  Launching Microsoft Edge for ChatGPT (Visible Window)
echo ==========================================================
echo.
echo Opening Edge to https://chatgpt.com with ForgeAgent profile.
echo You can log into your ChatGPT account here.
echo Once logged in, your session remains saved.
echo ForgeAgent will connect directly to this window!
echo.

set "EDGE_EXE="
if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" set "EDGE_EXE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if exist "C:\Program Files\Microsoft\Edge\Application\msedge.exe" set "EDGE_EXE=C:\Program Files\Microsoft\Edge\Application\msedge.exe"

if "%EDGE_EXE%"=="" (
    start "" msedge --remote-debugging-port=9222 --user-data-dir="%~dp0backend\data\browser_profile" "https://chatgpt.com"
) else (
    start "" "%EDGE_EXE%" --remote-debugging-port=9222 --user-data-dir="%~dp0backend\data\browser_profile" "https://chatgpt.com"
)

echo Microsoft Edge is open on your screen!
