<#
.SYNOPSIS
    AEON v3.0 — Universal Meaning Translator
    Installation script for Windows (PowerShell 5.1+)

.DESCRIPTION
    Downloads project from GitHub, installs Python dependencies,
    and configures the environment for first launch.

.EXAMPLE
    .\install.ps1
    .\install.ps1 -PythonPath "C:\Python311\python.exe"
    .\install.ps1 -SkipPythonCheck
#>

param(
    [string]$PythonPath = "python",
    [switch]$SkipPythonCheck = $false,
    [string]$Branch = "main",
    [string]$RepoUrl = "https://github.com/abonent0007/aeon_translator/releases/download/AEON/main.zip",
    [switch]$LocalOnly = $false
)

$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "AEON v3.0 Installer"

Write-Host @"
============================================================
        AEON v3.0 — Universal Meaning Translator
                 INSTALLER
============================================================
"@ -ForegroundColor Cyan

# ============================================
# 1. Check Python
# ============================================
if (-not $SkipPythonCheck) {
    Write-Host "[1/5] Checking Python..." -ForegroundColor Yellow
    try {
        $pyVersion = & $PythonPath --version 2>&1
        Write-Host "  OK: $pyVersion" -ForegroundColor Green
    } catch {
        Write-Host "  ERROR: Python not found at '$PythonPath'" -ForegroundColor Red
        Write-Host "  Install Python 3.8+ from https://www.python.org/downloads/" -ForegroundColor Yellow
        Write-Host "  Or specify path: .\install.ps1 -PythonPath 'C:\Python311\python.exe'" -ForegroundColor Yellow
        exit 1
    }

    # Check version >= 3.8
    $verStr = (& $PythonPath -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')") 2>&1
    $major, $minor = $verStr.Split('.')
    if ([int]$major -lt 3 -or ([int]$major -eq 3 -and [int]$minor -lt 8)) {
        Write-Host "  ERROR: Python 3.8+ required. You have $verStr" -ForegroundColor Red
        exit 1
    }
    Write-Host "  Version $verStr OK" -ForegroundColor Green
}

# ============================================
# 2. Download / locate project
# ============================================
$projectDir = Join-Path (Get-Location) "aeon_translator"

if ($LocalOnly) {
    Write-Host "[2/5] Using local project directory..." -ForegroundColor Yellow
    if (-not (Test-Path ".\aeon\__init__.py")) {
        Write-Host "  ERROR: Run this script from the project root (where aeon/ folder is)" -ForegroundColor Red
        exit 1
    }
    $projectDir = Get-Location
} elseif (Test-Path ".\aeon\__init__.py") {
    Write-Host "[2/5] Project already present, using local copy..." -ForegroundColor Yellow
    $projectDir = Get-Location
} else {
    Write-Host "[2/5] Downloading project from GitHub..." -ForegroundColor Yellow
    try {
        $zipPath = Join-Path $env:TEMP "aeon_translator.zip"
        Write-Host "  Downloading $RepoUrl ..."
        Invoke-WebRequest -Uri $RepoUrl -OutFile $zipPath -UseBasicParsing
        Write-Host "  Extracting..." -ForegroundColor Yellow
        Expand-Archive -Path $zipPath -DestinationPath $env:TEMP -Force
        $extracted = Get-ChildItem "$env:TEMP\aeon_translator-*" -Directory | Select-Object -First 1
        if ($extracted) {
            Move-Item $extracted.FullName $projectDir -Force
        }
        Remove-Item $zipPath -Force
        Write-Host "  OK: Project at $projectDir" -ForegroundColor Green
    } catch {
        Write-Host "  Download failed. If you already have the project, use -LocalOnly" -ForegroundColor Red
        Write-Host "  Error: $_" -ForegroundColor Red
        exit 1
    }
}

Set-Location $projectDir

# ============================================
# 3. Create virtual environment (optional, recommended)
# ============================================
Write-Host "[3/5] Setting up virtual environment..." -ForegroundColor Yellow
$venvDir = Join-Path $projectDir ".venv"
if (-not (Test-Path $venvDir)) {
    & $PythonPath -m venv $venvDir 2>&1 | Out-Null
    Write-Host "  Created .venv" -ForegroundColor Green
} else {
    Write-Host "  .venv already exists" -ForegroundColor Green
}

# Activate venv
if ($IsWindows -or $env:OS) {
    $pythonExe = Join-Path $venvDir "Scripts\python.exe"
    $pipExe = Join-Path $venvDir "Scripts\pip.exe"
} else {
    $pythonExe = Join-Path $venvDir "bin\python"
    $pipExe = Join-Path $venvDir "bin\pip"
}

# ============================================
# 4. Install dependencies
# ============================================
Write-Host "[4/5] Installing Python dependencies..." -ForegroundColor Yellow
Write-Host "  This may take 5-15 minutes on first run..."

try {
    & $pythonExe -m pip install --upgrade pip -q 2>&1 | Out-Null
    & $pipExe install -r requirements.txt 2>&1 | ForEach-Object {
        if ($_ -match "Successfully|already") { Write-Host "  $_" -ForegroundColor Green }
    }
    Write-Host "  Dependencies installed!" -ForegroundColor Green
} catch {
    Write-Host "  ERROR installing dependencies: $_" -ForegroundColor Red
    Write-Host "  Try manually: pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

# ============================================
# 5. Configure .env
# ============================================
Write-Host "[5/5] Configuring environment..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "  Created .env from .env.example" -ForegroundColor Green
        Write-Host "  EDIT .env to add your API keys!" -ForegroundColor Yellow
    } else {
        @"
# AEON Universal Translator — API Keys
# Get your keys:
#   DeepSeek: https://platform.deepseek.com
#   Flux:     https://gen-api.ru

DEEPSEEK_API_KEY=your_deepseek_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

FLUX_API_KEY=your_flux_key_here
FLUX_API_URL=https://api.gen-api.ru/api/v1/networks/flux-2
"@ | Out-File -FilePath ".env" -Encoding UTF8
        Write-Host "  Created .env with placeholders" -ForegroundColor Green
        Write-Host "  EDIT .env to add your API keys!" -ForegroundColor Yellow
    }
} else {
    Write-Host "  .env already exists" -ForegroundColor Green
}

# ============================================
# Done
# ============================================
Write-Host @"

============================================================
    INSTALLATION COMPLETE!
============================================================

  Next steps:
    1. Edit .env — add your API keys
    2. Launch web server: run_web.bat
       or: .venv\Scripts\python -m aeon.web_server
    3. Open http://localhost:8080

  Without API keys, AEON runs in rule-based mode
  (basic functionality, no LLM features).

============================================================
"@ -ForegroundColor Cyan

# Offer to launch
$launch = Read-Host "Launch web server now? (y/n)"
if ($launch -eq 'y') {
    if (Test-Path "run_web.bat") {
        Start-Process "run_web.bat"
    } else {
        & $pythonExe -m aeon.web_server
    }
}
