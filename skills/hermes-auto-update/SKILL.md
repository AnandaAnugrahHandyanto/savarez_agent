---
name: hermes-auto-update
description: Automated Hermes Agent update management — version check, incremental/full update, rollback, scheduled weekly update, China mirror config, version lock/switch, plugin & skill auto-update, update history
version: 2.0.0
author: xuanyukk
platforms: [windows]
metadata:
  hermes:
    tags: [update, system-management, automation, version-control]
    category: devops
    requires_toolsets: [terminal]
---

# Hermes Agent Auto-Update

Comprehensive update lifecycle management for Hermes Agent on Windows. Covers version checking, incremental and full updates, automatic rollback on failure, scheduled weekly unattended updates, China network mirror configuration, version locking and branch switching, and automatic plugin/skill refresh after agent updates.

## When to Use

Load this skill when the user requests any Hermes Agent update-related operation:

- Checking whether a new version is available
- Updating to the latest version (one-click or step-by-step)
- Performing incremental updates for minor version bumps
- Performing full reinstalls for major upgrades or dependency repair
- Rolling back a failed or unwanted update to the previous version
- Setting up or cancelling weekly scheduled automatic updates
- Configuring a China-friendly GitHub mirror for faster downloads
- Locking the current version to prevent automatic updates
- Switching between stable (`main`), beta (`develop`), or a specific version tag
- Updating all installed plugins or skills
- Viewing update history, backup files, and git changelogs

## Quick Reference

| Operation | Primary Commands |
|-----------|-----------------|
| Check for updates | `hermes update --check` |
| Full update (backup + restart) | `hermes update --backup --yes` |
| Update all plugins | `hermes plugins update --all` |
| Update all skills | `hermes skills update --all` |
| Stop gateway | `hermes gateway stop` |
| Start gateway | `hermes gateway start` |
| Lock current version | `hermes config set update.auto_check false` |
| Unlock version | `hermes config set update.auto_check true` |
| Switch to stable branch | `git -C ~/.hermes/hermes-agent checkout main && git -C ~/.hermes/hermes-agent pull` |
| Switch to beta branch | `git -C ~/.hermes/hermes-agent checkout develop && git -C ~/.hermes/hermes-agent pull` |
| Configure China mirror | `git -C ~/.hermes/hermes-agent remote set-url origin https://ghfast.top/https://github.com/NousResearch/hermes-agent.git` |
| Restore official remote | `git -C ~/.hermes/hermes-agent remote set-url origin https://github.com/NousResearch/hermes-agent.git` |

> **Windows path note:** The Hermes Agent executable is located at `$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe`. All commands below use this full path to ensure correct execution regardless of PATH configuration.

## Procedure

### 1. Check for New Version

Run the check command and report the result to the user:

```powershell
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe update --check
```

### 2. Incremental Update

Use for minor version bumps (e.g., v0.15.0 → v0.15.1). Only pulls changed files — approximately 80% faster than a full update.

**Step 1 — Create backup:**

```powershell
$backupPath = "$HOME\.hermes\backups\pre-update-$(Get-Date -Format yyyyMMddHHmmss).zip"
New-Item -Path "$HOME\.hermes\backups" -ItemType Directory -Force | Out-Null
Compress-Archive -Path $HOME\.hermes\* -DestinationPath $backupPath -Force
Write-Host "Backup saved to: $backupPath"
```

**Step 2 — Stop gateway (Windows requires this to release file locks):**

```powershell
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe gateway stop
Start-Sleep -Seconds 5
```

**Step 3 — Pull changes and update dependencies:**

```powershell
cd $HOME\.hermes\hermes-agent
git pull --rebase
pip install -r requirements.txt --upgrade --no-deps
```

**Step 4 — Restart gateway and verify:**

```powershell
Start-Sleep -Seconds 5
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe gateway start
$version = $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe --version
Write-Host "Current version: $version"
```

### 3. Full Update

Use for major version upgrades (e.g., v0.14.0 → v0.15.0) or when dependencies are corrupted. Reinstalls all dependencies from scratch.

1. Create backup (same as incremental update step 1)
2. Stop gateway (same as incremental update step 2)
3. Execute official full update command:
   ```powershell
   $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe update --full --backup --yes
   ```
4. Wait 15 seconds for the update to complete, then force-restart:
   ```powershell
   Start-Sleep -Seconds 15
   $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe gateway stop
   Start-Sleep -Seconds 5
   $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe gateway start
   ```
5. Verify version: `$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe --version`

### 4. One-Click Update (Recommended)

Combines backup, official update, plugin refresh, and skill refresh in a single workflow. Use this as the default update method.

1. Create backup (same as incremental update step 1)
2. Stop gateway (same as incremental update step 2)
3. Run official update:
   ```powershell
   $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe update --backup --yes
   ```
4. Update plugins and skills:
   ```powershell
   $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe plugins update --all
   $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe skills update --all
   ```
5. Wait 15 seconds, then force-restart gateway:
   ```powershell
   Start-Sleep -Seconds 15
   $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe gateway stop
   Start-Sleep -Seconds 5
   $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe gateway start
   ```
6. Verify version: `$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe --version`

### 5. Rollback to Previous Version

1. Stop gateway:
   ```powershell
   $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe gateway stop
   Start-Sleep -Seconds 3
   ```
2. Find the latest backup and restore it:
   ```powershell
   $latestBackup = Get-ChildItem "$HOME\.hermes\backups\" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
   Write-Host "Restoring from: $($latestBackup.Name)"
   Expand-Archive -Path $latestBackup.FullName -DestinationPath $HOME\.hermes\ -Force
   ```
3. Restart gateway and verify:
   ```powershell
   $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe gateway start
   $version = $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe --version
   Write-Host "Current version: $version"
   ```

### 6. Set Up Weekly Auto-Update

> **Requires administrator privileges on Windows.** Creates a scheduled task that runs every Sunday at 02:00 AM.

1. Create script directory and write the auto-update script to `$HOME\.hermes\scripts\auto-update.ps1`:
   ```powershell
   New-Item -Path "$HOME\.hermes\scripts" -ItemType Directory -Force | Out-Null

   $updateScript = @'
   $updateTime = Get-Date -Format yyyyMMddHHmmss
   $backupPath = "$HOME\.hermes\backups\auto-update-$updateTime.zip"
   New-Item -Path "$HOME\.hermes\backups" -ItemType Directory -Force | Out-Null
   Compress-Archive -Path $HOME\.hermes\* -DestinationPath $backupPath -Force
   $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe gateway stop
   Start-Sleep -Seconds 5
   $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe update --backup --yes
   $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe plugins update --all
   $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe skills update --all
   Start-Sleep -Seconds 10
   $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe gateway stop
   Start-Sleep -Seconds 5
   $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe gateway start
   "$(Get-Date) - Auto-update completed" | Out-File "$HOME\.hermes\logs\auto-update.log" -Append
   '@
   $updateScript | Out-File "$HOME\.hermes\scripts\auto-update.ps1" -Encoding utf8
   ```

2. Register the scheduled task:
   ```powershell
   $taskAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File $HOME\.hermes\scripts\auto-update.ps1"
   $taskTrigger = New-ScheduledTaskTrigger -Weekly -At 02:00 -DaysOfWeek Sunday
   $taskSetting = New-ScheduledTaskSettingsSet -RunWhetherUserIsLoggedOnOrNot -Hidden
   Register-ScheduledTask -TaskName "Hermes-每周自动更新" -Action $taskAction -Trigger $taskTrigger -Settings $taskSetting -User $env:USERNAME -Force
   ```

3. Verify the task was created: `Get-ScheduledTask -TaskName "Hermes-每周自动更新"`

### 7. Cancel Weekly Auto-Update

```powershell
Unregister-ScheduledTask -TaskName "Hermes-每周自动更新" -Confirm:$false -ErrorAction SilentlyContinue
```

### 8. Configure China GitHub Mirror

Replaces the origin remote with a domestic mirror for faster downloads in mainland China:

```powershell
cd $HOME\.hermes\hermes-agent
git remote set-url origin https://ghfast.top/https://github.com/NousResearch/hermes-agent.git
git remote -v
```

### 9. Restore Official GitHub Remote

```powershell
cd $HOME\.hermes\hermes-agent
git remote set-url origin https://github.com/NousResearch/hermes-agent.git
git remote -v
```

### 10. Lock Current Version

Prevents automatic update checks to keep the current version stable:

```powershell
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config set update.auto_check false
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config set update.auto_update false
```

### 11. Unlock Version Updates

Re-enables automatic update checks:

```powershell
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config set update.auto_check true
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe config set update.auto_update true
```

### 12. Switch to Stable Branch (`main`)

```powershell
cd $HOME\.hermes\hermes-agent
git checkout main
git pull
```

### 13. Switch to Beta Branch (`develop`)

> **Warning:** Beta branch may contain unstable features. Not recommended for production environments.

```powershell
cd $HOME\.hermes\hermes-agent
git checkout develop
git pull
```

### 14. Switch to a Specific Version Tag

Replace `<version-tag>` with the target version (e.g., `v0.15.0`):

```powershell
cd $HOME\.hermes\hermes-agent
git checkout <version-tag>
```

### 15. Update All Plugins

```powershell
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe plugins update --all
```

### 16. Update All Skills

```powershell
$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe skills update --all
```

### 17. View Update History

```powershell
# Auto-update log (last 10 entries)
if (Test-Path "$HOME\.hermes\logs\auto-update.log") {
    Get-Content "$HOME\.hermes\logs\auto-update.log" -Tail 10
} else {
    Write-Host "No auto-update log found."
}

# Backup file list (10 most recent)
Write-Host "`nBackup files:"
Get-ChildItem "$HOME\.hermes\backups\" -Filter "*.zip" | Sort-Object LastWriteTime -Descending | Select-Object -First 10 | Format-Table Name, LastWriteTime -AutoSize

# Git history (last 10 commits)
Write-Host "`nGit update history:"
cd $HOME\.hermes\hermes-agent
git log --oneline -10
```

## Pitfalls

### Update fails with "permission denied" or "access denied"
- Run PowerShell as **Administrator** before executing any update procedure.
- For scheduled task creation (Procedure step 6), administrator privileges are mandatory.

### Bot becomes unresponsive after update
- Force-kill and restart the gateway:
  ```powershell
  taskkill /F /IM hermes.exe /T
  Start-Sleep -Seconds 3
  $HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe gateway start
  ```
- If the issue persists, execute the rollback procedure (Procedure step 5) to restore the previous version.

### Update download is very slow in China
- Execute Procedure step 8 (Configure China Mirror) **before** attempting any update that pulls from GitHub.
- Verify the mirror is active: `git -C $HOME\.hermes\hermes-agent remote -v`

### Scheduled task does not execute
- Verify the task exists in Windows Task Scheduler under the name "Hermes-每周自动更新" with status "Ready".
- Confirm the task was created with administrator privileges.
- Test the script manually: `powershell.exe -ExecutionPolicy Bypass -File $HOME\.hermes\scripts\auto-update.ps1`

### Plugins or skills fail to update after agent update
- Ensure the gateway is running before updating plugins/skills.
- Run the update commands separately (Procedure steps 15 and 16).
- Check for error output from `hermes plugins update --all` and `hermes skills update --all`.

### Skill does not trigger in the bot system
- Confirm the skill file is placed in the correct skills directory (`~/.hermes/skills/`).
- Verify the skill is enabled and visible: `hermes skills list | Select-String "auto-update"`
- Re-import the skill file if the frontmatter was modified.

## Verification

After completing any update procedure, verify success with these checks:

1. **Version verification:** Run `$HOME\.hermes\hermes-agent\.venv\Scripts\hermes.exe --version` — the output should match the expected target version.
2. **Gateway liveness:** Send a test message to the bot through any configured messaging platform. The bot should respond.
3. **Backup integrity:** Check `~/.hermes/backups/` for a new `.zip` file with a timestamp matching the update time. The file should be non-zero in size.
4. **Scheduled task (if configured):** Open Windows Task Scheduler and confirm "Hermes-每周自动更新" is present with status "Ready" and trigger "Weekly, Sunday at 02:00".
5. **Mirror configuration (if configured):** Run `git -C $HOME\.hermes\hermes-agent remote -v` — the `origin` remote should point to `https://ghfast.top/https://github.com/NousResearch/hermes-agent.git`.
