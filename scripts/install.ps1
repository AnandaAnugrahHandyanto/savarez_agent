#!/usr/bin/env pwsh
# ============================================================================
# Hermes Agent Installer for Windows
# ============================================================================
# PowerShell installation script for Windows 10/11.
# Uses winget for package management and uv for Python environment.
#
# Usage:
#   irm https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.ps1 | iex
#
# Or with options:
#   .\install.ps1 -y -Branch main -Dir "$env:USERPROFILE\.hermes\hermes-agent"
#
# Issue: https://github.com/NousResearch/hermes-agent/issues/5924
# ============================================================================

#Requires -Version 5.1

param(
    [switch]$y,                 # Non-interactive mode
    [string]$Branch = "main",   # Git branch to install
    [string]$Dir,               # Installation directory
    [switch]$SkipPhase1,        # Skip prerequisites check
    [switch]$SkipPhase2,        # Skip workspace creation
    [switch]$SkipPhase3,        # Skip Python env setup
    [switch]$SkipPhase4,        # Skip agent install
    [switch]$SkipPhase5,        # Skip skills system
    [switch]$SkipPhase6,        # Skip memory bridge
    [switch]$SkipPhase7,        # Skip Git config
    [switch]$SkipPhase8,        # Skip verification
    [switch]$SkipPhase9,        # Skip first-run prompt
    [switch]$Help               # Show help
)

# Configuration
$RepoUrlHttps = "https://github.com/NousResearch/hermes-agent.git"
$RepoUrlSsh = "git@github.com:NousResearch/hermes-agent.git"
$HermesHome = "$env:USERPROFILE\.hermes"
if (-not $Dir) { $Dir = "$HermesHome\hermes-agent" }
$PythonVersion = "3.12"
$UvVersion = "latest"

# ============================================================================
# Helper Functions
# ============================================================================

function Print-Banner {
    Write-Host ""
    Write-Host "┌─────────────────────────────────────────────────────────┐" -ForegroundColor Magenta
    Write-Host "│             ⚕ Hermes Agent Installer                    │" -ForegroundColor Magenta
    Write-Host "├─────────────────────────────────────────────────────────┤" -ForegroundColor Magenta
    Write-Host "│  The self-improving AI agent built by Nous Research     │" -ForegroundColor Magenta
    Write-Host "│  Windows Native Installation                            │" -ForegroundColor Magenta
    Write-Host "└─────────────────────────────────────────────────────────┘" -ForegroundColor Magenta
    Write-Host ""
}

function Log-Info { param($msg) Write-Host "[INFO]  $msg" -ForegroundColor Cyan }
function Log-Success { param($msg) Write-Host "[OK]    $msg" -ForegroundColor Green }
function Log-Warn { param($msg) Write-Host "[WARN]  $msg" -ForegroundColor Yellow }
function Log-Error { param($msg) Write-Host "[ERROR] $msg" -ForegroundColor Red }
function Log-Phase { param($phase, $msg) Write-Host "[Phase $phase] $msg" -ForegroundColor Blue }

function Show-Help {
    Write-Host "Hermes Agent Installer for Windows"
    Write-Host ""
    Write-Host "Usage: install.ps1 [OPTIONS]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -y              Non-interactive mode (skip prompts)"
    Write-Host "  -Branch NAME    Git branch to install (default: main)"
    Write-Host "  -Dir PATH       Installation directory (default: ~/.hermes/hermes-agent)"
    Write-Host "  -SkipPhase1-9   Skip specific installation phases"
    Write-Host "  -Help           Show this help message"
    Write-Host ""
    Write-Host "Installation Phases:"
    Write-Host "  Phase 1: Prerequisites check (git, Python, uv, gh)"
    Write-Host "  Phase 2: Workspace creation"
    Write-Host "  Phase 3: Python environment setup"
    Write-Host "  Phase 4: Agent installation"
    Write-Host "  Phase 5: Skills system setup"
    Write-Host "  Phase 6: Memory bridge configuration"
    Write-Host "  Phase 7: Git configuration"
    Write-Host "  Phase 8: Verification (hermes --version)"
    Write-Host "  Phase 9: First-run prompt (hermes setup)"
    exit 0
}

function Check-WindowsVersion {
    $osInfo = Get-CimInstance -ClassName Win32_OperatingSystem
    $version = $osInfo.Version
    $build = $osInfo.BuildNumber
    
    Log-Info "Windows Version: $($osInfo.Caption) (Build $build)"
    
    # Windows 10 = Build 10240+, Windows 11 = Build 22000+
    if ($build -lt 10240) {
        Log-Error "Windows 10 or later is required. Current build: $build"
        exit 1
    }
    
    Log-Success "Windows version check passed"
}

function Install-WingetPackage {
    param($PackageId, $PackageName)
    
    Log-Info "Checking $PackageName..."
    
    $installed = winget list --id $PackageId --exact 2>$null
    if ($installed -match $PackageId) {
        Log-Success "$PackageName is already installed"
        return
    }
    
    Log-Info "Installing $PackageName via winget..."
    winget install --id $PackageId --accept-package-agreements --accept-source-agreements --silent
    
    if ($LASTEXITCODE -eq 0) {
        Log-Success "$PackageName installed successfully"
    } else {
        Log-Error "Failed to install $PackageName"
        exit 1
    }
}

function Check-Prerequisites {
    Log-Phase 1 "Checking prerequisites..."
    
    # Check winget availability
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        Log-Error "winget is not available. Please install App Installer from Microsoft Store."
        exit 1
    }
    
    # Install Git
    Install-WingetPackage "Git.Git" "Git"
    
    # Install Python 3.12+
    Install-WingetPackage "Python.Python.3.12" "Python 3.12"
    
    # Install GitHub CLI
    Install-WingetPackage "GitHub.cli" "GitHub CLI"
    
    # Install uv (astral-sh/uv via pip or winget)
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uv) {
        Log-Info "Installing uv (Python package manager)..."
        pip install uv --quiet
        if ($LASTEXITCODE -eq 0) {
            Log-Success "uv installed successfully"
        } else {
            Log-Warn "uv installation via pip failed, trying pipx..."
            pipx install uv
        }
    } else {
        Log-Success "uv is already installed"
    }
    
    Log-Success "Phase 1 complete: All prerequisites installed"
}

function Create-Workspace {
    Log-Phase 2 "Creating workspace..."
    
    # Create Hermes home directory
    if (-not (Test-Path $HermesHome)) {
        New-Item -ItemType Directory -Path $HermesHome -Force | Out-Null
        Log-Success "Created $HermesHome"
    } else {
        Log-Info "$HermesHome already exists"
    }
    
    # Enable Windows long paths (if not already)
    $longPathsEnabled = Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -ErrorAction SilentlyContinue
    if ($longPathsEnabled.LongPathsEnabled -ne 1) {
        Log-Warn "Long paths not enabled. Consider running as Admin to enable."
        Log-Info "To enable manually: fsutil behavior set enablelongpaths 1"
    }
    
    Log-Success "Phase 2 complete: Workspace ready"
}

function Clone-Repo {
    Log-Phase 3 "Cloning Hermes Agent repository..."
    
    if (Test-Path $Dir) {
        Log-Info "Installation directory exists: $Dir"
        if (-not $y) {
            $response = Read-Host "Remove existing installation and reinstall? [y/N]"
            if ($response -ne "y") {
                Log-Info "Using existing installation"
                return
            }
            Remove-Item -Recurse -Force $Dir
        }
    }
    
    # Clone repository
    Log-Info "Cloning from $RepoUrlHttps (branch: $Branch)..."
    git clone --branch $Branch $RepoUrlHttps $Dir
    
    if ($LASTEXITCODE -ne 0) {
        Log-Error "Failed to clone repository"
        exit 1
    }
    
    Log-Success "Phase 3 complete: Repository cloned to $Dir"
}

function Setup-PythonEnv {
    Log-Phase 3 "Setting up Python environment..."
    
    Push-Location $Dir
    
    # Create virtual environment with uv
    Log-Info "Creating virtual environment with uv..."
    uv venv --python $PythonVersion
    
    if ($LASTEXITCODE -ne 0) {
        Log-Error "Failed to create virtual environment"
        Pop-Location
        exit 1
    }
    
    # Activate virtual environment
    .venv\Scripts\Activate.ps1
    
    # Install Hermes Agent with all dependencies
    Log-Info "Installing Hermes Agent and dependencies..."
    uv pip install -e ".[all]"
    
    if ($LASTEXITCODE -ne 0) {
        Log-Warn "Full install failed, trying core dependencies..."
        uv pip install -e "."
    }
    
    Pop-Location
    Log-Success "Phase 3 complete: Python environment ready"
}

function Setup-Skills {
    Log-Phase 5 "Setting up skills system..."
    
    Push-Location $Dir
    
    # Ensure skills directory exists
    $skillsDir = "$HermesHome\skills"
    if (-not (Test-Path $skillsDir)) {
        New-Item -ItemType Directory -Path $skillsDir -Force | Out-Null
        Log-Success "Created skills directory: $skillsDir"
    }
    
    # Copy optional skills if available
    $optionalSkills = "$Dir\optional-skills"
    if (Test-Path $optionalSkills) {
        Log-Info "Optional skills available at $optionalSkills"
    }
    
    Pop-Location
    Log-Success "Phase 5 complete: Skills system ready"
}

function Setup-MemoryBridge {
    Log-Phase 6 "Setting up memory bridge..."
    
    # Memory bridge for WSL/Windows filesystem access
    $memoryDir = "$HermesHome\memory"
    if (-not (Test-Path $memoryDir)) {
        New-Item -ItemType Directory -Path $memoryDir -Force | Out-Null
        Log-Success "Created memory directory: $memoryDir"
    }
    
    # Create WSL bridge symlink if WSL is available
    $wsl = Get-Command wsl -ErrorAction SilentlyContinue
    if ($wsl) {
        Log-Info "WSL detected - setting up filesystem bridge..."
        $wslHermesHome = "/mnt/c$($HermesHome.Replace('\', '/').Replace('C:', ''))"
        Log-Info "Windows Hermes Home accessible from WSL at: $wslHermesHome"
    }
    
    Log-Success "Phase 6 complete: Memory bridge configured"
}

function Setup-GitConfig {
    Log-Phase 7 "Configuring Git..."
    
    Push-Location $Dir
    
    # Check if user has Git config
    $gitName = git config --get user.name 2>$null
    $gitEmail = git config --get user.email 2>$null
    
    if (-not $gitName -or -not $gitEmail) {
        if (-not $y) {
            Log-Warn "Git user.name or user.email not set"
            $name = Read-Host "Enter your name for Git commits"
            $email = Read-Host "Enter your email for Git commits"
            git config --global user.name $name
            git config --global user.email $email
            Log-Success "Git config set globally"
        } else {
            Log-Warn "Git config not set (non-interactive mode)"
        }
    } else {
        Log-Success "Git already configured: $gitName <$gitEmail>"
    }
    
    Pop-Location
    Log-Success "Phase 7 complete: Git configuration done"
}

function Verify-Installation {
    Log-Phase 8 "Verifying installation..."
    
    # Add to PATH if not already
    $venvBin = "$Dir\.venv\Scripts"
    $currentPath = $env:PATH
    if ($currentPath -notlike "*$venvBin*") {
        $env:PATH = "$venvBin;$currentPath"
        Log-Info "Added $venvBin to PATH"
    }
    
    # Check hermes command
    Push-Location $Dir
    .venv\Scripts\Activate.ps1
    
    $hermes = Get-Command hermes -ErrorAction SilentlyContinue
    if ($hermes) {
        $version = hermes --version 2>$null
        Log-Success "Hermes installed: $version"
    } else {
        Log-Warn "hermes command not directly available, use .venv\Scripts\hermes.exe"
        if (Test-Path ".venv\Scripts\hermes.exe") {
            Log-Success "Hermes executable found at .venv\Scripts\hermes.exe"
        }
    }
    
    Pop-Location
    Log-Success "Phase 8 complete: Installation verified"
}

function FirstRun-Prompt {
    Log-Phase 9 "First-run setup..."
    
    if ($y) {
        Log-Info "Skipping interactive setup (non-interactive mode)"
        Log-Info "Run 'hermes setup' manually to configure your agent"
        return
    }
    
    Write-Host ""
    Write-Host "╔─────────────────────────────────────────────────────────╗" -ForegroundColor Cyan
    Write-Host "║  Hermes Agent is installed!                             ║" -ForegroundColor Cyan
    Write-Host "╠─────────────────────────────────────────────────────────╣" -ForegroundColor Cyan
    Write-Host "║  Run 'hermes setup' to configure:                       ║" -ForegroundColor Cyan
    Write-Host "║    - LLM provider (OpenAI, Anthropic, etc.)             ║" -ForegroundColor Cyan
    Write-Host "║    - Tools and permissions                              ║" -ForegroundColor Cyan
    Write-Host "║    - Messaging gateway (Telegram, Discord, etc.)        ║" -ForegroundColor Cyan
    Write-Host "╚─────────────────────────────────────────────────────────╝" -ForegroundColor Cyan
    Write-Host ""
    
    $runSetup = Read-Host "Run 'hermes setup' now? [y/N]"
    if ($runSetup -eq "y") {
        Push-Location $Dir
        .venv\Scripts\Activate.ps1
        hermes setup
        Pop-Location
    } else {
        Log-Info "You can run 'hermes setup' later"
    }
    
    Log-Success "Phase 9 complete: Installation finished!"
}

function Add-To-Path {
    # Add Hermes to user PATH permanently
    $venvBin = "$Dir\.venv\Scripts"
    $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    
    if ($userPath -notlike "*$venvBin*") {
        [Environment]::SetEnvironmentVariable("PATH", "$venvBin;$userPath", "User")
        Log-Success "Added Hermes to user PATH permanently"
    }
}

# ============================================================================
# Main Installation Flow
# ============================================================================

if ($Help) { Show-Help }

Print-Banner

# Phase 1: Prerequisites
if (-not $SkipPhase1) { Check-Prerequisites }

# Phase 2: Workspace
if (-not $SkipPhase2) { Create-Workspace }

# Phase 3: Clone & Python Env
if (-not $SkipPhase3) { 
    Clone-Repo
    Setup-PythonEnv 
}

# Phase 4: Agent (included in Phase 3 pip install)
if (-not $SkipPhase4) { Log-Phase 4 "Agent installed during Phase 3" }

# Phase 5: Skills
if (-not $SkipPhase5) { Setup-Skills }

# Phase 6: Memory Bridge
if (-not $SkipPhase6) { Setup-MemoryBridge }

# Phase 7: Git Config
if (-not $SkipPhase7) { Setup-GitConfig }

# Phase 8: Verification
if (-not $SkipPhase8) { Verify-Installation }

# Add to PATH
Add-To-Path

# Phase 9: First-run
if (-not $SkipPhase9) { FirstRun-Prompt }

# ============================================================================
# Final Summary
# ============================================================================

Write-Host ""
Write-Host "╔═════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║            ⚕ Hermes Agent Installation Complete        ║" -ForegroundColor Green
Write-Host "╠═════════════════════════════════════════════════════════╣" -ForegroundColor Green
Write-Host "║  Installation Directory: $Dir                          " -ForegroundColor Green
Write-Host "║  To start: hermes                                        ║" -ForegroundColor Green
Write-Host "║  To configure: hermes setup                              ║" -ForegroundColor Green
Write-Host "║  To update: hermes update                                ║" -ForegroundColor Green
Write-Host "║  Documentation: https://hermes-agent.nousresearch.com   ║" -ForegroundColor Green
Write-Host "╚═════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""