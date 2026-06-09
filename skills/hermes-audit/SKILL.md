---
name: hermes-audit
description: Full audit system deployment for Hermes Agent — security audit logging, session trajectory snapshots, log rotation, DEBUG/INFO switching, observability monitoring, daily auto-backup, status query, backup restore
version: 2.1.0
author: xuanyukk
platforms: [windows]
metadata:
  hermes:
    tags: [audit, security, logging, backup, monitoring]
    category: devops
    requires_toolsets: [terminal]
---

# Hermes Agent Audit System

Complete audit and monitoring system deployment for Hermes Agent on Windows. Deploys security audit logging, session trajectory capture, log rotation policies, log level management, observability monitoring, and automated daily backup of all audit data — all manageable through configuration commands.

## When to Use

Load this skill when the user requests audit-related configuration or management:

- Enabling or disabling the full audit system
- Checking audit system status (which components are active, log sizes)
- Retrieving recent command execution records from audit logs
- Switching between INFO (stable) and DEBUG (troubleshooting) log levels
- Setting up or cancelling daily automatic audit log backups
- Viewing backup archives and their status
- Performing emergency manual backups or restoring from backup files

## Quick Reference

| Operation | Primary Commands |
|-----------|-----------------|
| Enable audit logging | `hermes config set security.enable_audit_log true` |
| Enable terminal command audit | `hermes config set security.audit_terminal_commands true` |
| Enable file operation audit | `hermes config set security.audit_file_operations true` |
| Enable session snapshots | `hermes config set sessions.write_json_snapshots true` |
| Set log level to INFO | `hermes config set logging.level INFO` |
| Set log level to DEBUG | `hermes config set logging.level DEBUG` |
| Set max log file size (100MB) | `hermes config set logging.max_file_size 104857600` |
| Set max backup count | `hermes config set logging.max_backup_count 30` |
| Set max log age (7 days) | `hermes config set logging.max_age_days 7` |
| Install observability plugin | `hermes plugins install observability && hermes plugins enable observability` |
| View audit log tail | `Get-Content ~/.hermes/logs/audit.log -Tail 20` |
| Disable all audit | Set all security/session config keys to `false` |

> **Windows path note:** The Hermes Agent executable is located at `$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe`. All commands below use this full path.

## Procedure

### 1. Enable Full Audit Mode

Deploys all four layers of the audit system: security audit logging, session trajectory snapshots, log rotation, and observability monitoring.

```powershell
# 1. Enable core security audit
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config set security.enable_audit_log true
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config set security.audit_terminal_commands true
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config set security.audit_file_operations true
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config set security.redact_sensitive_info true
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config set security.audit_log_file "~/.hermes/logs/audit.log"

# 2. Enable session trajectory snapshots
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config set sessions.write_json_snapshots true

# 3. Configure log rotation (prevent disk overflow)
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config set logging.max_file_size 104857600
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config set logging.max_backup_count 30
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config set logging.max_age_days 7

# 4. Set stable INFO log level
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config set logging.level INFO

# 5. Install and enable observability plugin
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe plugins install observability
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe plugins enable observability

# 6. Restart gateway to apply all changes
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe gateway stop
Start-Sleep -Seconds 5
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe gateway start
```

**Audit coverage includes:** user messages, bot responses, terminal commands, file operations, configuration changes, permission modifications, gateway start/stop events, and skill load/unload operations.

**Output locations:**
- Audit log: `~/.hermes/logs/audit.log`
- Session snapshots: `~/.hermes/sessions/`
- Observability dashboard: `http://localhost:8080/observability`

### 2. Check Audit Status

Query the current state of all audit system components:

```powershell
$auditEnabled = $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config get security.enable_audit_log
$terminalAudit = $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config get security.audit_terminal_commands
$fileAudit = $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config get security.audit_file_operations
$sessionEnabled = $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config get sessions.write_json_snapshots
$logLevel = $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config get logging.level
$observabilityStatus = $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe plugins list | Select-String "observability"

# Report log file size
if (Test-Path $HOME\.hermes\logs\audit.log) {
    $logSize = [math]::Round((Get-Item $HOME\.hermes\logs\audit.log).Length / 1MB, 2)
    Write-Host "Audit log size: $logSize MB"
} else {
    Write-Host "Audit log not yet generated"
}
```

Report these status values to the user:
- `security.enable_audit_log` — true if core audit is active
- `security.audit_terminal_commands` — true if terminal command logging is active
- `security.audit_file_operations` — true if file operation logging is active
- `sessions.write_json_snapshots` — true if session trajectory capture is active
- `logging.level` — current log level (INFO or DEBUG)
- Observability plugin status — enabled or disabled
- Audit log current size in MB

### 3. View Recent Command Execution Records

Retrieve the last 20 terminal command audit entries:

```powershell
Get-Content $HOME\.hermes\logs\audit.log -Tail 20 | Select-String "terminal_command_executed"
```

### 4. Enable DEBUG Logging

Temporarily switch to verbose DEBUG logging for troubleshooting:

```powershell
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config set logging.level DEBUG
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe gateway stop
Start-Sleep -Seconds 3
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe gateway start
```

> **Note:** DEBUG logging produces significantly more output. Only use for active troubleshooting and switch back to INFO when done.

### 5. Disable DEBUG Logging (Restore INFO)

Return to stable INFO log level:

```powershell
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config set logging.level INFO
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe gateway stop
Start-Sleep -Seconds 3
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe gateway start
```

### 6. Disable Full Audit Mode

> **Requires user confirmation before execution.** Disabling audit will stop all logging, session snapshots, and security auditing.

After receiving explicit confirmation, execute:

```powershell
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config set security.enable_audit_log false
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config set security.audit_terminal_commands false
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config set security.audit_file_operations false
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config set sessions.write_json_snapshots false
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config set logging.level INFO
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe plugins disable observability

$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe gateway stop
Start-Sleep -Seconds 3
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe gateway start
```

Existing log files and session snapshots are preserved on disk — only new logging is stopped.

### 7. Set Up Daily Audit Auto-Backup

> **Requires administrator privileges on Windows.** Creates a scheduled task that runs every day at 01:00 AM.

1. Create the backup directory and write the auto-backup script to `$HOME\.hermes\log-backup\auto-backup.ps1`:
   ```powershell
   New-Item -Path "$HOME\.hermes\log-backup" -ItemType Directory -Force | Out-Null

   $backupScript = @'
   $backupTime = Get-Date -Format yyyyMMdd
   $backupDir = "$HOME\.hermes\log-backup"
   $sourceDir = "$HOME\.hermes\logs"
   $sessionsDir = "$HOME\.hermes\sessions"

   # Package all audit data
   Compress-Archive -Path $sourceDir\*, $sessionsDir\* -DestinationPath "$backupDir\audit-full-backup-$backupTime.zip" -Force

   # Auto-clean backups older than 30 days
   $expireTime = (Get-Date).AddDays(-30)
   Get-ChildItem -Path $backupDir -Filter "audit-full-backup-*.zip" | Where-Object { $_.LastWriteTime -lt $expireTime } | Remove-Item -Force
   '@
   $backupScript | Out-File "$HOME\.hermes\log-backup\auto-backup.ps1" -Encoding utf8
   ```

2. Register the scheduled task:
   ```powershell
   $taskAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File $HOME\.hermes\log-backup\auto-backup.ps1"
   $taskTrigger = New-ScheduledTaskTrigger -Daily -At 01:00
   $taskSetting = New-ScheduledTaskSettingsSet -RunWhetherUserIsLoggedOnOrNot -Hidden
   Register-ScheduledTask -TaskName "Hermes-审计日志自动备份" -Action $taskAction -Trigger $taskTrigger -Settings $taskSetting -User $env:USERNAME -Force
   ```

3. Verify: `Get-ScheduledTask -TaskName "Hermes-审计日志自动备份"`

**Backup policy:** Daily at 01:00, auto-expire after 30 days.

### 8. Cancel Daily Audit Auto-Backup

Stops the scheduled backup task. Existing backup files are preserved:

```powershell
Unregister-ScheduledTask -TaskName "Hermes-审计日志自动备份" -Confirm:$false -ErrorAction SilentlyContinue
```

### 9. View Backup Archive List

List all audit backup archives sorted by date (newest first):

```powershell
Get-ChildItem -Path "$HOME\.hermes\log-backup" -Filter "audit-full-backup-*.zip" | Sort-Object LastWriteTime -Descending | Format-Table Name, Length, LastWriteTime -AutoSize
```

### 10. Emergency Manual Backup

Execute immediately to create a point-in-time backup:

```powershell
$backupTime = Get-Date -Format yyyyMMddHHmm
New-Item -Path "$HOME\.hermes\log-backup" -ItemType Directory -Force | Out-Null
Compress-Archive -Path "$HOME\.hermes\logs\*", "$HOME\.hermes\sessions\*" -DestinationPath "$HOME\.hermes\log-backup\audit-manual-backup-$backupTime.zip" -Force
Write-Host "Manual backup completed: audit-manual-backup-$backupTime.zip"
```

### 11. Restore from Backup File

Replace `<backup-filename>` with the actual backup file name:

```powershell
$backupFile = "$HOME\.hermes\log-backup\<backup-filename>.zip"
Expand-Archive -Path $backupFile -DestinationPath "$HOME\.hermes\" -Force
Write-Host "Audit logs restored from: $backupFile"
```

## Pitfalls

### Audit log is not being generated
- Verify Hermes Agent version is ≥ v0.12.0 (required for audit support).
- Confirm `security.enable_audit_log` is set to `true` via Procedure step 2.
- Restart the gateway after enabling: `hermes gateway stop; Start-Sleep 3; hermes gateway start`

### Observability plugin fails to install
- Some Hermes Agent versions do not include the built-in observability plugin. This does not affect audit, backup, or logging core functionality.
- The remaining audit features (security logging, session snapshots, log rotation, backups) continue to work independently.

### Skill does not trigger in the bot system
- Confirm the skill file is placed in the correct skills directory (`~/.hermes/skills/`).
- Verify the skill is enabled and visible: `hermes skills list | Select-String "audit"`
- Re-import the skill file if the frontmatter was modified.

### Log files consuming excessive disk space
- Default log rotation is already active: max 100 MB per file, 30 backup files retained, 7-day expiry.
- To manually purge old rotated logs:
  ```powershell
  Remove-Item $HOME\.hermes\logs\*.log.* -Force
  ```

### Scheduled backup task does not execute
- Verify the task exists in Windows Task Scheduler under "Hermes-审计日志自动备份".
- Confirm the task was created with administrator privileges (required for `Register-ScheduledTask`).
- Test the script manually: `powershell.exe -ExecutionPolicy Bypass -File $HOME\.hermes\log-backup\auto-backup.ps1`

### DEBUG log level produces too much output
- This is expected behavior. DEBUG level records all internal operations for troubleshooting.
- Switch back to INFO as soon as troubleshooting is complete (Procedure step 5).
- The log rotation policy (100 MB per file, 30 backups) prevents disk overflow even at DEBUG level.

## Verification

After deploying the audit system, verify each component:

1. **Audit toggle:** Run Procedure step 2 (Check Audit Status). All core audit keys should report `true` when enabled.
2. **Command audit:** Execute any bot command, then run Procedure step 3. The command should appear in the audit log.
3. **Session trajectory:** Send any message to the bot, then check `~/.hermes/sessions/` — a new JSON snapshot file should be created.
4. **Log rotation:** Verify the rotation config: `hermes config get logging.max_file_size` should return `104857600`.
5. **Backup task:** Open Windows Task Scheduler and confirm "Hermes-审计日志自动备份" is present with status "Ready" and trigger "Daily at 01:00".
6. **Backup archive:** After the first backup runs, check `~/.hermes/log-backup/` for a `.zip` file named `audit-full-backup-YYYYMMDD.zip`.
