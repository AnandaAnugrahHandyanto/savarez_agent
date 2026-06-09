# Apollo Desktop Source-of-Truth Restore Runbook

**Capture Date:** 2026-06-09T11:51:08Z  
**Source Repo:** https://github.com/NousResearch/hermes-agent.git  
**Branch:** `preserve/scott-desktop-20260607T054234Z`  
**HEAD (short):** `957533d76`  
**Desktop Package Version:** `0.15.1`

---

## Source-of-Truth Location

- **Laptop repo path:** `C:\Users\Testing03\AppData\Local\hermes\hermes-agent`
- **Capture folder:** `scott-desktop-source-of-truth/20260609T115108Z`
- **Profile path:** `C:\Users\Testing03\AppData\Local\hermes\profiles\scott-omega-profile`

---

## Critical Configuration Facts

### Apollo MS Teams Bidirectional Session Sharing

The `scott-omega-profile` is configured with:
- `X-Hermes-Session-Id` and `X-Hermes-Session-Key` headers
- These are merged into custom-provider OpenAI client requests
- **Restore requirement:** Preserve these header configurations exactly; do not regenerate or rotate keys

### Custom Provider Switching

Named custom providers must be preserved:
- `custom:apollo`
- `custom:omega`

**Critical:** The `/api/model/set` endpoint must NOT blank `model.base_url`. This is a known issue that must be avoided during restore.

### Desktop-Only Profile Lock/Filter

The `scott-omega-profile` has Desktop-specific lock/filter configuration that must be preserved. This prevents profile drift across environments.

### Profile Seeding Files

The following files seed the `scott-omega-profile` and must be restored in order:
1. `SOUL.md`
2. `README.md`
3. `SCOTT_PROFILE_CONTEXT.md`
4. `FACTS.md`
5. `memories/USER.md`
6. `memories/MEMORY.md`
7. `memory_store.db`

### Holographic Memory Configuration

- `memory.provider` is set to `holographic`
- `memory_store.db` must be present
- **Do not expose private fact text** in logs or summaries

---

## Source-of-Truth Files

The capture folder contains:

| File | Purpose |
|------|---------|
| `manifest.json` | Artifact manifest with SHA-256 checksums |
| `custom-source.patch` | Custom provider configuration patch |
| `config.redacted.yaml` | Redacted configuration (no secrets) |
| `profile-config-summary.json` | Profile configuration summary |
| `holographic-memory-db-summary.json` | Memory DB summary (no private facts) |
| `profile-*` | Profile directory copies |
| `git-*` | Git state evidence (log, status, diff) |
| `diff-*` | Code diff evidence |

---

## Restoration Checklist

### 1. Repository Checkout

```bash
git clone https://github.com/NousResearch/hermes-agent.git
cd hermes-agent
git checkout preserve/scott-desktop-20260607T054234Z
git status  # Verify clean working tree
```

### 2. Apply Custom Configuration

```bash
# Review patch before applying
git apply --stat custom-source.patch

# Apply patch
git apply custom-source.patch

# Verify changes
git status
git diff --stat
```

### 3. Profile Restoration

Restore profile directory from capture:

```bash
# Copy profile directory (preserve permissions)
xcopy /E /I /K profile-sources/scott-omega-profile/ C:\Users\Testing03\AppData\Local\hermes\profiles\scott-omega-profile\

# Or on Linux/macOS:
cp -r profile-sources/scott-omega-profile/* C:\Users\Testing03\AppData\Local\hermes\profiles\scott-omega-profile/
```

Verify seeding files are present:
- `SOUL.md`
- `README.md`
- `SCOTT_PROFILE_CONTEXT.md`
- `FACTS.md`
- `memories/USER.md`
- `memories/MEMORY.md`
- `memory_store.db`

### 4. Build Verification

```bash
# Type checking
npm run type-check

# Build
npm run build

# Packaged executable build
npm run builder -- --dir
```

### 5. Executable Verification

```bash
# Verify executable exists
dir apps\desktop\release\win-unpacked\Hermes.exe

# Verify SHA-256 hash
certutil -hashfile apps\desktop\release\win-unpacked\Hermes.exe SHA256
# Expected: f89e2a2b437f44027dcbfb644812b0463cc40f256191b74e7141fd5ffe1bb139
```

### 6. Configuration Validation

```bash
# Parse YAML config (verify no syntax errors)
python -c "import yaml; yaml.safe_load(open('config.redacted.yaml'))"

# Review custom provider configuration
cat config.redacted.yaml | findstr /C:"custom:apollo" /C:"custom:omega"
```

### 7. Provider Probes (No Secret Exposure)

Test custom provider connectivity WITHOUT printing keys:

```bash
# Probe custom:apollo (sanitized response only)
curl -s -X POST http://localhost:8765/api/model/set \
  -H "Content-Type: application/json" \
  -d '{"model": "custom:apollo"}' \
  | jq '.status // .error'

# Probe custom:omega (sanitized response only)
curl -s -X POST http://localhost:8765/api/model/set \
  -H "Content-Type: application/json" \
  -d '{"model": "custom:omega"}' \
  | jq '.status // .error'
```

**Expected:** Both probes return success status without exposing `X-Hermes-Session-Key`.

### 8. Desktop Smoke Tests

```bash
# Launch Desktop (non-blocking)
start apps\desktop\release\win-unpacked\Hermes.exe

# Wait for startup
timeout /t 10

# Verify process is running
tasklist | findstr Hermes.exe

# Check Teams session sharing endpoint (sanitized)
curl -s http://localhost:8765/api/session/status | jq '.session_id // empty'
```

### 9. Holographic Memory Verification

```bash
# Verify memory_store.db exists and is accessible
python -c "import sqlite3; conn = sqlite3.connect('memory_store.db'); print('Tables:', [t[0] for t in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")])"

# Verify holographic provider is configured
python -c "import yaml; cfg = yaml.safe_load(open('config.redacted.yaml')); print('Memory provider:', cfg.get('memory', {}).get('provider', 'NOT SET'))"
```

**Expected:** Output shows `holographic` as the memory provider.

### 10. Final Validation

```bash
# Verify no secrets in restored files
findstr /S /I /C:"sk-" /C:"Bearer " /C:"xoxb-" /C:"ghp_" . 2>nul
# Expected: No matches (or only in expected credential files)

# Verify git state is clean
git status --short
# Expected: No output (clean working tree)

# Verify manifest checksums
python -c "import json, hashlib; m = json.load(open('manifest.json')); [print(f'{f[\"path\"]}: {f[\"sha256\"][:16]}...') for f in m['files']]"
```

---

## Known Issues to Avoid

1. **`/api/model/set` blanking `model.base_url`**: This is a known bug. After restore, verify `model.base_url` is preserved for custom providers.

2. **Profile drift**: Ensure `scott-omega-profile` lock/filter is active. Desktop should not accidentally load other profiles.

3. **Holographic memory private facts**: Do not query or expose private fact text in logs. Use summary endpoints only.

4. **Session key rotation**: Do NOT regenerate `X-Hermes-Session-Key`. The capture contains the working key; preserve it exactly.

---

## Rollback Procedure

If restore fails:

1. **Revert patch:**
   ```bash
   git checkout -- .
   git clean -fd
   ```

2. **Restore original profile:**
   ```bash
   # If backup exists, restore it
   # Otherwise, re-clone from source branch
   ```

3. **Verify executable:**
   ```bash
   # Rebuild if necessary
   npm run build
   npm run builder -- --dir
   ```

---

## Contact & Escalation

- **Primary maintainer:** Apollo (fleet peer)
- **Escalation path:** Vector (fleet coordinator)
- **Vault journal:** Use `vault-journal` to record restore outcomes
- **Fleet call:** Use `fleet-call` for cross-agent coordination

---

**Last Updated:** 2026-06-09T11:51:08Z  
**Capture Hash:** Refer to `manifest.json` for full artifact checksums
