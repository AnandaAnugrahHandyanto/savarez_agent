## Pass #98 – Backup, Restore & Disaster Recovery Deep Dive – 2026-05-25T15:30:00Z

### Scope
Backup coverage (session DB, credentials, config), backup integrity (checksum, corruption detection), restore procedures, disaster recovery plans, and backup encryption.

---

### 1. Backup Coverage

#### 1.1 Curator Snapshot (`agent/curator_backup.py`)
**What it backs up:**
- `~/.hermes/skills/` as a `tar.gz` snapshot (excluding `.curator_backups/` and `.hub/`)
- Includes SKILL.md, scripts/, references/, templates/, assets/, `.usage.json`, `.archive/`, `.curator_state`, `.bundled_manifest`
- Also captures `cron/jobs.json` as `cron-jobs.json` alongside the tarball

**What's NOT backed up:**
- Session database (`state.db`) — not included
- Credentials (`auth.json`, `.env`) — not included
- Config (`config.yaml`) — not included
- Logs, sessions directory, gateway data

**Control:** Enabled by default (`curator.backup.enabled: true`), keep last 5 (`curator.backup.keep: 5`). These are the only tuning knobs.

**Gap — Session DB not backed up:** The session database (`state.db`) is the primary store for all conversation history and is never included in any automated backup. A catastrophic disk failure loses all sessions with no restore path.

#### 1.2 Profile Export (`hermes_cli/profiles.py` → `export_profile()`)
**What it backs up:** Full profile directory via `shutil.make_archive(base, "gztar", ...)` including config, skills, memories, cron, gateway, and (for default profile) credentials.

**Exclusion list (`_DEFAULT_EXPORT_EXCLUDE_ROOT`):**
```
"profiles",           # never recursive-export other profiles
"state.db", "state.db-shm", "state.db-wal",
"hermes_state.db",
"auth.json",           # API keys, OAuth tokens
".env",                # API keys (dotenv)
"logs/",
"cache/",
"optional-skills/",
```

**Critical: `state.db` is explicitly excluded from all profile exports.** Session history is not portable via `hermes profile export`. This is a deliberate design decision (the archive is meant to be portable/reasonable-size), but it means session transcripts cannot be restored from a profile export.

**Named profiles** additionally exclude `auth.json` and `.env` at the `shutil.copytree` level (hardcoded in the function, not config-driven). The default profile export does include credentials (`.env`, `auth.json`) — the only backup path that includes API keys.

#### 1.3 Pre-Update Backup (`hermes update --backup`)
Introduced in v0.12.0 ([#16539](https://github.com/NousResearch/hermes-agent/pull/16539), [#16566](https://github.com/NousResearch/hermes-agent/pull/16566)). Off by default (`update.backup: true` in config.yaml to enable). Creates a tar.gz snapshot of `HERMES_HOME` before pulling. Based on `shutil.make_archive` — same exclusion list as profile export. Also takes a lightweight snapshot of `~/.hermes/pairing/` even when `--backup` is off.

**Gap — `state.db` excluded:** Pre-update backup also explicitly excludes the session database, so a failed update that corrupts `state.db` cannot be restored from the backup.

#### 1.4 Session Export (`hermes sessions export`)
Manual JSONL export of sessions via `db.export_all()` / `db.export_session()`. Requires a running Hermes instance. Not scheduled, not automatic. No mechanism to export the raw SQLite file as a backup.

#### 1.5 Credentials
- `auth.json` and `.env` — excluded from named profile exports, included in default profile exports only
- No separate credentials backup mechanism
- No encrypted credential vault

---

### 2. Backup Integrity

#### 2.1 Checksum / Integrity Verification
**Finding: NONE FOUND.**

- No SHA256/MD5 hash computed for any backup file
- No checksum stored alongside `skills.tar.gz` in curator snapshots
- No checksum stored alongside profile export archives
- `tarfile` is used directly — no integrity hash
- gzip compression level 6 is used but no post-creation verification (e.g., extracting to check the archive is readable)

#### 2.2 Corruption Detection
- Curator: `tarfile.TarError` caught during creation → logs debug, deletes partial snapshot, returns `None`. The curator proceeds without aborting.
- During rollback: `archive.exists()` checked, but no extraction attempt until `tf.extractall()` — a corrupt gzip would surface as a TarError mid-extract.
- Profile import: `_safe_extract_profile_archive()` validates path safety but no integrity hash.

**Gap:** A corrupted `skills.tar.gz` (e.g., partial write) would not be detected until a rollback is attempted, and the error message ("snapshot extract failed") gives no indication of whether the archive itself is corrupted vs. an OS/filesystem error.

#### 2.3 Backup Verification
- No automated backup verification (no test-restore, no hash check)
- WAL checkpoint (`PRAGMA wal_checkpoint(PASSIVE/TRUNCATE)`) is used in `hermes_state.py` for DB consistency, but this is not a backup mechanism — it's just DB hygiene.

---

### 3. Restore Procedure

#### 3.1 Curator Rollback
Documented in `agent/curator_backup.py` (lines 530–668). Strategy:
1. Take a safety snapshot of current skills (`snapshot_skills(reason="pre-rollback to {target}")`) before touching anything — if this fails, bail out entirely.
2. Move current skills to `.rollback-staging-<ts>/` (implementation detail, not user-facing).
3. Extract target `skills.tar.gz` into `~/.hermes/skills/`.
4. On extract failure: move staged contents back (best-effort), return failure.
5. Reconcile cron skill-link fields from `cron-jobs.json` (surgical — only `skills`/`skill` fields on matched job IDs).
6. Delete staging dir after successful extract.

**Rollback safety:** The pre-rollback safety snapshot makes the rollback itself undoable. The safety snapshot goes into the regular backup pool and is subject to pruning.

**Path safety:** Extract rejects absolute paths and `..` path components. Python 3.12+ uses `filter="data"` for safer extraction; older versions fall back to unfiltered but still check for unsafe paths.

**Gap — No manifest hash verification:** `_read_manifest()` just reads `manifest.json` as JSON — no signature, no hash. A tampered manifest could report false size/counts.

#### 3.2 Profile Import
Profile import (`hermes_cli/profiles.py` → `_safe_extract_profile_archive()`) validates archive members before extraction, rejecting absolute paths and `..` components. It uses `shutil.copytree` with a custom ignore for credentials on named profiles.

**Gap — Not tested/verified:** No documented test of restore procedure. No "verify your backup works" guidance.

#### 3.3 Session DB Restore
**Finding: NO RESTORE PROCEDURE EXISTS for `state.db`.**

The session DB is never automatically backed up. There is no:
- Scheduled snapshot of the SQLite file
- Point-in-time recovery mechanism
- Restore command for session data

Session export (`hermes sessions export`) is the only session backup path, but it requires a running Hermes instance with a healthy database to export from — a corrupt DB cannot export itself.

---

### 4. Disaster Recovery

#### 4.1 DR Plan
**Finding: NO DISASTER RECOVERY PLAN EXISTS.**

No `DISASTER_RECOVERY.md`, no `DR_PLAN.md`, no runbooks, no BCP (Business Continuity Plan) documentation found anywhere in the repository.

#### 4.2 Runbooks
**Finding: NO RUNBOOKS FOUND.**

No runbooks for:
- How to recover from `state.db` corruption
- How to recover from accidental `hermes update` failure
- How to recover from profile deletion
- How to restore from a curator snapshot
- How to recover from credential loss

The only restore guidance is inline in CLI `--help` output and docstrings.

#### 4.3 DR Testing
**Finding: NO DR TESTING FOUND.**

- No mention of DR drills
- No `test_disaster_recovery.py`
- No documented test-restore procedure for any backup mechanism
- Curator rollback has no test file
- Profile import has no test file

#### 4.4 Recovery Time Objective (RTO) / Recovery Point Objective (RPO)
**Not defined.** No SLO/SLA for recovery time.

---

### 5. Backup Encryption

#### 5.1 Encryption at Rest
**Finding: NONE.** No backup file is encrypted.

- Curator snapshots (`skills.tar.gz`) are plain gzip-compressed tar files.
- Profile export archives (`.tar.gz`) are plain.
- Pre-update backups (`.tar.gz`) are plain.
- No mechanism to encrypt backups at rest.

#### 5.2 Encryption Key Management
**Finding: NOT APPLICABLE — no encryption exists.**

No backup encryption key management, no `backup.key` or similar, no envelope encryption.

#### 5.3 Unencrypted Backup Risks
- `skills.tar.gz` in `.curator_backups/` contains skill source code, cron job configs (which reference skill names and schedules), `.usage.json` (telemetry), `.curator_state`, and `.bundled_manifest`. If an attacker gains read access to `~/.hermes/skills/.curator_backups/`, they can read all skill source and cron configuration.
- Profile exports for the default profile include `auth.json` and `.env` (API keys, OAuth tokens) as plain tar.gz — a significant risk if the archive is stored on cloud storage or shared systems.
- Session export JSONL files contain full conversation history (including tool calls, tool results, and any sensitive data displayed in sessions). No encryption.

---

### 6. WAL Checkpoint (DB Hygiene)

`hermes_state.py` uses `PRAGMA wal_checkpoint(PASSIVE)` every N successful writes (line 429–440) and `PRAGMA wal_checkpoint(TRUNCATE)` during vacuum (line 3102). This keeps the WAL file from growing unbounded and ensures data is flushed to the main DB file, but it is not a backup mechanism — it just manages SQLite's write-ahead log.

---

### Summary Table

| Area | Status | Notes |
|------|--------|-------|
| Session DB backup | ❌ Missing | `state.db` never included in any backup |
| Credentials backup | ⚠️ Partial | Default profile includes them; named profiles exclude them |
| Config backup | ⚠️ Partial | Included in profile export but not curator snapshot |
| Curator snapshot | ✅ Exists | Skills + cron jobs, plain tar.gz, no encryption |
| Profile export | ✅ Exists | Full profile tar.gz, plain, excludes `state.db` |
| Pre-update backup | ✅ Exists (opt-in) | Plain tar.gz, excludes `state.db` |
| Backup integrity (checksum) | ❌ Missing | No SHA256/MD5 hash for any backup |
| Corruption detection | ⚠️ Weak | Only catch TarError during extract; no proactive check |
| Restore procedure (curator) | ✅ Documented | Pre-rollback safety snapshot, path sanitization |
| Restore procedure (profile) | ⚠️ Partial | Path validation but no verify/test step |
| Restore procedure (session DB) | ❌ Missing | No mechanism to restore `state.db` |
| DR plan | ❌ Missing | No DR plan, no runbooks, no BCP |
| DR testing | ❌ Missing | No test-restore for any backup |
| Backup encryption | ❌ Missing | All backups plain tar.gz |
| Encryption key management | ❌ N/A | No encryption to manage keys for |
| Unencrypted backup risk | ⚠️ High | Credentials in plain profile exports; skills in plain curator snapshots |

---

### Key Risks

1. **Session DB loss with no restore path** — `state.db` is never backed up. A disk failure or file system corruption loses all conversation history permanently. The only recovery path would be a filesystem-level snapshot (e.g., Time Machine) outside Hermes.

2. **No backup integrity verification** — No checksum means a corrupted backup is indistinguishable from a good one until a restore is attempted.

3. **Default profile exports include credentials in plain tar.gz** — `auth.json` and `.env` in an unencrypted archive is a significant exposure if the archive is stored anywhere other than local disk.

4. **Named profile exports exclude credentials** — This is a security decision but means credentials cannot be restored from a named profile export, requiring manual re-authentication.

5. **No DR plan or testing** — No runbooks, no documented recovery procedures beyond inline docstrings. No test-restore to verify backup usability.

6. **Curator snapshots are read-accessible** — Skills source code, cron job configs, and usage telemetry are stored in plain gzip files accessible to anyone with read access to `~/.hermes/skills/.curator_backups/`.

---

*Pass #98 audit complete. Key gap: no automated backup of `state.db`, no backup integrity verification, no disaster recovery plan, all backups unencrypted.*