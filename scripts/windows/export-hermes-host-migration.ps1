# Export a Hermes Windows host migration bundle.
#
# Default behavior is secret-safe: it records config, runtime metadata, and
# scheduled-task definitions, but it only lists secret-bearing file names and
# .env key names. Pass -IncludeSecrets only for a private, trusted transfer.

[CmdletBinding()]
param(
    [string]$OutputDir = "",
    [string]$HermesHome = "",
    [string]$AgentRoot = "",
    [string]$WebUiRoot = "",
    [switch]$IncludeSecrets,
    [switch]$IncludeLogs,
    [switch]$NoArchive
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

function Resolve-DefaultPath {
    param(
        [string]$Value,
        [string]$Fallback
    )
    if ($Value -and $Value.Trim()) {
        return (Resolve-Path -LiteralPath $Value).Path
    }
    if (Test-Path -LiteralPath $Fallback) {
        return (Resolve-Path -LiteralPath $Fallback).Path
    }
    return $Fallback
}

function Copy-IfExists {
    param(
        [string]$Source,
        [string]$Destination
    )
    if (Test-Path -LiteralPath $Source) {
        $parent = Split-Path -Parent $Destination
        if ($parent) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
        Copy-Item -LiteralPath $Source -Destination $Destination -Force
        return $true
    }
    return $false
}

function Get-DotEnvKeyNames {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return @()
    }
    $keys = @()
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }
        $key = ($trimmed -split "=", 2)[0].Trim().TrimStart([char]0xFEFF)
        if ($key) {
            $keys += $key
        }
    }
    return $keys | Sort-Object -Unique
}

function Invoke-Capture {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList,
        [int]$TimeoutSeconds = 20
    )
    $null = $TimeoutSeconds
    try {
        $oldExit = $global:LASTEXITCODE
        $output = (& $FilePath @ArgumentList 2>&1 | Out-String).Trim()
        $exit = $global:LASTEXITCODE
        if ($null -eq $exit) {
            $exit = if ($output) { 1 } else { 0 }
        }
        $global:LASTEXITCODE = $oldExit
        return @{
            ok = ($exit -eq 0)
            stdout = if ($exit -eq 0) { $output } else { "" }
            stderr = if ($exit -eq 0) { "" } else { $output }
            exit_code = $exit
        }
    } catch {
        return @{ ok = $false; stdout = ""; stderr = $_.Exception.Message; exit_code = $null }
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")
if (-not $AgentRoot) {
    $AgentRoot = $repoRoot.Path
} else {
    $AgentRoot = (Resolve-Path -LiteralPath $AgentRoot).Path
}

if (-not $HermesHome) {
    if ($env:HERMES_HOME -and $env:HERMES_HOME.Trim()) {
        $HermesHome = $env:HERMES_HOME.Trim()
    } else {
        $HermesHome = Join-Path $env:USERPROFILE ".hermes"
    }
}
$HermesHome = Resolve-DefaultPath -Value $HermesHome -Fallback $HermesHome

if (-not $WebUiRoot) {
    $sibling = Join-Path (Split-Path -Parent $AgentRoot) "hermes-WebUI"
    $desktop = Join-Path $env:USERPROFILE "Desktop\hermes-webui"
    if (Test-Path -LiteralPath $sibling) {
        $WebUiRoot = (Resolve-Path -LiteralPath $sibling).Path
    } elseif (Test-Path -LiteralPath $desktop) {
        $WebUiRoot = (Resolve-Path -LiteralPath $desktop).Path
    } else {
        $WebUiRoot = $sibling
    }
} else {
    $WebUiRoot = Resolve-DefaultPath -Value $WebUiRoot -Fallback $WebUiRoot
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
if (-not $OutputDir) {
    $OutputDir = Join-Path $HermesHome "migration\hermes-host-$stamp"
}
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$filesDir = Join-Path $OutputDir "files"
$tasksDir = Join-Path $OutputDir "scheduled-tasks"
$notesDir = Join-Path $OutputDir "notes"
New-Item -ItemType Directory -Path $filesDir, $tasksDir, $notesDir -Force | Out-Null

$configCopied = Copy-IfExists -Source (Join-Path $HermesHome "config.yaml") -Destination (Join-Path $filesDir "hermes_home\config.yaml")
$gatewayStateCopied = Copy-IfExists -Source (Join-Path $HermesHome "gateway_state.json") -Destination (Join-Path $filesDir "hermes_home\gateway_state.json")

$secretFiles = @(
    (Join-Path $HermesHome ".env"),
    (Join-Path $HermesHome "auth.json"),
    (Join-Path $WebUiRoot ".env")
)
$secretInventory = @()
foreach ($secret in $secretFiles) {
    $secretInventory += [pscustomobject]@{
        path = $secret
        exists = (Test-Path -LiteralPath $secret)
        env_keys = if ($secret.EndsWith(".env")) { @(Get-DotEnvKeyNames -Path $secret) } else { @() }
        exported = $false
    }
}

if ($IncludeSecrets) {
    foreach ($secret in $secretFiles) {
        if (-not (Test-Path -LiteralPath $secret)) { continue }
        $relative = if ($secret -like "$HermesHome*") {
            Join-Path "secrets\hermes_home" ($secret.Substring($HermesHome.Length).TrimStart("\"))
        } else {
            Join-Path "secrets\webui" (Split-Path -Leaf $secret)
        }
        Copy-IfExists -Source $secret -Destination (Join-Path $filesDir $relative) | Out-Null
    }
    foreach ($item in $secretInventory) {
        if ($item.exists) { $item.exported = $true }
    }
}

if ($IncludeLogs) {
    $logsRoot = Join-Path $HermesHome "logs"
    if (Test-Path -LiteralPath $logsRoot) {
        $targetLogs = Join-Path $filesDir "logs"
        New-Item -ItemType Directory -Path $targetLogs -Force | Out-Null
        Get-ChildItem -LiteralPath $logsRoot -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 10 |
            ForEach-Object {
                Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $targetLogs $_.Name) -Force
            }
    }
}

$taskNames = @(
    "HermesGatewayAutoStart",
    "HermesWebUIAutoStartNative",
    "HermesServerConnectivityWatchdog",
    "HermesSystemStartupSitrep",
    "HermesTailscaleServeWebUI",
    "HermesLlamaFallbackRTX3060",
    "HermesAgentStackAutoStart"
)
$taskSummaries = @()
foreach ($taskName in $taskNames) {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if (-not $task) {
        $taskSummaries += [pscustomobject]@{ task_name = $taskName; exists = $false }
        continue
    }
    $info = Get-ScheduledTaskInfo -TaskName $taskName -ErrorAction SilentlyContinue
    $xml = Export-ScheduledTask -TaskName $taskName
    Write-Utf8NoBom -Path (Join-Path $tasksDir "$taskName.xml") -Content $xml
    $taskSummaries += [pscustomobject]@{
        task_name = $taskName
        exists = $true
        state = [string]$task.State
        last_run_time = if ($info) { $info.LastRunTime } else { $null }
        last_task_result = if ($info) { $info.LastTaskResult } else { $null }
        actions = @($task.Actions | ForEach-Object {
            [pscustomobject]@{
                execute = $_.Execute
                arguments = $_.Arguments
                working_directory = $_.WorkingDirectory
            }
        })
    }
}

$git = Invoke-Capture -FilePath "git" -ArgumentList @("-C", $AgentRoot, "rev-parse", "HEAD")
$gitBranch = Invoke-Capture -FilePath "git" -ArgumentList @("-C", $AgentRoot, "branch", "--show-current")
$gitRemote = Invoke-Capture -FilePath "git" -ArgumentList @("-C", $AgentRoot, "remote", "-v")
$tailscale = Invoke-Capture -FilePath "tailscale" -ArgumentList @("serve", "status")

$ports = @()
foreach ($port in @(8787, 8080)) {
    $ports += @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object LocalAddress, LocalPort, OwningProcess, State)
}

$llamaServer = if ($env:HERMES_LLAMA_SERVER_EXE) {
    $env:HERMES_LLAMA_SERVER_EXE
} else {
    Join-Path $env:LOCALAPPDATA "Programs\llama-turboquant\bin\llama-server.exe"
}
$llamaModel = $env:HERMES_LLAMA_MODEL_PATH

$manifest = [pscustomobject]@{
    schema_version = 1
    exported_at = (Get-Date).ToString("o")
    source_host = $env:COMPUTERNAME
    source_user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    include_secrets = [bool]$IncludeSecrets
    paths = [pscustomobject]@{
        agent_root = $AgentRoot
        webui_root = $WebUiRoot
        hermes_home = $HermesHome
    }
    git = [pscustomobject]@{
        branch = $gitBranch.stdout.Trim()
        commit = $git.stdout.Trim()
        remotes = $gitRemote.stdout.Trim()
    }
    copied = [pscustomobject]@{
        config_yaml = $configCopied
        gateway_state = $gatewayStateCopied
        logs = [bool]$IncludeLogs
    }
    secrets = $secretInventory
    scheduled_tasks = $taskSummaries
    runtime = [pscustomobject]@{
        ports = $ports
        tailscale_serve_status = $tailscale.stdout.Trim()
        tailscale_error = $tailscale.stderr.Trim()
        llama_server_path = $llamaServer
        llama_server_exists = (Test-Path -LiteralPath $llamaServer)
        llama_model_path = $llamaModel
        llama_model_exists = ($llamaModel -and (Test-Path -LiteralPath $llamaModel))
    }
}

$manifestJson = $manifest | ConvertTo-Json -Depth 12
Write-Utf8NoBom -Path (Join-Path $OutputDir "manifest.json") -Content $manifestJson

$secretNote = @"
Hermes host migration bundle
============================

This bundle was exported from: $env:COMPUTERNAME
Created: $(Get-Date -Format o)

Secrets included: $([bool]$IncludeSecrets)

If secrets are not included, copy these manually on the destination host:
- $HermesHome\.env
- $HermesHome\auth.json
- $WebUiRoot\.env, only if the WebUI checkout uses one

After import, run:
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\verify-hermes-host-migration.ps1
"@
Write-Utf8NoBom -Path (Join-Path $notesDir "README.txt") -Content $secretNote

if (-not $NoArchive) {
    $zipPath = "$OutputDir.zip"
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -Path (Join-Path $OutputDir "*") -DestinationPath $zipPath -Force
    Write-Host "Exported migration bundle: $OutputDir"
    Write-Host "Archive: $zipPath"
} else {
    Write-Host "Exported migration bundle: $OutputDir"
}
