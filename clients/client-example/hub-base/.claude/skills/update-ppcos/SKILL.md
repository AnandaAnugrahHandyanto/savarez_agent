---
name: update-ppcos
description: Update the ppcos CLI package and all hub + client skills to the latest stable version. Use for upgrades or when checking for updates.
argument-hint: "[--check]"
---

# Update ppcos

Updates the ppcos CLI package to the latest stable release, then updates all hub and client skills to match. Works from any directory — hub root or inside a client folder.

## Command Format

```
/update-ppcos              # Full update: CLI + skills
/update-ppcos --check      # Check for updates without installing
```

## Process

### Phase 1: Login

The session token expires every 24 hours, so always re-authenticate before doing anything.

1. **Resolve email address:**

   First, find the hub root by walking up from the current directory looking for `main-config.json` or `my-brand/`. Then check for an existing email in `my-brand/brand.json`:

   - If `my-brand/brand.json` exists and has a non-empty `company.email` field:
     - Ask via AskUserQuestion: "Is **{email}** the email for your ppcos account? (yes / enter a different one)"
     - If the user confirms: use that email.
     - If the user provides a different one: use the one they gave.
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

6. Confirm: "Logged in as {email}. Session expires: {expiresAt formatted}."

### Phase 1.5: Repository Safety Check

Ensure the hub repo has a `.gitignore` that covers sensitive files, credentials, and build artifacts at every directory level.

1. **Locate the hub root** (already resolved during Phase 1 login).

2. **Check for `.gitignore`** at the hub root:

   - If it **does not exist** → create it with the full required pattern set below.
   - If it **exists** → read it and check which required patterns are missing. Append only the missing ones under a clearly marked section.

3. **Required `.gitignore` patterns:**

   ```gitignore
   # === ppcos managed patterns (do not remove) ===

   # Secrets & environment
   .env
   .env.*
   .env.local
   .env.production

   # Keys & certificates
   *.pem
   *.key
   *.p12
   *.pfx
   *.jks

   # Credentials
   credentials.json
   *-credentials.json
   secrets.json
   service-account*.json

   # Node
   node_modules/

   # OS & IDE
   .DS_Store
   Thumbs.db
   .vscode/
   .idea/

   # Temp & logs
   tmp/
   *.log
   ```

   When appending to an existing file, add a blank line before the section header. Do not duplicate patterns that already exist in the file — skip any pattern that is already present (even if written slightly differently, e.g. `node_modules` vs `node_modules/`).

4. **Check for tracked files that should now be ignored:**

   Run:

   ```bash
   git ls-files -i --exclude-standard
   ```

   - If the command returns **no output** → everything is clean, proceed silently.
   - If it returns **any files** → this means sensitive or ignored files are still tracked in git. **Do NOT auto-fix.** Instead:

     1. Show the user the list of tracked-but-ignored files.
     2. Warn clearly:
        ```
        ⚠️  These files are in .gitignore but still tracked by git.
        They will continue to appear in commits until explicitly untracked.
        ```
     3. Provide the fix command but **do not run it** without user consent:
        ```
        To untrack them (keeps local copies, removes from git):
          git rm --cached <file1> <file2> ...
        Then commit the change.
        ```
     4. Ask via AskUserQuestion: "Want me to untrack these files now? (yes / no / skip)"
        - If **yes** → run `git rm --cached` for each file, then tell the user to commit when ready.
        - If **no** or **skip** → continue to Phase 2.

     **Note:** Untracking removes files from the index only — local copies are preserved. However, the files remain in git history. If any of these are actual secrets (API keys, tokens, passwords), advise the user to rotate those credentials since git history is not cleaned by this step.

### Phase 2: Update CLI Package

1. **Get current installed version:**

   ```bash
   ppcos --version
   ```

   Store as `currentVersion`.

2. **Check latest available version:**

   ```bash
   npm view ppcos version 2>/dev/null
   ```

   Store as `latestVersion`.

   - If this command fails, tell the user: "Could not check latest version. Verify your internet connection and npm registry access." — then stop.

3. **Compare versions:**
   - If `--check` flag: show `ppcos v{currentVersion} — latest is v{latestVersion}` and stop.
   - If `currentVersion` equals `latestVersion`: tell the user the CLI is up to date and skip to Phase 3.
   - If `latestVersion` is newer: proceed with install.

4. **Install the update:**

   ```bash
   npm install -g ppcos@latest
   ```

   - If this fails with `EACCES` or permission error, tell the user:
     ```
     Permission denied. Try one of:
       1. Run with sudo:  sudo npm install -g ppcos@latest
       2. Fix npm permissions: https://docs.npmjs.com/resolving-eacces-permissions-errors-when-installing-packages-globally
     ```
     Ask via AskUserQuestion whether they want to retry with sudo or stop. If they choose sudo, run `sudo npm install -g ppcos@latest`. If it fails again, stop.

   - If this fails for another reason, show the error and stop.

5. **Verify the update:**

   ```bash
   ppcos --version
   ```

   Confirm the version now matches `latestVersion`. If not, warn: "Update command ran but version is still v{currentVersion}. Try `npm cache clean --force` and retry."

   Report: `ppcos CLI updated: v{currentVersion} → v{latestVersion}`

### Phase 3: Update Skills

Run the skills update:

```bash
ppcos update
```

This updates hub skills (`.managed-hub.json`) and all client skills (`.managed.json`).

If the command detects modified files in a client, it shows a conflict prompt with options including `d` to view differences. Use the `d` option to view the diff, then explain to the user what changed in plain language — e.g., "The account-auditor skill added two new diagnostic fields" or "The query file was updated with campaign experiment filtering." Then ask the user what they want to do and enter their choice.

### Phase 4: Summary

```
ppcos update complete!

  CLI:    v{previousVersion} → v{newVersion}
  Skills: Updated via ppcos update

Run `ppcos status` to verify all clients.
```

If the CLI was already current:

```
ppcos update complete!

  CLI:    v{currentVersion} (already up to date)
  Skills: Updated via ppcos update

Run `ppcos status` to verify all clients.
```

## Error Handling

| Error | Message |
|-------|---------|
| Not a git repo | "This directory is not a git repository. `.gitignore` check skipped." — continue to Phase 2. |
| `git ls-files` fails | "Could not check tracked files. Verify you're inside a git repository." — continue to Phase 2. |
| Send-code API fails | Show API error. Suggest: "Check your email address and internet connection." |
| Invalid verification code | "Verification failed. Double-check the 6-digit code and try again." |
| No internet / npm unreachable | "Could not check latest version. Verify your internet connection and npm registry access." |
| Permission denied on npm install | Offer sudo retry or link to npm permissions fix. |
| npm install fails (other) | Show the error output. Suggest: "Check npm logs for details." |
| ppcos update fails (auth) | "Authentication may have failed. Run `/update-ppcos` again." |
| Version unchanged after install | "Version still v{currentVersion}. Try `npm cache clean --force` and retry." |

## Notes

- This skill works from **any directory** — hub root or client folder. The npm install is global, and `ppcos update` discovers clients from the current working directory.
- Never run `sudo` without explicit user consent.
- The login step always runs first. Even if the session looks valid, re-authenticate to avoid mid-update expiry.
