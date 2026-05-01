$ErrorActionPreference = 'Stop'
$taskName = 'QMTIntradayRefresh'
$desktop = 'C:\Users\mac\Desktop'
$scriptPath = Join-Path $desktop 'qmt_runtime\admin\qmt_intraday_refresh_watchdog.ps1'

$times = @('09:26','09:32','09:45','10:15','11:00','13:15','14:00','14:40')
$triggers = @()
foreach ($t in $times) {
    $dt = [datetime]::ParseExact($t, 'HH:mm', $null)
    $triggers += New-ScheduledTaskTrigger -Daily -At $dt
}

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-ExecutionPolicy Bypass -NoProfile -File `"$scriptPath`""
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -StartWhenAvailable

try {
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
} catch {}

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers -Principal $principal -Settings $settings | Out-Null
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName, State, TaskPath | ConvertTo-Json -Depth 3
