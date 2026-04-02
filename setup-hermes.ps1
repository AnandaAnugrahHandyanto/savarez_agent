# ============================================================================
# Hermes Agent Setup Script (Windows PowerShell)
# ============================================================================
# Quick setup for developers who cloned the repo manually.
# Uses uv for fast Python provisioning and package management.
#
# Usage:
#   .\setup-hermes.ps1
#
# This script:
# 1. Installs uv if not present
# 2. Creates a virtual environment with Python 3.11 via uv
# 3. Installs all dependencies (main package + submodules)
# 4. Creates .env from template (if not exists)
# 5. Adds the hermes CLI to user PATH via Scripts folder
# 6. Runs the setup wizard (optional)
# ============================================================================

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

$PythonVersion = "3.11"

Write-Host ""
Write-Host "Hermes Agent Setup" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# Install / locate uv
# ============================================================================

Write-Host "-> Checking for uv..." -ForegroundColor Cyan

$UvCmd = $null

if (Get-Command uv -ErrorAction SilentlyContinue) {
    $UvCmd = "uv"
} elseif (Test-Path "$env:USERPROFILE\.local\bin\uv.exe") {
    $UvCmd = "$env:USERPROFILE\.local\bin\uv.exe"
} elseif (Test-Path "$env:USERPROFILE\.cargo\bin\uv.exe") {
    $UvCmd = "$env:USERPROFILE\.cargo\bin\uv.exe"
} elseif (Test-Path "$env:APPDATA\uv\bin\uv.exe") {
    $UvCmd = "$env:APPDATA\uv\bin\uv.exe"
}

if ($UvCmd) {
    $UvVersion = & $UvCmd --version 2>$null
    Write-Host "OK uv found ($UvVersion)" -ForegroundColor Green
} else {
    Write-Host "-> Installing uv..." -ForegroundColor Cyan
    try {
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression

        # Refresh PATH for current session
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" + $env:PATH

        foreach ($candidate in @(
            "$env:APPDATA\uv\bin\uv.exe",
            "$env:USERPROFILE\.local\bin\uv.exe",
            "$env:USERPROFILE\.cargo\bin\uv.exe"
        )) {
            if (Test-Path $candidate) {
                $UvCmd = $candidate
                break
            }
        }

        if (-not $UvCmd -and (Get-Command uv -ErrorAction SilentlyContinue)) {
            $UvCmd = "uv"
        }

        if ($UvCmd) {
            $UvVersion = & $UvCmd --version 2>$null
            Write-Host "OK uv installed ($UvVersion)" -ForegroundColor Green
        } else {
            Write-Host "FAIL uv installed but not found. Open a new terminal and retry." -ForegroundColor Red
            exit 1
        }
    } catch {
        Write-Host "FAIL Failed to install uv. Visit https://docs.astral.sh/uv/" -ForegroundColor Red
        exit 1
    }
}

# ============================================================================
# Python check (uv can provision it automatically)
# ============================================================================

Write-Host "-> Checking Python $PythonVersion..." -ForegroundColor Cyan

$PythonPath = & $UvCmd python find $PythonVersion 2>$null
if ($PythonPath) {
    $PythonFoundVersion = & $PythonPath --version 2>$null
    Write-Host "OK $PythonFoundVersion found" -ForegroundColor Green
} else {
    Write-Host "-> Python $PythonVersion not found, installing via uv..." -ForegroundColor Cyan
    & $UvCmd python install $PythonVersion
    $PythonPath = & $UvCmd python find $PythonVersion 2>$null
    $PythonFoundVersion = & $PythonPath --version 2>$null
    Write-Host "OK $PythonFoundVersion installed" -ForegroundColor Green
}

# ============================================================================
# Virtual environment
# ============================================================================

Write-Host "-> Setting up virtual environment..." -ForegroundColor Cyan

if (Test-Path "venv") {
    Write-Host "-> Removing old venv..." -ForegroundColor Cyan
    Remove-Item -Recurse -Force "venv"
}

& $UvCmd venv venv --python $PythonVersion
Write-Host "OK venv created (Python $PythonVersion)" -ForegroundColor Green

$env:VIRTUAL_ENV = "$ScriptDir\venv"

# ============================================================================
# Dependencies
# ============================================================================

Write-Host "-> Installing dependencies..." -ForegroundColor Cyan

if (Test-Path "uv.lock") {
    Write-Host "-> Using uv.lock for hash-verified installation..." -ForegroundColor Cyan
    $env:UV_PROJECT_ENVIRONMENT = "$ScriptDir\venv"
    & $UvCmd sync --all-extras --locked 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "OK Dependencies installed (lockfile verified)" -ForegroundColor Green
    } else {
        Write-Host "WARN Lockfile install failed (may be outdated), falling back to pip install..." -ForegroundColor Yellow
        & $UvCmd pip install -e ".[all]"
        if ($LASTEXITCODE -ne 0) {
            & $UvCmd pip install -e "."
        }
        Write-Host "OK Dependencies installed" -ForegroundColor Green
    }
} else {
    & $UvCmd pip install -e ".[all]"
    if ($LASTEXITCODE -ne 0) {
        & $UvCmd pip install -e "."
    }
    Write-Host "OK Dependencies installed" -ForegroundColor Green
}

# ============================================================================
# Submodules (terminal backend + RL training)
# ============================================================================

Write-Host "-> Installing optional submodules..." -ForegroundColor Cyan

if ((Test-Path "tinker-atropos") -and (Test-Path "tinker-atropos\pyproject.toml")) {
    & $UvCmd pip install -e ".\tinker-atropos"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "OK tinker-atropos installed" -ForegroundColor Green
    } else {
        Write-Host "WARN tinker-atropos install failed (RL tools may not work)" -ForegroundColor Yellow
    }
} else {
    Write-Host "WARN tinker-atropos not found (run: git submodule update --init --recursive)" -ForegroundColor Yellow
}

# ============================================================================
# Optional: ripgrep (for faster file search)
# ============================================================================

Write-Host "-> Checking ripgrep (optional, for faster search)..." -ForegroundColor Cyan

if (Get-Command rg -ErrorAction SilentlyContinue) {
    Write-Host "OK ripgrep found" -ForegroundColor Green
} else {
    Write-Host "WARN ripgrep not found (file search will use grep fallback)" -ForegroundColor Yellow
    $installRg = Read-Host "Install ripgrep for faster search? [Y/n]"
    if ($installRg -eq "" -or $installRg -match "^[Yy]") {
        $installed = $false

        if (Get-Command winget -ErrorAction SilentlyContinue) {
            winget install BurntSushi.ripgrep.MSVC --silent
            if ($LASTEXITCODE -eq 0) { $installed = $true }
        }

        if (-not $installed -and (Get-Command scoop -ErrorAction SilentlyContinue)) {
            scoop install ripgrep
            if ($LASTEXITCODE -eq 0) { $installed = $true }
        }

        if (-not $installed -and (Get-Command choco -ErrorAction SilentlyContinue)) {
            choco install ripgrep -y
            if ($LASTEXITCODE -eq 0) { $installed = $true }
        }

        if (-not $installed -and (Get-Command cargo -ErrorAction SilentlyContinue)) {
            Write-Host "-> Trying cargo install (no admin required)..." -ForegroundColor Cyan
            cargo install ripgrep
            if ($LASTEXITCODE -eq 0) { $installed = $true }
        }

        if ($installed) {
            Write-Host "OK ripgrep installed" -ForegroundColor Green
        } else {
            Write-Host "WARN Auto-install failed. Install options:" -ForegroundColor Yellow
            Write-Host "    winget install BurntSushi.ripgrep.MSVC"
            Write-Host "    scoop install ripgrep"
            Write-Host "    choco install ripgrep"
            Write-Host "    cargo install ripgrep"
            Write-Host "    https://github.com/BurntSushi/ripgrep#installation"
        }
    }
}

# ============================================================================
# Environment file
# ============================================================================

if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "OK Created .env from template" -ForegroundColor Green
    }
} else {
    Write-Host "OK .env exists" -ForegroundColor Green
}

# ============================================================================
# PATH setup — add venv\Scripts to user PATH
# ============================================================================

Write-Host "-> Setting up hermes command..." -ForegroundColor Cyan

$VenvScripts = "$ScriptDir\venv\Scripts"
$UserPath = [System.Environment]::GetEnvironmentVariable("PATH", "User")

if ($UserPath -notlike "*$VenvScripts*") {
    [System.Environment]::SetEnvironmentVariable(
        "PATH",
        "$VenvScripts;$UserPath",
        "User"
    )
    $env:PATH = "$VenvScripts;$env:PATH"
    Write-Host "OK Added venv\Scripts to user PATH" -ForegroundColor Green
} else {
    Write-Host "OK venv\Scripts already on PATH" -ForegroundColor Green
}

# ============================================================================
# Seed bundled skills into %USERPROFILE%\.hermes\skills\
# ============================================================================

$HermesHome = if ($env:HERMES_HOME) { $env:HERMES_HOME } else { "$env:USERPROFILE\.hermes" }
$HermesSkillsDir = "$HermesHome\skills"

if (-not (Test-Path $HermesSkillsDir)) {
    New-Item -ItemType Directory -Force -Path $HermesSkillsDir | Out-Null
}

Write-Host ""
Write-Host "Syncing bundled skills to $HermesSkillsDir ..."

$syncResult = & "$ScriptDir\venv\Scripts\python.exe" "$ScriptDir\tools\skills_sync.py" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "OK Skills synced" -ForegroundColor Green
} else {
    if (Test-Path "$ScriptDir\skills") {
        # Copy only files that don't already exist (emulate cp -rn)
        Get-ChildItem "$ScriptDir\skills" -Recurse | ForEach-Object {
            $dest = $_.FullName.Replace("$ScriptDir\skills", $HermesSkillsDir)
            if (-not (Test-Path $dest)) {
                $destDir = Split-Path $dest
                if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Force -Path $destDir | Out-Null }
                Copy-Item $_.FullName $dest
            }
        }
        Write-Host "OK Skills copied" -ForegroundColor Green
    }
}

# ============================================================================
# Done
# ============================================================================

Write-Host ""
Write-Host "OK Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host ""
Write-Host "  1. Restart your terminal (or open a new PowerShell window) to pick up PATH changes."
Write-Host ""
Write-Host "  2. Run the setup wizard to configure API keys:"
Write-Host "     hermes setup"
Write-Host ""
Write-Host "  3. Start chatting:"
Write-Host "     hermes"
Write-Host ""
Write-Host "Other commands:"
Write-Host "  hermes status          # Check configuration"
Write-Host "  hermes gateway install # Install gateway service (messaging + cron)"
Write-Host "  hermes cron list       # View scheduled jobs"
Write-Host "  hermes doctor          # Diagnose issues"
Write-Host ""

$runWizard = Read-Host "Would you like to run the setup wizard now? [Y/n]"
if ($runWizard -eq "" -or $runWizard -match "^[Yy]") {
    Write-Host ""
    & "$ScriptDir\venv\Scripts\python.exe" -m hermes_cli.main setup
}
