---
name: health-check
description: Verify hub and client setups — manifest integrity, hooks, config files, version drift, and data hygiene. Use for health checks or to diagnose setup issues.
argument-hint: "[client-name]"
---

# Health Check

Read-only audit of the ppcos hub and all (or one) client workspace. Reports manifest integrity, registry drift, hook health, version drift, context freshness, and data bloat. Never modifies files.

## Command Format

```
/health-check                  # Audit hub + all clients
/health-check <client-name>    # Audit hub + one specific client
```

## Path Resolution

**Must be run from the hub root.**

1. Check current directory for `main-config.json` or `clients/` directory.
2. If not found, walk up parent directories until found.
3. If the current directory is inside `clients/<name>/`, resolve up to the hub root before proceeding.

If no hub root is found: "Could not find hub root (no main-config.json). Run `ppcos init` from your hub directory first."

## Process

Run Phases 0–7 in order, collecting results as you go. Emit the final report only after all phases finish.

### Phase 0: Login

The session token expires every 24 hours. Re-authenticate before running the remote version checks in Phase 5 so the skill bundle version lookup doesn't fail mid-run.

1. **Resolve email address:**

   Walk up from the current directory to find the hub root (already done during path resolution). Then check for an existing email in `my-brand/brand.json`:

   - If `my-brand/brand.json` exists and has a non-empty `company.email` field:
     - Ask via AskUserQuestion: "Is **{email}** the email for your ppcos account? (yes / enter a different one)"
     - If confirmed: use that email. If the user provides a different one: use the one they gave.
   - If `my-brand/brand.json` doesn't exist or has no email:
     - Ask via AskUserQuestion: "What's the email address linked to your ppcos account?"

2. **Send verification code** — call the API directly:

   ```bash
   curl -s -X POST https://ppcos.vercel.app/api/auth/send-code \
     -H "Content-Type: application/json" \
     -d '{"email": "{email}"}'
   ```

   The response returns `{ "token": "...", "message": "..." }`. Store the `token` value — it's needed for verification.

   - If the request fails or returns an error, show the error message and stop.
   - On success, tell the user: "Verification code sent — check your email."

3. **Ask for the 6-digit code** via AskUserQuestion:
   - "Enter the 6-digit verification code from your email:"

4. **Verify the code** — call the API:

   ```bash
   curl -s -X POST https://ppcos.vercel.app/api/auth/verify-code \
     -H "Content-Type: application/json" \
     -d '{"email": "{email}", "code": "{code}", "token": "{token}"}'
   ```

   The response returns `{ "email": "...", "sessionToken": "...", "expiresAt": "..." }`.

   - If verification fails, show the error and stop.

5. **Store the session** — read `~/.ppcos/config.json`, set the `auth` field, and write it back:

   ```json
   {
     "auth": {
       "email": "{email}",
       "sessionToken": "{sessionToken}",
       "expiresAt": "{expiresAt}"
     }
   }
   ```

   Preserve any other existing keys in the config file. Create `~/.ppcos/` directory if it doesn't exist.

6. Confirm: "Logged in as {email}. Running health check..."

Hold onto `sessionToken` for Phase 5.

### Phase 1: Core status via `ppcos status`

Run:

```bash
ppcos status
```

Parse the output. This already covers:

- Hub + client manifest integrity (modified/missing files)
- `baseVersion` vs currently installed `ppcos` package version
- Conflict log entries
- Custom skill listing
- Config file listing
- Auth session state + expiry
- Branding configuration

If `ppcos status` fails to run, record the failure and continue with the remaining phases — do not stop.

Store for the report:
- Per target: `version`, `updateAvailable`, `modifiedFiles`, `missingFiles`, `conflicts`
- Global: `authState`, `packageVersion`

### Phase 2: Registry drift (`main-config.json` ↔ filesystem)

1. Read `main-config.json` at the hub root. If missing: warn "no main-config.json — clients managed individually".
2. List `clients/` directory and filter to folders containing `.managed.json`.
3. Compare:
   - **Orphan folders**: clients with `.managed.json` not listed in `main-config.json`.
   - **Stale entries**: entries in `main-config.json` with no matching folder or no `.managed.json`.
   - **Disabled**: entries where `enabled: false` — report as info, not warning.

### Phase 3: Config file presence

For hub root and each client, verify these files **exist** (they are init-only and never checksummed, but missing = broken):

| Scope | File |
|-------|------|
| Client | `config/ads-context.config.json` |
| Client | `config/.env` |
| Client | `context/business.md` |
| Client | `.claude/settings.local.json` |
| Hub | `my-brand/brand.json` (warn only — optional until branding is configured) |

Missing any of the three client files = ✗. Missing `settings.local.json` = ⚠.

### Phase 4: Hook health (OS-aware)

Expected hook files per client, under `clients/<name>/.claude/hooks/`:

- `post-compact-reminder.sh`
- `session-context-check.sh`
- `stop-memory-check.sh`

For each hook file:

1. **All OSes**: file exists, is non-empty, first line starts with `#!`.
2. **macOS / Linux** (detect with `uname` — anything other than `MINGW*`, `CYGWIN*`, `MSYS*`):
   - Executable bit set. Check with:
     ```bash
     test -x "<path>" && echo ok || echo noexec
     ```
   - Syntax valid:
     ```bash
     bash -n "<path>" 2>&1
     ```
3. **Windows** (`MINGW*`, `CYGWIN*`, `MSYS*`, or Node `process.platform === 'win32'`):
   - Skip the executable-bit and `bash -n` checks — unreliable on Windows filesystems.
   - Verify `bash` is resolvable once per run:
     ```bash
     where bash 2>nul || which bash 2>/dev/null
     ```
     If nothing is returned, emit a single hub-level warning: "hooks need Git Bash or WSL installed to run — install from https://git-scm.com/download/win". Do not repeat per client.

Never run `chmod`. Never modify hook files. Report-only.

### Phase 5: Remote version drift (live)

Two lookups, both once per run (not per client):

1. **CLI package version** — via npm:

   ```bash
   npm view ppcos version 2>/dev/null
   ```

   Store as `latestCliVersion`. Compare with the installed package version reported by Phase 1 (`ppcos status` footer or `ppcos --version`).

2. **Skill bundle version** — via the ppcos backend, using the session token from Phase 0:

   ```bash
   curl -s https://ppcos.vercel.app/api/skills/version \
     -H "Authorization: Bearer {sessionToken}"
   ```

   Store the returned version as `latestSkillVersion`. Compare with each target's manifest `baseVersion` (already collected in Phase 1).

Report:

- `latestCliVersion` > installed → ⚠ "ppcos CLI is v{installed}, latest is v{latestCliVersion} → run /update-ppcos"
- Any target's `baseVersion` < `latestSkillVersion` → ⚠ per target: "skills are v{baseVersion}, latest is v{latestSkillVersion} → run /update-ppcos"
- Both equal → ✓
- Either call fails / offline → mark the specific check as "skipped — offline" and continue. Do not fail the whole phase.

### Phase 6: Context freshness

For each client:

1. **Memory log** — list files in `clients/<name>/context/memory/` matching `YYYY-MM-DD.md`. Find the newest by filename.
   - No files → ⚠ "no memory log entries yet".
   - Newest > 3 days old → ⚠ "last memory entry is {N} days old".
   - Otherwise → ✓.
2. **Account changelog** — stat `clients/<name>/context/account-changelog.md`.
   - Missing → ⚠ "no account-changelog.md — run /account-changelog".
   - mtime > 7 days ago → ⚠ "account-changelog is {N} days stale — run /account-changelog".
   - Otherwise → ✓.

Compute "days old" from today's date vs the file date (ISO filename for memory, mtime for changelog).

### Phase 7: Data bloat

For each client, scan these directories and apply thresholds. Never delete — report only.

| Directory | Threshold |
|-----------|-----------|
| `context/google-ads/data/` | `>20` files OR `>50` MB total |
| `context/competitor-ads/` | `>15` files OR `>25` MB total |
| `created/rsas/` | `>10` files OR any file `>30` days old |
| `created/` (total) | `>100` MB |
| Any single file anywhere under the client | `>10` MB |
| `context/` + `created/` combined | `>200` MB |

Use one `du`/`find` pass per client to keep it fast:

```bash
# macOS / Linux
find "clients/<name>/context" "clients/<name>/created" -type f -printf "%s %p\n" 2>/dev/null
# or, if printf is unsupported (BSD find on macOS):
find "clients/<name>/context" "clients/<name>/created" -type f -exec stat -f "%z %N" {} \;
```

For Windows/MSYS, fall back to a Node one-liner via `node -e` that walks the directory with `fs.readdirSync({ recursive: true })` and sums sizes — or simply use `du -sk` if available in Git Bash.

Report each threshold breach as a single line with the directory, counts, and size. Do not list individual files unless there are 3 or fewer.

## Output Format

Emit a single markdown report. Group by target: hub first, then each client. One line per check with `✓` / `⚠` / `✗` and, for non-✓, the exact fix command.

```
# ppcos health report — {YYYY-MM-DD HH:MM}

## Hub
✓ Manifest integrity — 0 modified, 0 missing
✓ Hook runtime — bash resolved
⚠ CLI version drift — installed v{X}, latest v{Y} → run: /update-ppcos
✓ Branding configured ({brand name})

## clients/{client-name}
✓ Manifest integrity — 0 modified, 0 missing
✓ Registry entry in main-config.json
✗ Missing config file: context/business.md → run: /business-context-gatherer
⚠ Account-changelog is 12 days stale → run: /account-changelog
⚠ Data bloat — context/google-ads/data has 34 files (72 MB) → review & archive
✓ Hooks: 3/3 present and executable

## Summary
  Targets checked: {N}
  ✓ Pass:     {count}
  ⚠ Warning:  {count}
  ✗ Error:    {count}
```

Finish with:

- If any `✗` → "One or more critical issues found. Fix the ✗ items before running audits or updates."
- If only `⚠` → "Setup is functional but has {N} warnings. Address when convenient."
- If all `✓` → "All checks passed. Setup is healthy."

## Error Handling

| Error | Message |
|-------|---------|
| Hub root not found | "Could not find hub root (no main-config.json). Run `ppcos init` from your hub directory first." |
| Client argument not found | "Client `{name}` not found in `clients/` directory." |
| `ppcos status` fails | Record the failure, note it in the report, continue with other phases. |
| Send-code API fails | Show API error. Suggest: "Check your email address and internet connection." |
| Invalid verification code | "Verification failed. Double-check the 6-digit code and try again." |
| `npm view` offline / fails | Mark the CLI version check in Phase 5 as "skipped — offline" and continue. |
| `/api/skills/version` fails | Mark the skill bundle check in Phase 5 as "skipped — offline" and continue. |
| Hook file unreadable | Report ✗ with the filesystem error message. |
| Permission denied on a directory | Report ⚠ with "permission denied scanning {path}" and continue. |

## Notes

- Read-only. This skill never writes files, runs updates, or modifies configuration. It diagnoses and points at fix commands.
- Fix commands in the report should reference other ppcos skills by slash name (`/update-ppcos`, `/account-changelog`, `/business-context-gatherer`) or CLI commands (`ppcos update`, `ppcos login`) — never raw shell workarounds.
- Do not spawn subagents for individual checks. One pass, one report.
- Safe to re-run as often as the user wants — no side effects.
