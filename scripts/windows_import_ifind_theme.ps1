param(
    [string]$InputPath,
    [string]$Sheet = '',
    [string]$OutputDir = 'C:\Users\mac\Desktop\qmt_runtime\exports',
    [string]$DateTag = '',
    [string]$PythonExe = 'python'
)

$ErrorActionPreference = 'Stop'

if (-not $InputPath) {
    throw 'InputPath is required. Example: -InputPath C:\path\to\ifind_export.xlsx'
}

if (-not (Test-Path $InputPath)) {
    throw "Input file not found: $InputPath"
}

if (-not $DateTag -or $DateTag.Trim() -eq '') {
    $DateTag = Get-Date -Format 'yyyyMMdd'
}

$targetDir = Join-Path $OutputDir $DateTag
New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir '..')
$importer = Join-Path $repoRoot 'scripts\import_ifind_theme_table.py'
$outputPath = Join-Path $targetDir 'ifind_theme_enrichment.json'

$cmd = @(
    $PythonExe,
    $importer,
    '--input', $InputPath,
    '--output', $outputPath
)
if ($Sheet -and $Sheet.Trim() -ne '') {
    $cmd += @('--sheet', $Sheet)
}

Write-Host "[IFIND] importing: $InputPath"
Write-Host "[IFIND] output: $outputPath"
& $cmd[0] $cmd[1..($cmd.Length-1)]

Write-Host "[IFIND] done"
Write-Host $outputPath
