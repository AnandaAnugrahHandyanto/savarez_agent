# Import a Hermes Windows host migration bundle.
#
# Secrets are never restored unless -RestoreSecrets is explicitly supplied.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$MigrationPath,
    [string]$HermesHome = "",
    [string]$AgentRoot = "",
    [string]$WebUiRoot = "",
    [switch]$RestoreSecrets,
    [switch]$InstallAutostart,
    [switch]$StartAfterImport,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Content
    )
    $parent = Split-Path -Parent $Path
    if ($parent) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    [System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($false))
}

function Backup-And-Copy {
    param(
        [string]$Source,
        [string]$Destination,
        [string]$BackupRoot
    )
    if (-not (Test-Path -LiteralPath $Source)) {
        return $false
    }
    $parent = Split-Path -Parent $Destination
    if ($parent) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    if ((Test-Path -LiteralPath $Destination) -and -not $Force) {
        $backupPath = Join-Path $BackupRoot ($Destination -replace "[:\\]", "_")
        New-Item -ItemType Directory -Path (Split-Path -Parent $backupPath) -Force | Out-Null
        Copy-Item -LiteralPath $Destination -Destination $backupPath -Force
        Write-Host "Backed up existing file: $Destination -> $backupPath"
    }
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
    Write-Host "Restored: $Destination"
    return $true
}

function Resolve-BundleRoot {
    param([string]$Path)
    $resolved = Resolve-Path -LiteralPath $Path
    $source = $resolved.Path
    if ((Get-Item -LiteralPath $source).PSIsContainer) {
        return $source
    }
    if ($source.EndsWith(".zip", [System.StringComparison]::OrdinalIgnoreCase)) {
        $tempRoot = Join-Path $env:TEMP ("hermes-host-migration-" + [guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        Expand-Archive -LiteralPath $source -DestinationPath $tempRoot -Force
        return $tempRoot
    }
    throw "MigrationPath must be a directory or .zip archive: $Path"
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")
if (-not $AgentRoot) {
    $AgentRoot = $repoRoot.Path
}
if (-not $HermesHome) {
    if ($env:HERMES_HOME -and $env:HERMES_HOME.Trim()) {
        $HermesHome = $env:HERMES_HOME.Trim()
    } else {
        $HermesHome = Join-Path $env:USERPROFILE ".hermes"
    }
}
if (-not $WebUiRoot) {
    $WebUiRoot = Join-Path (Split-Path -Parent $AgentRoot) "hermes-WebUI"
}

$bundleRoot = Resolve-BundleRoot -Path $MigrationPath
$manifestPath = Join-Path $bundleRoot "manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw "Missing manifest.json in migration bundle: $bundleRoot"
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupRoot = Join-Path $HermesHome "migration\backup-before-import-$stamp"
New-Item -ItemType Directory -Path $HermesHome, $backupRoot -Force | Out-Null

$filesRoot = Join-Path $bundleRoot "files"
Backup-And-Copy -Source (Join-Path $filesRoot "hermes_home\config.yaml") -Destination (Join-Path $HermesHome "config.yaml") -BackupRoot $backupRoot | Out-Null

if ($RestoreSecrets) {
    Backup-And-Copy -Source (Join-Path $filesRoot "secrets\hermes_home\.env") -Destination (Join-Path $HermesHome ".env") -BackupRoot $backupRoot | Out-Null
    Backup-And-Copy -Source (Join-Path $filesRoot "secrets\hermes_home\auth.json") -Destination (Join-Path $HermesHome "auth.json") -BackupRoot $backupRoot | Out-Null
    if (Test-Path -LiteralPath $WebUiRoot) {
        Backup-And-Copy -Source (Join-Path $filesRoot "secrets\webui\.env") -Destination (Join-Path $WebUiRoot ".env") -BackupRoot $backupRoot | Out-Null
    }
} else {
    Write-Host "Secrets were not restored. Copy .env/auth files manually or rerun with -RestoreSecrets for a trusted private bundle." -ForegroundColor Yellow
}

$importNote = @"
Imported Hermes migration bundle
================================

Imported at: $(Get-Date -Format o)
Source host: $($manifest.source_host)
Source commit: $($manifest.git.commit)
Secrets restored: $([bool]$RestoreSecrets)
Backup root: $backupRoot
"@
Write-Utf8NoBom -Path (Join-Path $HermesHome "migration\last-import.txt") -Content $importNote

if ($InstallAutostart) {
    $installScript = Join-Path $AgentRoot "scripts\windows\install-hermes-autostart.ps1"
    if (-not (Test-Path -LiteralPath $installScript)) {
        throw "Missing autostart installer: $installScript"
    }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installScript -RefreshDesktopShortcuts
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

if ($StartAfterImport) {
    $gatewayScript = Join-Path $AgentRoot "scripts\windows\start-hermes-gateway.ps1"
    $webuiScript = Join-Path $AgentRoot "scripts\windows\start-hermes-webui.ps1"
    if (Test-Path -LiteralPath $webuiScript) {
        Start-Process -FilePath "powershell.exe" -ArgumentList @(
            "-NoProfile",
            "-WindowStyle",
            "Hidden",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            $webuiScript,
            "-WebUiRoot",
            $WebUiRoot,
            "-AgentRoot",
            $AgentRoot,
            "-Port",
            "8787"
        ) -WindowStyle Hidden | Out-Null
        Write-Host "Started WebUI launcher."
    }
    if (Test-Path -LiteralPath $gatewayScript) {
        Start-Process -FilePath "powershell.exe" -ArgumentList @(
            "-NoProfile",
            "-WindowStyle",
            "Hidden",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            $gatewayScript
        ) -WindowStyle Hidden | Out-Null
        Write-Host "Started gateway launcher."
    }
}

Write-Host "Import finished. Verify with:" -ForegroundColor Green
Write-Host "  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\verify-hermes-host-migration.ps1"
