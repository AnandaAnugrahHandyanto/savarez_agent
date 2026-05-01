$ErrorActionPreference = 'Stop'
$taskName = 'QMTEndOfDayTimeline'
$desktop = 'C:\Users\mac\Desktop'
$scriptPath = Join-Path $desktop 'qmt_runtime\admin\qmt_end_of_day_timeline_watchdog.ps1'
$dt = [datetime]::ParseExact('14:50', 'HH:mm', $null)
$trigger = New-ScheduledTaskTrigger -Daily -At $dt
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-ExecutionPolicy Bypass -NoProfile -File `"$scriptPath`""
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -StartWhenAvailable
try {
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
} catch {}
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings | Out-Null
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName, State, TaskPath | ConvertTo-Json -Depth 3
