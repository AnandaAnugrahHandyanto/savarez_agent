$tasks = Get-ScheduledTask | Where-Object { $_.TaskName -like '*QMT*' -or $_.TaskName -like '*qmt*' } | Select-Object TaskName, State, TaskPath
$tasks | ConvertTo-Json -Depth 3
