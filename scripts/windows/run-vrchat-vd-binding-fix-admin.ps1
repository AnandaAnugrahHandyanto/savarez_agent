#Requires -Version 5.1
<#
.SYNOPSIS
  Elevated VRChat + Virtual Desktop binding/OpenXR fix for Quest 2 via VD.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\run-vrchat-vd-binding-fix-admin.ps1
#>
[CmdletBinding()]
param(
    [ValidateSet('Auto', 'VirtualDesktop', 'SteamVR')]
    [string]$Preference = 'VirtualDesktop',
    [switch]$SkipVdSettingsPatch,
    [string]$LogPath = ''
)

$ErrorActionPreference = 'Stop'
if (-not $LogPath) { $LogPath = Join-Path $env:TEMP 'vrchat_vd_binding_admin_fix.log' }

function Write-Log {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format 'o'), $Message
    Add-Content -Path $LogPath -Value $line -Encoding UTF8
    Write-Host $line
}

function Get-LatestVrChatLogSignals {
    $localLow = Join-Path $env:USERPROFILE 'AppData\LocalLow\VRChat\VRChat'
    $latest = Get-ChildItem $localLow -Filter 'output_log_*.txt' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $latest) { return @{ log_found = $false } }
    $text = Get-Content $latest.FullName -Raw -ErrorAction SilentlyContinue
    return @{
        log_found = $true
        log_path = $latest.FullName
        openxr_binding = if ($text -match 'Loaded Input Binding\[_OPENXR_GENERIC\]: (\w+)') { $Matches[1] } else { $null }
        touch_controller_usable = if ($text -match 'Oculus Touch controller = (True|False)') { $Matches[1] } else { $null }
        openxr_controller_usable = [bool]($text -match 'VRCInputProcessorOpenXR: can use OpenXR controller')
        vd_oculus_driver = [bool]($text -match 'oculus_virtualdesktop')
    }
}

try {
    Write-Log "VD binding admin fix starting (Preference=$Preference)"
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
    if (-not $isAdmin) {
        Write-Log 'Not elevated; re-launching with RunAs (approve UAC)...'
        $self = $MyInvocation.MyCommand.Path
        $argList = @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$self`"",
            '-Preference', $Preference,
            '-LogPath', "`"$LogPath`""
        )
        if ($SkipVdSettingsPatch) { $argList += '-SkipVdSettingsPatch' }
        Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList ($argList -join ' ') -Wait
        Write-Log 'Elevated child process finished.'
        exit $LASTEXITCODE
    }

    $fixScript = Join-Path $PSScriptRoot 'vrchat_quest2_openxr_fix.ps1'
    . $fixScript

    $vdCfg = Get-VirtualDesktopStreamerConfig
    Write-Log ("VD StreamerSettings keys: " + ($vdCfg.streamer_settings_keys -join ', '))
    Write-Log ("VD OpenVR external_drivers: " + ($vdCfg.openvr_external_drivers -join ' | '))

    $br = Invoke-VrChatBindingReset -DisableOscInputController
    foreach ($a in $br.actions) { Write-Log ("binding: " + $a) }

    if (-not $SkipVdSettingsPatch) {
        $vdPatch = Invoke-VirtualDesktopStreamerSettingsPatch
        if ($vdPatch.patched) {
            foreach ($c in $vdPatch.changes) { Write-Log ("VD settings: " + $c) }
            Write-Log ("VD settings backup: " + $vdPatch.backup)
        } else {
            Write-Log ("VD settings patch skipped: " + $vdPatch.reason)
        }
    }

    $result = Invoke-OpenXrFix -Preference $Preference -ResetBindings
    Write-Log ("chosen_manifest=" + $result.chosen_manifest)
    foreach ($w in $result.registry_writes) { Write-Log ("wrote: " + $w) }

    Get-VirtualDesktopStreamerHints | ForEach-Object { Write-Log ("MANUAL: " + $_) }
    Write-Log 'MANUAL: VRChat Quick Menu > Options > Controls > Reset VR Controls (required if log still shows Custom binding).'
    Write-Log 'MANUAL: VD Streamer > enable SteamVR Games + controller tracking passthrough; restart Streamer after settings patch.'

    $signals = Get-LatestVrChatLogSignals
    Write-Log ("log_snapshot openxr_binding=" + $signals.openxr_binding + " touch=" + $signals.touch_controller_usable)

    Write-Log 'SUCCESS'
    exit 0
}
catch {
    Write-Log ("FAILED: " + $_.Exception.Message)
    exit 1
}
