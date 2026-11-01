<#
.SYNOPSIS
    Builds a clean, shareable ForgeAgent zip (ForgeAgent-share.zip) next to the project folder.
.DESCRIPTION
    Copies only the source files into a temporary folder, leaving out everything private or machine-specific
    (browser logins, databases, chats, API keys, virtual environment, node_modules, git history, agent
    workspace). It then checks the result and refuses to finish if anything private slipped in.
    See WHAT_NOT_TO_SEND.md for the reasons behind each exclusion.
#>
param(
    [string]$OutDir = (Split-Path -Parent (Resolve-Path "$PSScriptRoot\..").Path)
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path "$PSScriptRoot\..").Path
$ZipPath = Join-Path $OutDir "ForgeAgent-share.zip"
$Staging = Join-Path ([System.IO.Path]::GetTempPath()) ("forgeagent_share_" + [guid]::NewGuid().ToString("N").Substring(0, 8))
$Inner = Join-Path $Staging "ForgeAgent"

Write-Host "Building a shareable copy of ForgeAgent..." -ForegroundColor Cyan
New-Item -ItemType Directory -Path $Inner -Force | Out-Null

# Folders that must never be shared (full paths)
$excludeDirs = @(
    "$Root\backend\data",          # browser logins, database, chats
    "$Root\backend\.venv",         # machine-specific Python environment
    "$Root\frontend\node_modules", # rebuilt by SETUP.bat
    "$Root\frontend\dist",         # rebuilt by SETUP.bat
    "$Root\workspace",             # your personal agent output
    "$Root\.git",                  # full change history
    "$Root\.remember"
)
# Folder names to skip anywhere
$excludeDirNames = @("__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".vite")
# Files to skip anywhere
$excludeFiles = @(
    "*.pyc", "*.log", ".env", "*.db", "*.db-journal", "*.sqlite", "*.sqlite3",
    "studio_sessions.json", "*.zip",
    "START EDGE.bat", "STARTFRONTEND.bat",   # duplicates of START_EDGE.bat / START_FRONTEND.bat
    "WHAT_NOT_TO_SEND.md"                    # notes for the sender, not the receiver
)

$args = @($Root, $Inner, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/NP", "/XD") + $excludeDirs + $excludeDirNames + @("/XF") + $excludeFiles
& robocopy @args | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy failed with exit code $LASTEXITCODE" }

# The app expects these folders to exist
New-Item -ItemType Directory -Path "$Inner\workspace" -Force | Out-Null
Set-Content -Path "$Inner\workspace\README.txt" -Value "ForgeAgent saves the files it creates for you in this folder." -Encoding UTF8

# Safety check: refuse to build if anything private slipped in
$forbidden = Get-ChildItem -Path $Inner -Recurse -Force -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -in @("browser_profile", "edge_profile", "forgeagent.db", "studio_sessions.json", ".env", ".venv", "node_modules", ".git", "data") -or
    $_.Extension -in @(".db", ".sqlite", ".sqlite3", ".log", ".pyc")
}
if ($forbidden) {
    $forbidden | ForEach-Object { Write-Host "  PRIVATE FILE FOUND: $($_.FullName)" -ForegroundColor Red }
    Remove-Item -Recurse -Force $Staging
    throw "Stopped: private files would have been included. Nothing was zipped."
}

if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($Staging, $ZipPath, [System.IO.Compression.CompressionLevel]::Optimal, $false)

$fileCount = (Get-ChildItem -Path $Inner -Recurse -File -Force).Count
Remove-Item -Recurse -Force $Staging
$sizeMb = [math]::Round((Get-Item $ZipPath).Length / 1MB, 2)

Write-Host ""
Write-Host "No private files found in the zip." -ForegroundColor Green
Write-Host "Created: $ZipPath  ($fileCount files, $sizeMb MB)" -ForegroundColor Green
Write-Host "Send that file. The other person starts with SETUP_GUIDE.md inside it." -ForegroundColor Green
