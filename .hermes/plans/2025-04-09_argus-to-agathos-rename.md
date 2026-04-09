# Argus → Agathos Rename Plan

> **For Hermes:** Use integration-preserving-refactoring skill to execute this rename phase-by-phase.

**Goal:** Rename the entire Argus program to Agathos while preserving all Hermes integrations, config compatibility, and functionality.

**Architecture:** Phased rename with verification at each step. Package name, class name, CLI name, paths, and config keys all updated systematically.

**Tech Stack:** Python 3.12, Hermes-agent integration, launchd daemon, SQLite state.

---

## Integration Points (MUST PRESERVE)

These Hermes integrations must work exactly the same after rename:

1. **cron.jobs imports** — `from cron.jobs import list_jobs` (argus.py line 65-67)
2. **SessionDB import** — `from hermes_state import SessionDB, DEFAULT_DB_PATH` (argus.py line 68)
3. **Config loader** — `from hermes_cli.config import load_config as _hermes_load_config` (argus.py line 69)
4. **CONFIG.get() toggles** — All 13+ module toggles checked via CONFIG
5. **CLI integration** — `hermes` binary subprocess calls preserved
6. **Database schema** — argus.db → agathos.db with same tables
7. **Log paths** — ~/hermes/logs/argus → ~/hermes/logs/agathos
8. **PID file** — argus.pid → agathos.pid

---

## Phase 1: Package Directory Rename

**Objective:** Rename `argus/` directory to `agathos/`

**Files:**
- Rename: `~/Projects/hermes-dev/argus/` → `~/Projects/hermes-dev/agathos/`

**Commands:**
```bash
cd ~/Projects/hermes-dev
mv argus agathos
```

**Verification:**
```bash
ls -la agathos/
ls argus/ 2>&1 | grep "No such file"
```

---

## Phase 2: Main Module and Class Rename

**Objective:** Rename `argus.py` to `agathos.py` and `class Argus` to `class Agathos`

**Files:**
- Rename: `agathos/argus.py` → `agathos/agathos.py`
- Modify: `agathos/agathos.py` — class name and docstring

**Step 1: Rename file**
```bash
cd ~/Projects/hermes-dev/agathos
mv argus.py agathos.py
```

**Step 2: Update class name in agathos.py**

Find:
```python
class Argus:
    """ARGUS — Agent Resource Guardian & Unified Supervisor"""
```

Replace:
```python
class Agathos:
    """AGATHOS — Agent Guardian & Health Oversight System"""
```

**Step 3: Update docstring references**

Find: `ARGUS — Agent Resource Guardian & Unified Supervisor`
Replace: `AGATHOS — Agent Guardian & Health Oversight System`

Find: `The Hundred-Eyed Watchman`
Replace: `The Vigilant Guardian`

**Verification:**
```bash
grep -n "class Agathos" agathos/agathos.py
grep -n "class Argus" agathos/*.py  # Should find nothing
```

---

## Phase 3: Update agathos/__init__.py

**Objective:** Update exports and imports in the package __init__.py

**Files:**
- Modify: `agathos/__init__.py`

**Changes:**
1. Docstring: `"""Argus - Agent Resource...` → `"""Agathos - Agent Guardian...`
2. Import: `from .argus import Argus` → `from .agathos import Agathos`
3. Export: `"Argus",` → `"Agathos",`
4. All daemon management function names: `argus_*` → `agathos_*`

**Verification:**
```bash
python3 -c "from agathos import Agathos; print('✓ Import works')"
```

---

## Phase 4: Update All Internal Module Imports

**Objective:** Change all `from argus` and `from .argus` imports to `from agathos` and `from .agathos`

**Files to modify (in agathos/):**
- actions.py — imports from sibling modules
- audit.py — imports
- circuit_breaker.py — imports
- cleanup.py — imports
- cli.py — imports
- cost_monitor.py — imports
- daemon_mgmt.py — imports
- directives.py — imports
- directives_schema.py — imports
- drift.py — imports
- entropy.py — imports
- hermes_fallback.py — imports
- memory_compat.py — imports
- metrics.py — imports
- ml_data.py — imports
- notifications.py — imports
- provider_health.py — imports
- resources.py — imports
- setup.py — imports
- subprocess_utils.py — imports
- venv_utils.py — imports
- wal_monitor.py — imports

**Pattern:**
```python
# Before:
from argus.something import x
from .argus import Argus

# After:
from agathos.something import x
from .agathos import Agathos
```

**Verification:**
```bash
python3 -m py_compile agathos/*.py
```

---

## Phase 5: Rename CLI Scripts

**Objective:** Rename CLI entry points

**Files:**
- Rename: `agathos/bin/argus-control` → `agathos/bin/agathos-control`
- Rename: `agathos/bin/check-argus` → `agathos/bin/check-agathos`
- Modify: Both files — update ARGUS_* variables to AGATHOS_*

**Changes in agathos-control:**
1. `ARGUS_SCRIPT` → `AGATHOS_SCRIPT`
2. `LOG_DIR` — `argus` → `agathos`
3. `ARGUS_PYTHON` → `AGATHOS_PYTHON`
4. Comments: ARGUS → AGATHOS
5. Output strings: argus → agathos
6. PID file: argus.pid → agathos.pid
7. launchd label: com.hermes.argus → com.hermes.agathos

**Changes in check-agathos:**
1. All argus references → agathos

**Verification:**
```bash
bash -n agathos/bin/agathos-control
bash -n agathos/bin/check-agathos
```

---

## Phase 6: Update Paths, Log Dirs, DB Names in Code

**Objective:** Update all hardcoded paths from argus to agathos

**Files (path updates needed):**
- agathos.py (main daemon) — `_ARGUS_HOME`, `_argus_path()`, `argus.db`, `argus.pid`, `logs/argus/`
- daemon_mgmt.py — all function names and paths
- cli.py — paths and strings
- setup.py — paths and strings
- venv_utils.py — any path references

**Patterns to find/replace:**
1. `_ARGUS_HOME` → `_AGATHOS_HOME`
2. `_argus_path()` → `_agathos_path()`
3. `argus.db` → `agathos.db`
4. `argus.pid` → `agathos.pid`
5. `logs/argus/` → `logs/agathos/`
6. `com.hermes.argus` → `com.hermes.agathos`
7. Function names: `write_argus_pid_file()` → `write_agathos_pid_file()`

---

## Phase 7: Rename Test Directory

**Objective:** Rename `tests/argus/` to `tests/agathos/`

**Commands:**
```bash
cd ~/Projects/hermes-dev
mv tests/argus tests/agathos
```

**Update test files:**
- Update all imports from `from argus` to `from agathos`
- Update all test class names (TestArgus → TestAgathos)
- Update path calculations in conftest.py

---

## Phase 8: Update Config Keys

**Objective:** Change config keys from `argus:` to `agathos:`

**Files:**
- agathos/agathos.py — `_DEFAULT_CONFIG` and `CONFIG` usage
- agathos/setup.py — config schema documentation
- All files using `CONFIG.get("argus_...")` patterns

**Patterns:**
```python
# Before:
argus:
  poll_interval: 30
  entropy_detection_enabled: true

# After:
agathos:
  poll_interval: 30
  entropy_detection_enabled: true
```

In code:
```python
# Before:
CONFIG.get("argus_poll_interval", 30)
config.get("cost_monitoring", {})

# After:
CONFIG.get("agathos_poll_interval", 30)
config.get("cost_monitoring", {})  # (subsection stays same)
```

---

## Phase 9: Update Documentation

**Objective:** Update README, docstrings, and comments

**Files:**
- agathos/README.md — full rewrite
- agathos/PR_CHECKLIST.md — update references
- All module docstrings
- ARGUS-HERMES-INTEGRATION-ANALYSIS.md
- ARGUS-HERMES-PHASE2-ANALYSIS.md
- VENV_SETUP.md

**Patterns:**
- "ARGUS" → "AGATHOS"
- "Argus" → "Agathos"
- "argus" → "agathos" (in paths/commands)
- "Hundred-Eyed Watchman" → "Vigilant Guardian"

---

## Phase 10: Final Verification

**Syntax check:**
```bash
cd ~/Projects/hermes-dev
python3 -m py_compile agathos/*.py
```

**Import test:**
```bash
cd ~/Projects/hermes-dev
source .local/venv/bin/activate
python3 -c "from agathos import Agathos; print('✓ Package import OK')"
python3 -c "from agathos import Agathos, inject_prompt, kill_session; print('✓ Exports OK')"
```

**CLI test:**
```bash
cd ~/Projects/hermes-dev
bash agathos/bin/agathos-control status
```

**Full test suite:**
```bash
cd ~/Projects/hermes-dev
python3 -m pytest tests/agathos/ -o "addopts=" -q
```

---

## Rollback Strategy

If any phase fails:

```bash
# Full rollback
cd ~/Projects/hermes-dev
mv agathos argus 2>/dev/null || true
mv tests/agathos tests/argus 2>/dev/null || true
git checkout -- argus/ tests/argus/ 2>/dev/null || true
```

---

## Metrics to Track

| Phase | Files Changed | Lines Changed | Status |
|-------|--------------|---------------|--------|
| 1: Directory rename | 1 | N/A | ⏳ |
| 2: Module/class rename | 2 | ~50 | ⏳ |
| 3: __init__.py update | 1 | ~50 | ⏳ |
| 4: Internal imports | 20+ | ~100 | ⏳ |
| 5: CLI rename | 2 | ~100 | ⏳ |
| 6: Paths update | 5+ | ~50 | ⏳ |
| 7: Test rename | 15+ | ~50 | ⏳ |
| 8: Config keys | 5+ | ~30 | ⏳ |
| 9: Documentation | 5+ | ~200 | ⏳ |
| **Total** | **~60** | **~700** | |

---

## Verification Checklist

- [ ] All Hermes imports preserved (cron.jobs, hermes_state, hermes_cli.config)
- [ ] Package imports work: `from agathos import Agathos`
- [ ] CLI works: `agathos-control status`
- [ ] All 40 exports in __all__ work
- [ ] No argus references in Python imports
- [ ] Tests pass: pytest tests/agathos/
- [ ] Syntax valid: py_compile on all modules
- [ ] Config key migration documented for users
