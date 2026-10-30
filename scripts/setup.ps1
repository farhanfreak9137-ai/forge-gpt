<#
.SYNOPSIS
    ForgeAgent V1 Setup Script for Windows
.DESCRIPTION
    Checks Python 3.12+ (or installs via uv), creates virtualenv, installs backend requirements,
    installs frontend npm packages, and preps the Playwright chromium browser.
#>

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Green
Write-Host " ForgeAgent V1: Automated Environment Setup (Windows)" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

$RootPath = Resolve-Path "$PSScriptRoot\.."

# 1. Check Python / uv
Write-Host "`n[1/4] Checking Python runtime..." -ForegroundColor Cyan
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Host "uv detected. Ensuring Python 3.12 runtime..."
    uv python install 3.12
} else {
    Write-Host "uv not found on PATH. Attempting winget install of astral-sh.uv..."
    winget install --id astral-sh.uv --silent --accept-package-agreements --accept-source-agreements --scope user
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","User") + ";" + [System.Environment]::GetEnvironmentVariable("Path","Machine")
    uv python install 3.12
}

# 2. Setup Backend Virtual Environment
Write-Host "`n[2/4] Setting up backend dependencies..." -ForegroundColor Cyan
Set-Location "$RootPath\backend"
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment in backend\.venv..."
    uv venv --python 3.12 .venv
}
Write-Host "Installing backend packages..."
uv pip install -r requirements.txt --python .venv\Scripts\python.exe

Write-Host "Installing Playwright browser..."
.\.venv\Scripts\python -m playwright install chromium

# 3. Setup Frontend
Write-Host "`n[3/4] Installing frontend dependencies..." -ForegroundColor Cyan
Set-Location "$RootPath\frontend"
cmd /c npm install

Write-Host "`n[4/4] Building production frontend assets..." -ForegroundColor Cyan
cmd /c npm run build

# Return to root
Set-Location $RootPath
Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host " ForgeAgent V1 Setup Completed Successfully!" -ForegroundColor Green
Write-Host " Run .\scripts\start.ps1 to launch the server and dashboard." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

