<#
.SYNOPSIS
    ForgeAgent V1 Local Startup Script
.DESCRIPTION
    Launches Microsoft Edge (ChatGPT on port 9222), the FastAPI backend server on 127.0.0.1:8000,
    and the Vite frontend dev server on 127.0.0.1:5173.
#>

$ErrorActionPreference = "Stop"

$RootPath = Resolve-Path "$PSScriptRoot\.."

# First run: verify virtualenv and frontend dependencies
if (-not (Test-Path "$RootPath\backend\.venv\Scripts\python.exe") -or -not (Test-Path "$RootPath\frontend\node_modules")) {
    Write-Host "Environment not set up yet; running scripts\setup.ps1 first..." -ForegroundColor Yellow
    & "$PSScriptRoot\setup.ps1"
}

Write-Host "==========================================================" -ForegroundColor Green
Write-Host " Starting ForgeAgent V1 (Local Windows Host)" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

# 1. Start Microsoft Edge with ChatGPT if not already open
Write-Host "`n[1/3] Ensuring Microsoft Edge (ChatGPT on port 9222) is open..." -ForegroundColor Cyan
$EdgePath = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if (-not (Test-Path $EdgePath)) { $EdgePath = "C:\Program Files\Microsoft\Edge\Application\msedge.exe" }
$ProfileDir = "$RootPath\backend\data\browser_profile"

$EdgeListening = $false
try {
    $conn = New-Object System.Net.Sockets.TcpClient
    $iar = $conn.BeginConnect("127.0.0.1", 9222, $null, $null)
    $success = $iar.AsyncWaitHandle.WaitOne(800, $false)
    if ($success -and $conn.Connected) {
        $EdgeListening = $true
        $conn.EndConnect($iar)
    }
    $conn.Close()
} catch {}

if (-not $EdgeListening) {
    Write-Host "Launching Microsoft Edge to https://chatgpt.com..." -ForegroundColor Green
    Start-Process -FilePath $EdgePath -ArgumentList "--remote-debugging-port=9222", "--user-data-dir=`"$ProfileDir`"", "https://chatgpt.com"
    Start-Sleep -Seconds 2
} else {
    Write-Host "Microsoft Edge is already running on port 9222." -ForegroundColor Gray
}

# 2. Start Backend in Background Process
Write-Host "`n[2/3] Launching Backend on http://127.0.0.1:8000..." -ForegroundColor Cyan
$BackendProcess = Start-Process -FilePath "$RootPath\backend\.venv\Scripts\python.exe" `
    -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir `"$RootPath\backend`"" `
    -WorkingDirectory "$RootPath\backend" `
    -PassThru

Start-Sleep -Seconds 2

# 3. Start Frontend
Write-Host "`n[3/3] Launching Frontend on http://localhost:5173..." -ForegroundColor Cyan
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
