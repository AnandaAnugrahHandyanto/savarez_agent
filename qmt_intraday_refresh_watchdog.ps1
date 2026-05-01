$ErrorActionPreference = 'Continue'
$desktop = 'C:\Users\mac\Desktop'
$python = 'C:\Program Files\Python311\python.exe'
$dateStr = Get-Date -Format 'yyyyMMdd'
$exportDir = Join-Path $desktop ("qmt_runtime\exports\{0}" -f $dateStr)
$reportDir = Join-Path $desktop ("qmt_runtime\reports\{0}" -f $dateStr)
$script = Join-Path $desktop 'qmt_runtime\auxiliary\qmt_intraday_snapshot_and_refresh.py'
$statusJson = Join-Path $desktop 'qmt_runtime\intraday_refresh_last.json'
$outLog = Join-Path $desktop 'qmt_runtime\auxiliary\intraday_refresh_out.log'
$errLog = Join-Path $desktop 'qmt_runtime\auxiliary\intraday_refresh_err.log'
$tag = Get-Date -Format 'HHmm'

$result = [ordered]@{
  ts = (Get-Date).ToString('s')
  ok = $false
  export_dir = $exportDir
  report_dir = $reportDir
  script = $script
  tag = $tag
}

if (!(Test-Path $python)) {
  $result.error = 'python not found'
  $result | ConvertTo-Json -Depth 6 | Set-Content -Path $statusJson -Encoding UTF8
  Get-Content $statusJson
  exit 1
}

if (!(Test-Path $script)) {
  $result.error = 'intraday script not found'
  $result | ConvertTo-Json -Depth 6 | Set-Content -Path $statusJson -Encoding UTF8
  Get-Content $statusJson
  exit 1
}

try {
  & $python $script $exportDir $reportDir --python-bin $python --tag $tag 2>> $errLog 1>> $outLog
  if (!(Test-Path $statusJson)) {
    $result.ok = $true
    $result.warning = 'status json missing after python pipeline'
    $result | ConvertTo-Json -Depth 6 | Set-Content -Path $statusJson -Encoding UTF8
  }
} catch {
  $result.error = $_.Exception.Message
  $result | ConvertTo-Json -Depth 6 | Set-Content -Path $statusJson -Encoding UTF8
}

Get-Content $statusJson
if (Test-Path (Join-Path $reportDir 'intraday_refresh_report.txt')) { Get-Content (Join-Path $reportDir 'intraday_refresh_report.txt') }
if (Test-Path (Join-Path $reportDir 'intraday_timeline_report.txt')) { Get-Content (Join-Path $reportDir 'intraday_timeline_report.txt') }
if (Test-Path (Join-Path $reportDir 'intraday_state_matrix_report.txt')) { Get-Content (Join-Path $reportDir 'intraday_state_matrix_report.txt') }
