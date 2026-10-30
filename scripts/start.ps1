<#
.SYNOPSIS
    ForgeAgent V1 Local Startup Script
.DESCRIPTION
    Launches the FastAPI backend server on 127.0.0.1:8000 and the Vite frontend dev server on 127.0.0.1:5173.
#>

$ErrorActionPreference = "Stop"

$RootPath = Resolve-Path "$PSScriptRoot\.."

Write-Host "==========================================================" -ForegroundColor Green
Write-Host " Starting ForgeAgent V1 (Local Windows Host)" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

# 1. Start Backend in Background Process (without --reload because Playwright subprocesses require Windows Proactor loop)
Write-Host "`n[1/2] Launching Backend on http://127.0.0.1:8000..." -ForegroundColor Cyan
$BackendProcess = Start-Process -FilePath "$RootPath\backend\.venv\Scripts\python.exe" `
    -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8000" `
    -WorkingDirectory "$RootPath\backend" `
    -PassThru

Start-Sleep -Seconds 2

# 2. Start Frontend
Write-Host "`n[2/2] Launching Frontend on http://localhost:5173..." -ForegroundColor Cyan
Write-Host "Opening web dashboard in your browser..." -ForegroundColor Green
Start-Process "http://localhost:5173"
Write-Host "Press Ctrl+C to terminate both servers.`n" -ForegroundColor Yellow

try {
    Set-Location "$RootPath\frontend"
    cmd /c npm run dev
} finally {
    Write-Host "`nStopping ForgeAgent Backend..." -ForegroundColor Yellow
    if ($BackendProcess -and -not $BackendProcess.HasExited) {
        Stop-Process -Id $BackendProcess.Id -Force
    }
}

