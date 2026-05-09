# Debugging Session Notes: Source Watcher Silent Wedge

## 2026-05-09 — End-to-end gate test

### What happened

Ran an E2E watcher gate test:
1. Planted `_test_gate_broken.py` (F821: undefined name) under `/opt/data/repo/scripts/`
2. Waited 4 min → watcher correctly refused the commit ✓
3. Deleted the file, waited 4 min for "recovery commit"
4. **Recovery never came.** Watcher appeared frozen — no new log output for 7+ minutes.

### Investigation: Why no recovery commit?

**Root cause of the hang:** The test was designed incorrectly. The broken file was planted as an **untracked** file (`?? _test_gate_broken.py`). Git only commits files that are staged (via `git add`). An untracked file is invisible to the watcher — it doesn't appear in `git status --porcelain` as a tracked change, so the watcher has nothing to commit after deletion.

**Recovery IS automatic** — but only for tracked files. Once the broken file was staged and blocked, then deleted:
- `git reset` (defensive, at top of `commit_and_push()`) unstages it
- Watcher sees a new deletion in `git status --porcelain`
- Debounce fires → commits the deletion → gate passes (deletion has no Python to lint)

The test design made it *look* like the watcher was wedged when it was actually behaving correctly.

### The Silent Wedge Pattern

When a daemon process appears to hang with no output, no errors, but the process is alive:

**Symptoms:**
- Process PID exists, no zombie
- `ps aux | grep process` shows running
- Log file mtime frozen (no new writes)
- No errors in log
- `git status --porcelain` from terminal shows clean tree
- `/proc/<pid>/fd/1 -> logfile` (stdout still open to log path)

**Diagnostic checklist:**
```
# 1. Confirm process alive and stdout still connected
ps aux | grep <name>
stat /proc/<pid>/fd/1   # inode should match log file

# 2. Confirm log file NOT growing
stat /path/to/log
sleep 30
stat /path/to/log   # mtime should change if process writing

# 3. Check git state from terminal (independent of watcher)
cd /opt/data/repo && git status --porcelain

# 4. Check what syscall the process is currently in (if readable)
cat /proc/<pid>/syscall

# 5. Check memory maps
cat /proc/<pid>/maps | tail -5

# 6. Verify tree is actually clean from subprocess POV
python3 -c "import subprocess; r=subprocess.run(['git','status','--porcelain'],capture_output=True,text=True); print(r.stdout)"
```

**Key insight:** The watcher loop calls `git("add", "-A")` before lint. If lint fails and `commit_and_push()` returns early, the file remains staged. On the NEXT cycle, `changed_files(porcelain_status())` returns the staged file — even if it's been deleted from the worktree. This creates a staged-deletion mismatch that `git commit` handles gracefully (commits the deletion), BUT the lint gate runs on staged Python files and may fail again if the deletion hasn't cleared the staging area. The defensive `git reset` at top of `commit_and_push()` (added in fix commit `b12fd7b`) resolves this — it clears leftover staging before every attempt.

### The Watcher Staging Defect (fixed in b12fd7b)

**Before fix:** After lint blocked a commit, the broken file remained in the git index (staged). Subsequent cycles kept trying to commit the staged-but-lint-failed file, getting stuck in a loop. Git status from terminal showed the file as staged (`A  _test_gate_broken.py`) but the worktree was clean — a mismatch that confused debugging.

**Fix:** `git reset` (index-only, no worktree impact) at the top of `commit_and_push()`, clearing any leftover staging from prior failed attempts.

**Verification:** After the fix, `git status --porcelain` correctly shows `?? _test_gate_broken.py` (untracked) during the gate-blocked phase — not staged.

### E2E Gate Test Recipe (corrected)

To test the watcher gate with a broken file that will actually be recoverable:

```bash
# 1. Plant a broken tracked file (git add first so it's in the index)
cat > /opt/data/repo/scripts/_test_gate_broken.py <<'EOF'
def _broken(): return UNDEFINED_GATE_TEST_MARKER
EOF
cd /opt/data/repo && git add scripts/_test_gate_broken.py
# git status --porcelain now shows: A  scripts/_test_gate_broken.py

# 2. Wait 4 min for watcher debounce → REFUSING to commit (gate blocks)

# 3. Verify staging state — should still be A (staged), not untracked
cd /opt/data/repo && git status --porcelain

# 4. Delete and unstage
rm /opt/data/repo/scripts/_test_gate_broken.py
cd /opt/data/repo && git reset HEAD -- scripts/_test_gate_broken.py
# git status --porcelain now shows: D  scripts/_test_gate_broken.py

# 5. Wait 4 min → watcher commits the deletion, gate passes
```

### Key Watcher Code Locations

| Concern | File | Key lines |
|---------|------|-----------|
| Defensive index reset | `scripts/source_watcher.py` | 438–448 |
| Lint gate + block | `scripts/source_watcher.py` | 217–270 |
| Staged Python files for lint | `scripts/source_watcher.py` | 132–146 |
| Debounce loop | `scripts/source_watcher.py` | 532–571 |
| Blocked lint log | `scripts/source_watcher.py` | 180–196 |
| Telegram notification | `scripts/source_watcher.py` | 335–357 |
