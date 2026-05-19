# Deprecated: use scripts/create-hermes-desktop-shortcuts.ps1 (creates all shortcuts under Desktop\Hermes Agent\).
# This wrapper remains for older docs that reference scripts\windows\create-hermes-desktop-shortcut.ps1

$ErrorActionPreference = "Stop"
$Unified = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) "create-hermes-desktop-shortcuts.ps1"
if (-not (Test-Path -LiteralPath $Unified)) {
    Write-Error "Not found: $Unified"
}
& powershell -NoProfile -ExecutionPolicy Bypass -File $Unified @args
