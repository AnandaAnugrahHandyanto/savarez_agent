$ErrorActionPreference = 'Continue'
$desktop = 'C:\Users\mac\Desktop'
$python = 'C:\Program Files\Python311\python.exe'
$script = Join-Path $desktop 'qmt_runtime\auxiliary\qmt_status_panel.py'
$baseDir = Join-Path $desktop 'qmt_runtime'
$outPath = Join-Path $desktop 'qmt_runtime\reports\status_panel.txt'
$statusJson = Join-Path $desktop 'qmt_runtime\status_panel_last.json'

$result = [ordered]@{
  ts = (Get-Date).ToString('s')
  ok = $false
  out = $outPath
}

try {
  & $python $script $baseDir --out $outPath | Out-Null
  $result.ok = $true
} catch {
  $result.error = $_.Exception.Message
}

$result | ConvertTo-Json -Depth 6 | Set-Content -Path $statusJson -Encoding UTF8
Get-Content $statusJson
if (Test-Path $outPath) { Get-Content $outPath }
