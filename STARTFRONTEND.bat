@echo off
title ForgeAgent - Frontend Dashboard
cd /d "%~dp0"

echo ==========================================================
echo  Launching ForgeAgent Frontend Dashboard
echo ==========================================================
echo.

:: Check if backend is running on port 8000
netstat -ano | findstr ":8000" >nul
if errorlevel 1 (
    echo [Backend] Starting background backend on port 8000...
    start "ForgeAgent Backend" /min "%~dp0backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir "%~dp0backend"
    ping 127.0.0.1 -n 3 >nul
) else (
    echo [Backend] Backend is already running on port 8000.
)

:: Launch frontend dev server
cd /d "%~dp0frontend"
echo [Frontend] Starting Vite Dev Server on http://localhost:5173...
start http://localhost:5173
npm run dev
