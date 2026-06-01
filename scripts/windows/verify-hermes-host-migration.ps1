# Verify a Hermes Windows host after migration or recovery.

[CmdletBinding()]
param(
    [string]$WebUiUrl = "http://127.0.0.1:8787",
    [string]$TailnetUrl = "https://9.taile4f666.ts.net",
    [string]$HermesHome = "",
    [switch]$SkipTailnet,
    [switch]$SkipLlama,
    [switch]$RequireTailnet,
    [switch]$RequireLlama,
    [switch]$Json
)

$ErrorActionPreference = "Stop"

if (-not $HermesHome) {
    if ($env:HERMES_HOME -and $env:HERMES_HOME.Trim()) {
        $HermesHome = $env:HERMES_HOME.Trim()
    } else {
        $HermesHome = Join-Path $env:USERPROFILE ".hermes"
    }
}

function Test-Http {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 8
        return [pscustomobject]@{
            name = $Url
            ok = ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500)
            status = $response.StatusCode
            detail = ""
        }
    } catch {
        return [pscustomobject]@{
            name = $Url
            ok = $false
            status = "ERR"
            detail = $_.Exception.Message
        }
    }
}

function Test-Port {
    param([int]$Port)
    $listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    return [pscustomobject]@{
        name = "port $Port listening"
        ok = ($listeners.Count -gt 0)
        status = if ($listeners.Count -gt 0) { "LISTEN" } else { "MISSING" }
        detail = ($listeners | Select-Object -First 4 | ForEach-Object { "$($_.LocalAddress):$($_.LocalPort) pid=$($_.OwningProcess)" }) -join "; "
    }
}

function Test-GatewayState {
    param([string]$StatePath)
    if (-not (Test-Path -LiteralPath $StatePath)) {
        return [pscustomobject]@{ name = "gateway_state.json"; ok = $false; status = "MISSING"; detail = $StatePath }
    }
    try {
        $state = Get-Content -LiteralPath $StatePath -Raw -Encoding UTF8 | ConvertFrom-Json
        $telegram = $null
        if ($state.platforms -and $state.platforms.telegram) {
            $telegram = $state.platforms.telegram.state
        }
        $ok = ($state.gateway_state -eq "running" -and $telegram -eq "connected")
        return [pscustomobject]@{
            name = "gateway_state.json"
            ok = $ok
            status = $state.gateway_state
            detail = "pid=$($state.pid); telegram=$telegram; updated_at=$($state.updated_at)"
        }
    } catch {
        return [pscustomobject]@{ name = "gateway_state.json"; ok = $false; status = "ERR"; detail = $_.Exception.Message }
    }
}

function Test-ScheduledTaskState {
    param([string]$TaskName)
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $task) {
        return [pscustomobject]@{ name = "task $TaskName"; ok = $false; status = "MISSING"; detail = "" }
    }
    $info = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue
    return [pscustomobject]@{
        name = "task $TaskName"
        ok = $true
        status = [string]$task.State
        detail = if ($info) { "last=$($info.LastRunTime); result=$($info.LastTaskResult)" } else { "" }
    }
}

$web = $WebUiUrl.TrimEnd("/")
$tail = $TailnetUrl.TrimEnd("/")
$results = @()
$results += Test-Port -Port 8787
$results += Test-Http -Url "$web/"
$results += Test-Http -Url "$web/health"
$results += Test-Http -Url "$web/api/auth/status"
$results += Test-GatewayState -StatePath (Join-Path $HermesHome "gateway_state.json")
$results += Test-ScheduledTaskState -TaskName "HermesGatewayAutoStart"
$results += Test-ScheduledTaskState -TaskName "HermesWebUIAutoStartNative"
$results += Test-ScheduledTaskState -TaskName "HermesTailscaleServeWebUI"

if (-not $SkipTailnet) {
    $results += Test-Http -Url "$tail/"
    $results += Test-Http -Url "$tail/health"
    $results += Test-Http -Url "$tail/api/auth/status"
}

if (-not $SkipLlama) {
    $llama = Test-Http -Url "http://127.0.0.1:8080/v1/models"
    if (-not $RequireLlama) {
        $llama | Add-Member -NotePropertyName optional -NotePropertyValue $true -Force
    }
    $results += $llama
}

if ($Json) {
    $results | ConvertTo-Json -Depth 6
} else {
    $results | Format-Table -AutoSize -Wrap name, ok, status, detail
}

$failures = @($results | Where-Object {
    if ($_.optional -and -not $RequireLlama) { return $false }
    if ($_.name -like "$tail/*" -and -not $RequireTailnet) { return $false }
    -not $_.ok
})

if ($failures.Count -gt 0) {
    exit 1
}
exit 0
