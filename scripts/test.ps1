<#
.SYNOPSIS
    ForgeAgent V1 Automated Acceptance Test Suite (Tests A - L)
.DESCRIPTION
    Runs all 12 mandatory end-to-end acceptance tests via pytest.
#>

$ErrorActionPreference = "Stop"

$RootPath = Resolve-Path "$PSScriptRoot\.."

Write-Host "==========================================================" -ForegroundColor Green
Write-Host " Running ForgeAgent V1 Mandatory Acceptance Tests (A - L)" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

Set-Location "$RootPath\backend"
& ".\.venv\Scripts\python.exe" -m pytest tests -v --tb=short

