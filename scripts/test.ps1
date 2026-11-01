<#
.SYNOPSIS
    ForgeAgent V1 Automated Test Suite
.DESCRIPTION
    Runs the full pytest suite (acceptance tests A - N plus the security and resilience tests).
    The live ChatGPT/Edge test (Test M) is skipped unless FORGEAGENT_LIVE_TESTS=1 is set.
#>

$ErrorActionPreference = "Stop"

$RootPath = Resolve-Path "$PSScriptRoot\.."

Write-Host "==========================================================" -ForegroundColor Green
Write-Host " Running ForgeAgent V1 Test Suite" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

Set-Location "$RootPath\backend"
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    throw "backend\.venv not found. Run scripts\setup.ps1 first."
}
& ".\.venv\Scripts\python.exe" -m pytest tests -v --tb=short

