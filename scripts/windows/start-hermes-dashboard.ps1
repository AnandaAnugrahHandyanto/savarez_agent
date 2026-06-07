param(
    [string]$HermesRoot = "C:\Users\downl\Documents\New project\hermes-agent",
    [string]$HermesHome = "C:\Users\downl\.hermes",
    [string]$HostName = "127.0.0.1",
    [int]$Port = 9120
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$HermesRoot = (Resolve-Path -LiteralPath $HermesRoot).Path
$env:HERMES_HOME = $HermesHome
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$logDir = Join-Path $HermesHome "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
    exit 0
}

$pythonExe = Join-Path $HermesRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
    $pythonExe = Join-Path $HermesRoot "venv\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
    $pythonExe = (Get-Command python.exe -ErrorAction Stop | Select-Object -First 1 -ExpandProperty Source)
}

Start-Process `
    -FilePath $pythonExe `
    -ArgumentList @("-m", "hermes_cli.main", "dashboard", "--host", $HostName, "--port", "$Port", "--no-open", "--skip-build") `
    -WorkingDirectory $HermesRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir "dashboard-stdout.log") `
    -RedirectStandardError (Join-Path $logDir "dashboard-stderr.log") | Out-Null
