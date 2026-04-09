# ARGUS Complexity Reduction Plan

> **Goal:** Reduce argus.py from 1,582 lines to ~900 lines (-43%) while preserving ALL Hermes integrations.
> **Constraint:** Never compromise a Hermes function, hook, adapter, class, or function tie-in.

## Current State Analysis

### File Sizes
| File | Lines | Complexity |
|------|-------|------------|
| argus.py | 1,582 | High - orchestrator with embedded utilities |
| actions.py | 541 | Medium - 14 action functions |
| notifications.py | 559 | Medium - 12 notification senders |
| memory_compat.py | 567 | Medium - 8 memory providers |
| provider_health.py | 569 | Medium - health tracking |
| others | <500 each | Low |
| **Total** | **~8,100** | **18 modules** |

### Complexity Issues in argus.py

1. **Lines 212-287: PID file management** (76 lines) - utility functions embedded in main file
2. **Lines 290-442: Launchd integration** (153 lines) - platform-specific code mixed with core
3. **Lines 556-599: Subprocess utilities** (44 lines) - `_get_cron_env()`, `_safe_subprocess()`
4. **Lines 615-709: Session discovery** (95 lines) - 3 nearly identical discovery methods
5. **Lines 1079-1230: `_run_periodic_checks()`** (152 lines) - repetitive module check pattern
6. **Lines 1337-1400: Action wrappers** (64 lines) - thin wrappers that just call actions.py

### Hermes Integration Points (MUST PRESERVE)

```python
# Lines 40-82: Hermes internals with graceful fallback
try:
    from cron.jobs import list_jobs
    from hermes_state import SessionDB, DEFAULT_DB_PATH
    from hermes_cli.config import load_config as _hermes_load_config
    _HERMES_INTERNALS_AVAILABLE = True
except (ImportError, TypeError) as _e:
    from hermes_fallback import list_jobs, SessionDB, DEFAULT_DB_PATH, _hermes_load_config
```

**These patterns must remain exactly as-is.**

---

## Refactoring Plan

### Phase 1: Extract daemon_mgmt.py (PID + Launchd)

**Extract lines 212-442 from argus.py into new module:**

```python
# argus/daemon_mgmt.py (~230 lines)
"""Daemon management: PID files, launchd integration, lifecycle."""

import os
import sys
import json
import time
import subprocess
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("argus.daemon")

# Import Hermes constants (same pattern as argus.py)
try:
    from hermes_constants import get_hermes_home
    _HERMES_HOME = get_hermes_home()
except ImportError:
    _HERMES_HOME = Path(os.path.expanduser("~/.hermes"))

_ARGUS_HOME = Path(os.path.expanduser("~/hermes"))
_ARGUS_PID_PATH = _ARGUS_HOME / "data" / "watcher" / "argus.pid"
_ARGUS_KIND = "argus-watcher"
_ARGUS_LAUNCHD_LABEL = "com.hermes.argus"

# All PID functions from lines 217-287
def get_argus_pid_path() -> Path: ...
def build_argus_pid_record() -> dict: ...
def write_argus_pid_file() -> None: ...
def remove_argus_pid_file() -> None: ...
def read_argus_pid_record() -> Optional[dict]: ...
def get_argus_running_pid() -> Optional[int]: ...
def is_argus_running() -> bool: ...

# All launchd functions from lines 295-442
def get_argus_launchd_label() -> str: ...
def get_argus_launchd_plist_path() -> Path: ...
def generate_argus_launchd_plist() -> str: ...
def argus_launchd_install() -> bool: ...
def argus_launchd_uninstall() -> bool: ...
def argus_launchd_status() -> dict: ...
```

**Update argus.py imports:**
```python
# Replace lines 212-442 with:
from .daemon_mgmt import (
    write_argus_pid_file,
    remove_argus_pid_file,
    get_argus_running_pid,
    is_argus_running,
)
```

**Impact:** -230 lines from argus.py

---

### Phase 2: Extract subprocess_utils.py

**Extract lines 556-599 from argus.py:**

```python
# argus/subprocess_utils.py (~50 lines)
"""Subprocess utilities with Hermes environment awareness."""

import os
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("argus.subprocess")

# Import Hermes constants (same pattern)
try:
    from hermes_constants import get_hermes_home
    _HERMES_HOME = get_hermes_home()
except ImportError:
    _HERMES_HOME = Path(os.path.expanduser("~/.hermes"))

_ARGUS_HOME = Path(os.path.expanduser("~/hermes"))

def build_argus_subprocess_env() -> Dict[str, str]:
    """Build a full environment dict for subprocess calls."""
    env = os.environ.copy()
    paths = [
        "/opt/homebrew/bin",
        "/usr/local/bin",
        str(_ARGUS_HOME / "bin"),
        str(Path.home() / ".local" / "bin"),
        str(_HERMES_HOME / "credentials"),
        "/usr/bin",
        "/bin",
    ]
    env["PATH"] = ":".join(paths)
    env["HOME"] = os.path.expanduser("~")
    return env

def safe_subprocess(
    cmd: List[str], timeout: int = 10, **kwargs
) -> Optional[subprocess.CompletedProcess]:
    """Run a subprocess with full env and error handling. Never raises."""
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=build_argus_subprocess_env(),
            **kwargs,
        )
    except FileNotFoundError:
        logger.warning("Command not found: %s (check PATH)", cmd[0])
        return None
    except subprocess.TimeoutExpired:
        logger.warning("Command timed out after %ss: %s", timeout, " ".join(cmd))
        return None
    except Exception as e:
        logger.error("Subprocess error for %s: %s", cmd[0], e, exc_info=True)
        return None
```

**Update argus.py:**
```python
# Replace _get_cron_env() and _safe_subprocess() with:
from .subprocess_utils import safe_subprocess
```

**Update actions.py** (which also needs subprocess):
```python
# In actions.py, replace direct subprocess calls with:
from .subprocess_utils import safe_subprocess
```

**Impact:** -44 lines from argus.py

---

### Phase 3: Consolidate Session Discovery

**Current:** 3 nearly identical methods (lines 615-709 = 95 lines)

**Refactor to single parameterized method:**

```python
# In argus.py, replace _discover_cron_sessions(), _discover_delegate_sessions(), 
# _discover_manual_sessions() with:

def _discover_sessions_by_source(self, source_type: str) -> List[Dict]:
    """Discover sessions from a specific source (cron, delegate, manual)."""
    sessions = []
    
    try:
        if source_type == "cron":
            jobs = list_jobs(include_disabled=False)
            for job in jobs:
                sessions.append({
                    "session_id": f"cron_{job['id']}",
                    "session_type": "cron",
                    "job_id": job["id"],
                    "task_description": job.get("name", "Unknown"),
                    "model": job.get("model"),
                    "provider": job.get("provider"),
                    "metadata": json.dumps(job),
                })
                
        elif source_type in ("delegate", "manual"):
            db = SessionDB(DEFAULT_DB_PATH)
            try:
                all_sessions = db.list_sessions_rich(limit=50)
            finally:
                db.close()
            
            for s in all_sessions:
                if source_type == "delegate":
                    if s.get("source") in ("delegate", "delegate_task"):
                        sessions.append({
                            "session_id": f"delegate_{s['id']}",
                            "session_type": "delegate_task",
                            "task_description": s.get("title", f"Delegate {s['id'][:12]}"),
                            "metadata": json.dumps({
                                "session_id": s["id"],
                                "source": s.get("source"),
                                "started_at": s.get("started_at"),
                            }),
                        })
                else:  # manual
                    source = s.get("source", "")
                    if source in ("cli", "telegram", "manual", "gateway"):
                        sessions.append({
                            "session_id": f"manual_{s['id']}",
                            "session_type": "manual",
                            "task_description": s.get("title", f"Session {s['id'][:12]}"),
                            "metadata": json.dumps({
                                "session_id": s["id"],
                                "source": source,
                                "started_at": s.get("started_at"),
                            }),
                        })
                        
    except Exception as e:
        logger.error("Error discovering %s sessions: %s", source_type, e, exc_info=True)
    
    return sessions

def discover_sessions(self) -> List[Dict]:
    """Discover all active agent sessions."""
    return (
        self._discover_sessions_by_source("cron") +
        self._discover_sessions_by_source("delegate") +
        self._discover_sessions_by_source("manual")
    )
```

**Impact:** -60 lines from argus.py (95 → 35)

---

### Phase 4: Simplify _run_periodic_checks() with Module Runner Pattern

**Current:** Lines 1079-1230 (152 lines) with repetitive try/except blocks

**Refactor to declarative module runner:**

```python
# In argus.py, replace _run_periodic_checks() with:

def _run_periodic_checks(self):
    """Run resource, drift, and cleanup checks every N cycles."""
    cycle = self._cycle_count
    mod = cycle % 10
    
    # Define periodic checks: (cycle_offset, config_key, module, check_func, audit_func, notification_type)
    PERIODIC_CHECKS = [
        (0, "resource_checks_enabled", _resources, "run_resource_check", "record_resource_alert", "resource_alert"),
        (None, "drift_detection_enabled", _drift, None, "record_drift_event", None),  # Every cycle
        (3, "provider_health_enabled", _provider_health, "run_provider_check", "record_provider_alert", "provider_health"),
        (5, "cleanup_enabled", _cleanup, "run_cleanup", "record_cleanup_event", None),
        (7, "cost_monitoring_enabled", _cost_monitor, "check_costs", "record_cost_alert", "cost_alert"),
    ]
    
    for offset, config_key, module, check_func, audit_func, notify_type in PERIODIC_CHECKS:
        if offset is not None and mod != offset:
            continue
        if not CONFIG.get(config_key, True):
            continue
            
        try:
            # Run check
            if check_func:
                report = getattr(module, check_func)(self.cursor, self.conn) if check_func != "check_costs" else getattr(module, check_func)(CONFIG)
            else:
                # Drift detection is special - no cursor/conn args
                changes = self._drift_detector.check()
                if changes:
                    self._drift_detector.record_changes(self.cursor, self.conn, changes)
                    if CONFIG.get("audit_trail_enabled", True):
                        for c in changes:
                            _audit.record_drift_event(...)
                continue
            
            # Check if alert needed
            if report.get("overall_severity") in ("warning", "critical") or report.get("has_alert"):
                alert = module.format_alert(report) if hasattr(module, 'format_alert') else str(report)
                if alert:
                    logger.warning("%s alert:\n%s", config_key.replace('_enabled', '').replace('_', ' '), alert)
                    
                    if CONFIG.get("audit_trail_enabled", True) and audit_func:
                        getattr(_audit, audit_func)(self.cursor, self.conn, **self._build_audit_args(report, audit_func))
                    
                    if notify_type and CONFIG.get("notifications_enabled", True):
                        _notifications.send_notification(self.cursor, self.conn, "system", notify_type, alert)
                        
        except Exception as e:
            logger.error("%s check failed: %s", config_key.replace('_enabled', ''), e)
    
    # Circuit breaker (special handling)
    if mod == 8:
        cb_config = CONFIG.get("circuit_breaker", {})
        if cb_config.get("enabled", False):
            try:
                events = _circuit_breaker.check_circuits(self.cursor, self.conn, CONFIG)
                for event in events:
                    if event.get("notify"):
                        msg = _circuit_breaker.format_circuit_event(event)
                        logger.warning("Circuit breaker: %s", msg)
                        if CONFIG.get("audit_trail_enabled", True):
                            _audit.record_circuit_event(...)
                        if CONFIG.get("notifications_enabled", True):
                            _notifications.send_notification(...)
            except Exception as e:
                logger.error("Circuit breaker check failed: %s", e)

def _build_audit_args(self, report: dict, audit_func: str) -> dict:
    """Build appropriate arguments for audit functions based on type."""
    if "resource" in audit_func:
        return {"resource_type": "system", "severity": report["overall_severity"], "details": report}
    elif "provider" in audit_func:
        return {"providers": list(report.get("providers", {}).keys()), "severity": report["overall_severity"], "details": report}
    elif "cleanup" in audit_func:
        return {"findings": report}
    elif "cost" in audit_func:
        return {"details": report}
    return {"details": report}
```

**Impact:** -100 lines from argus.py (152 → 52)

---

### Phase 5: Remove Redundant Action Wrappers

**Current:** Lines 1337-1400 (64 lines) of thin wrappers

**Remove these methods entirely - call actions.py directly:**

```python
# REMOVE from Argus class:
# - _restart_cron_session() → call _actions.restart_cron_session() directly
# - _restart_delegate_session() → call _actions.restart_delegate_session() directly  
# - _restart_manual_session() → call _actions.restart_manual_session() directly
# - _build_corrective_prompt() → call _actions.build_corrective_prompt() directly
# - _kill_cron_session() → call _actions.kill_cron_session() directly
# - _kill_delegate_session() → call _actions.kill_delegate_session() directly
# - _kill_manual_session() → call _actions.kill_manual_session() directly
# - _terminate_pid() → call _actions.terminate_pid() directly
# - _inject_cron_prompt() → call _actions.inject_cron_prompt() directly
# - _inject_delegate_prompt() → call _actions.inject_delegate_prompt() directly
# - _inject_manual_prompt() → call _actions.inject_manual_prompt() directly

# KEEP only these (they use self.cursor/conn):
# - _restart_session() - uses self.cursor, self.conn, CORRECTIVE_PROMPTS
# - _kill_session() - uses self.cursor, self.conn
# - _inject_prompt() - uses self.cursor, self.conn
# - _send_notification() - uses self.cursor, self.conn
```

**Update execute_action() to call actions.py directly:**

```python
def execute_action(self, session_id: str, decision: Dict):
    """Execute the decided action."""
    action = decision["action"]
    reason = decision["reason"]
    
    logger.info("Executing %s on %s: %s", action, session_id, reason)
    
    # Record action in database
    self.cursor.execute("...")
    action_id = self.cursor.lastrowid
    
    try:
        if action == "restart":
            # Call directly to actions.py, not through wrapper
            _actions.restart_session(self.cursor, self.conn, session_id, reason, CORRECTIVE_PROMPTS)
            if CONFIG.get("notifications_enabled", True):
                _notifications.send_notification(self.cursor, self.conn, session_id, "restart", f"Restarted: {reason}")
        
        elif action == "kill":
            _actions.kill_session(self.cursor, self.conn, session_id, reason)
            if CONFIG.get("notifications_enabled", True):
                _notifications.send_notification(self.cursor, self.conn, session_id, "kill", f"Killed: {reason}")
        
        elif action == "inject_prompt":
            _actions.inject_prompt(self.cursor, self.conn, session_id, decision.get("prompt", ""))
        
        # ... rest same
```

**Impact:** -55 lines from argus.py (64 → 9)

---

## Line Count Summary

| Change | Lines Removed | Lines Added | Net |
|--------|--------------|-------------|-----|
| Extract daemon_mgmt.py | 230 | 0 (new file) | -230 |
| Extract subprocess_utils.py | 44 | 0 (new file) | -44 |
| Consolidate session discovery | 60 | 35 | -25 |
| Simplify _run_periodic_checks | 100 | 50 | -50 |
| Remove action wrappers | 55 | 0 | -55 |
| **Total** | **489** | **85** | **-404** |

**argus.py: 1,582 → ~1,178 lines (-25%)**

---

## Hermes Integration Verification

All Hermes integration points are **preserved**:

1. **Lines 40-82: Hermes internals import** - No change
2. **Line 201: _hermes_load_config()** - No change
3. **Line 619: list_jobs()** - No change (now called from _discover_sessions_by_source)
4. **Line 645: SessionDB(DEFAULT_DB_PATH)** - No change (now called from _discover_sessions_by_source)
5. **All CONFIG.get() checks** - No change
6. **All module imports** - No change

---

## Testing Strategy

Before/after each phase:
```bash
# Syntax check
python3 -m py_compile argus/*.py

# Import check
python3 -c "from argus import Argus; print('OK')"

# Full test suite
cd ~/Projects/hermes-dev && python3 -m pytest tests/argus/ -v --tb=short

# Integration check
python3 -c "
from argus import Argus
from argus.daemon_mgmt import is_argus_running, get_argus_running_pid
from argus.subprocess_utils import safe_subprocess
print('All imports OK')
"
```

---

## Migration Order

1. **Phase 1:** Create daemon_mgmt.py + update imports (safest, no logic change)
2. **Phase 2:** Create subprocess_utils.py + migrate actions.py (test actions.py still works)
3. **Phase 3:** Consolidate session discovery (test session detection)
4. **Phase 4:** Simplify _run_periodic_checks (test all periodic modules)
5. **Phase 5:** Remove action wrappers (test restart/kill/inject)

---

## Rollback Plan

If any phase fails:
```bash
# Restore from git
git checkout -- argus/argus.py
rm argus/daemon_mgmt.py argus/subprocess_utils.py  # if created

# Or use backup
cp argus/argus.py.backup argus/argus.py
```

---

*Plan created: 2025-04-09*
*Estimated reduction: 1,582 → 1,178 lines (-25%)*
*Hermes integrations: 100% preserved*
