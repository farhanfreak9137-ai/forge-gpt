<#
.SYNOPSIS
    ForgeAgent V1 Microsoft Edge ChatGPT Launcher
.DESCRIPTION
    Launches the Playwright Microsoft Edge adapter to chat with ChatGPT directly.
.EXAMPLE
    .\scripts\chat_edge.ps1 "Write a quicksort function in Python"
    .\scripts\chat_edge.ps1 --headless "Hello"
    .\scripts\chat_edge.ps1
#>

$ErrorActionPreference = "Stop"

$RootPath = Resolve-Path "$PSScriptRoot\.."
$PythonExe = "$RootPath\backend\.venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    Write-Host "Error: Virtual environment not found at backend\.venv." -ForegroundColor Red
    Write-Host "Please run .\scripts\setup.ps1 first." -ForegroundColor Yellow
    exit 1
}

& $PythonExe "$RootPath\scripts\chat_edge.py" @args

