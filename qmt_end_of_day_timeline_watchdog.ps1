$ErrorActionPreference = 'Continue'
$desktop = 'C:\Users\mac\Desktop'
$python = 'C:\Program Files\Python311\python.exe'
$dateStr = Get-Date -Format 'yyyyMMdd'
$exportDir = Join-Path $desktop ("qmt_runtime\exports\{0}" -f $dateStr)
$reportDir = Join-Path $desktop ("qmt_runtime\reports\{0}" -f $dateStr)
$timelineScript = Join-Path $desktop 'qmt_runtime\auxiliary\qmt_intraday_timeline.py'
$matrixScript = Join-Path $desktop 'qmt_runtime\auxiliary\qmt_intraday_state_matrix.py'
$statusJson = Join-Path $desktop 'qmt_runtime\end_of_day_timeline_last.json'

$result = [ordered]@{
  ts = (Get-Date).ToString('s')
  ok = $false
  export_dir = $exportDir
  report_dir = $reportDir
}

try {
  & $python $timelineScript $exportDir --out (Join-Path $reportDir 'intraday_timeline_report.txt') | Out-Null
  & $python $matrixScript $exportDir --out (Join-Path $reportDir 'intraday_state_matrix.txt') | Out-Null
  $result.ok = $true
} catch {
  $result.error = $_.Exception.Message
}

$result | ConvertTo-Json -Depth 6 | Set-Content -Path $statusJson -Encoding UTF8
Get-Content $statusJson
if (Test-Path (Join-Path $reportDir 'intraday_timeline_report.txt')) { Get-Content (Join-Path $reportDir 'intraday_timeline_report.txt') }
if (Test-Path (Join-Path $reportDir 'intraday_state_matrix.txt')) { Get-Content (Join-Path $reportDir 'intraday_state_matrix.txt') }
