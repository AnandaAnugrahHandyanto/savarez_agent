function Get-OpenXrManifestCandidates {
    $steamVrRoot = @(
        'C:\Program Files (x86)\Steam\steamapps\common\SteamVR',
        'C:\Program Files\Steam\steamapps\common\SteamVR'
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    $steamManifest = if ($steamVrRoot) { Join-Path $steamVrRoot 'steamxr_win64.json' } else { $null }
    $vdManifest = 'C:\Program Files\Virtual Desktop Streamer\OpenXR\virtualdesktop-openxr.json'
    $oculusManifest = @(
        'C:\Program Files\Oculus\Support\oculus-runtime\oculus_openxr_64.json',
        'C:\Program Files\Meta Quest Remote Desktop\oculus_openxr_64.json'
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    [PSCustomObject]@{
        steamvr_manifest = $steamManifest
        steamvr_exists   = [bool]($steamManifest -and (Test-Path $steamManifest))
        vd_manifest      = $vdManifest
        vd_exists        = Test-Path $vdManifest
        oculus_manifest  = $oculusManifest
        oculus_exists    = [bool]$oculusManifest
    }
}

function Get-RegistryOpenXrFixed {
    $results = @()
    foreach ($root in @('HKLM:\SOFTWARE\Khronos\OpenXR\1', 'HKCU:\SOFTWARE\Khronos\OpenXR\1')) {
        $item = [PSCustomObject]@{
            root            = $root
            key_exists      = (Test-Path $root)
            active_exists   = $false
            active_manifest = $null
        }
        if (-not (Test-Path $root)) { $results += $item; continue }
        $props = Get-ItemProperty $root -ErrorAction SilentlyContinue
        if ($props -and ($props.PSObject.Properties.Name -contains 'ActiveRuntime')) {
            $item.active_exists = [bool]$props.ActiveRuntime
            $item.active_manifest = [string]$props.ActiveRuntime
        }
        $results += $item
    }
    return $results
}

function Resolve-PreferredOpenXrManifest {
    param([string]$Preference = 'Auto', $Candidates)
    switch ($Preference) {
        'VirtualDesktop' {
            if ($Candidates.vd_exists) { return $Candidates.vd_manifest }
            throw 'Virtual Desktop OpenXR manifest not found.'
        }
        'SteamVR' {
            if ($Candidates.steamvr_exists) { return $Candidates.steamvr_manifest }
            throw 'SteamVR OpenXR manifest not found.'
        }
        default {
            if ($Candidates.vd_exists) { return $Candidates.vd_manifest }
            if ($Candidates.steamvr_exists) { return $Candidates.steamvr_manifest }
            if ($Candidates.oculus_exists) { return $Candidates.oculus_manifest }
            throw 'No OpenXR manifest found.'
        }
    }
}

function Set-OpenXrActiveRuntimeValue {
    param([ValidateSet('HKCU','HKLM')][string]$Hive, [string]$ManifestPath)
    if (-not (Test-Path $ManifestPath)) { throw "Manifest missing: $ManifestPath" }
    $keyPath = if ($Hive -eq 'HKCU') { 'HKCU:\SOFTWARE\Khronos\OpenXR\1' } else { 'HKLM:\SOFTWARE\Khronos\OpenXR\1' }
    if (-not (Test-Path $keyPath)) { New-Item -Path $keyPath -Force | Out-Null }
    Set-ItemProperty -Path $keyPath -Name 'ActiveRuntime' -Value $ManifestPath -Type String
    $wow = if ($Hive -eq 'HKCU') { 'HKCU:\SOFTWARE\WOW6432Node\Khronos\OpenXR\1' } else { 'HKLM:\SOFTWARE\WOW6432Node\Khronos\OpenXR\1' }
    if (-not (Test-Path $wow)) { New-Item -Path $wow -Force | Out-Null }
    $manifest32 = $ManifestPath -replace 'virtualdesktop-openxr\.json$', 'virtualdesktop-openxr-32.json'
    if (Test-Path $manifest32) { Set-ItemProperty -Path $wow -Name 'ActiveRuntime' -Value $manifest32 -Type String }
}

function Register-OpenXrAvailableRuntime {
    param([ValidateSet('HKCU','HKLM')][string]$Hive, [string]$ManifestPath)
    if (-not (Test-Path $ManifestPath)) { return }
    $parent = if ($Hive -eq 'HKCU') { 'HKCU:\SOFTWARE\Khronos\OpenXR\1' } else { 'HKLM:\SOFTWARE\Khronos\OpenXR\1' }
    if (-not (Test-Path $parent)) { New-Item -Path $parent -Force | Out-Null }
    $keyPath = Join-Path $parent 'AvailableRuntimes'
    if (-not (Test-Path $keyPath)) { New-Item -Path $keyPath -Force | Out-Null }
    New-ItemProperty -Path $keyPath -Name $ManifestPath -Value 0 -PropertyType DWord -Force | Out-Null
}

function Get-OpenXrManifestList {
    param($Candidates)
    $list = New-Object System.Collections.Generic.List[string]
    foreach ($m in @($Candidates.vd_manifest, $Candidates.steamvr_manifest, $Candidates.oculus_manifest)) {
        if ($m -and (Test-Path $m) -and -not $list.Contains($m)) { [void]$list.Add($m) }
    }
    return $list
}

function Invoke-OpenXrFix {
    param([string]$Preference = 'Auto', [switch]$ResetBindings)
    $candidates = Get-OpenXrManifestCandidates
    $manifest = Resolve-PreferredOpenXrManifest -Preference $Preference -Candidates $candidates
    $manifests = Get-OpenXrManifestList -Candidates $candidates
    if (-not $manifests.Contains($manifest)) { [void]$manifests.Add($manifest) }

    $before = Get-RegistryOpenXrFixed
    Write-Host '--- OpenXR ActiveRuntime BEFORE ---' -ForegroundColor Yellow
    $before | Format-Table root, active_exists, active_manifest -AutoSize | Out-Host

    foreach ($m in $manifests) { Register-OpenXrAvailableRuntime -Hive 'HKCU' -ManifestPath $m }
    Set-OpenXrActiveRuntimeValue -Hive 'HKCU' -ManifestPath $manifest
    $written = @("HKCU ActiveRuntime=$manifest")

    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if ($isAdmin) {
        foreach ($m in $manifests) { Register-OpenXrAvailableRuntime -Hive 'HKLM' -ManifestPath $m }
        Set-OpenXrActiveRuntimeValue -Hive 'HKLM' -ManifestPath $manifest
        $written += "HKLM ActiveRuntime=$manifest"
    } else {
        Write-Host 'HKLM: skipped (not elevated).' -ForegroundColor DarkYellow
    }

    if ($ResetBindings) {
        $bindings = Join-Path $env:USERPROFILE 'AppData\LocalLow\VRChat\VRChat\Bindings'
        if (Test-Path $bindings) {
            $backup = Join-Path (Split-Path $bindings -Parent) ('Bindings_backup_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
            Copy-Item -Path $bindings -Destination $backup -Recurse -Force
            Remove-Item -Path $bindings -Recurse -Force
            Write-Host "Bindings backed up to $backup" -ForegroundColor Green
        }
    }

    $after = Get-RegistryOpenXrFixed
    Write-Host '--- OpenXR ActiveRuntime AFTER ---' -ForegroundColor Green
    $after | Format-Table root, active_exists, active_manifest -AutoSize | Out-Host

    [PSCustomObject]@{ chosen_manifest = $manifest; registry_writes = $written; before = $before; after = $after }
}

function Get-VirtualDesktopStreamerHints {
    @(
        'Enable SteamVR / SteamVR games in Virtual Desktop Streamer.',
        'Enable controller tracking passthrough to SteamVR.',
        'Launch VRChat from VD Games tab (not desktop mirror).',
        'Oculus Touch=False is expected on VD+SteamVR; OpenXR controller path should be active.'
    )
}


