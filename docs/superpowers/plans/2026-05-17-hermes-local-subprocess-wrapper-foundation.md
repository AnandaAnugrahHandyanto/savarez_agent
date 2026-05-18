# Hermes Local Subprocess Wrapper Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local, test-backed subprocess wrapper foundation for future Claude Code and Codex CLI routing without activating any live routing, Telegram, gateway, cron, daemon, MCP, provider, deploy, merge, R-audit, or production surface.

**Architecture:** Add a small `agent/cmh_subprocess/` package with focused modules for flag verification, profile-aware envelope tracking, halt flags, structured preflight results, wrapper preflight assembly, and read-only budget formatting. Tests drive each behavior first and use temporary `HERMES_HOME` values so no real user state is touched.

**Tech Stack:** Python standard library, pytest, Hermes `get_hermes_home()`, existing CLI command registry only if the optional local `/budget` command is included.

---

## File Structure

Create these files:

- `agent/cmh_subprocess/__init__.py`
  - Package exports only stable helpers and types.
- `agent/cmh_subprocess/result.py`
  - Shared result dataclasses and status constants.
- `agent/cmh_subprocess/flags.py`
  - CLI help text parsing and required/optional flag validation.
- `agent/cmh_subprocess/envelope.py`
  - Profile-aware envelope state defaults, read/write, rolling window reset, and budget gating.
- `agent/cmh_subprocess/halt_flags.py`
  - Profile-aware halt flag state, malformed-state fail-closed behavior, and class mapping.
- `agent/cmh_subprocess/wrappers.py`
  - Disabled-by-default wrapper preflight helpers for Claude and Codex print paths.
- `agent/cmh_subprocess/budget_display.py`
  - Pure formatter for budget and halt-state display. This supports tests and a later local CLI command without requiring CLI integration now.
- `tests/agent/test_cmh_subprocess_flags.py`
  - Flag parser and verifier tests.
- `tests/agent/test_cmh_subprocess_envelope.py`
  - Envelope default, increment, reset, and cap tests.
- `tests/agent/test_cmh_subprocess_halt_flags.py`
  - Halt state tests.
- `tests/agent/test_cmh_subprocess_wrappers.py`
  - Wrapper preflight tests.
- `tests/agent/test_cmh_subprocess_budget_display.py`
  - Pure display formatting tests.

Do not modify these in this A-slice unless Christopher explicitly extends scope:

- `gateway/`
- `cron/`
- `tools/send_message_tool.py`
- `~/.hermes/wrappers/`
- `~/.hermes/bin/`
- profile config files
- launchd plist files
- vault dispatch folders

## Task 1: Flag verification foundation

**Files:**
- Create: `agent/cmh_subprocess/__init__.py`
- Create: `agent/cmh_subprocess/flags.py`
- Create: `tests/agent/test_cmh_subprocess_flags.py`

- [ ] **Step 1: Write failing tests for flag extraction and Claude required flags**

Create `tests/agent/test_cmh_subprocess_flags.py` with this content:

```python
from agent.cmh_subprocess.flags import (
    CLAUDE_REQUIRED_FLAGS,
    validate_flags,
    extract_long_flags,
)

CLAUDE_HELP = """
Usage: claude [options] [prompt]
  -p, --print                                       Print response and exit
  --max-budget-usd <amount>                         Maximum dollar amount to spend on API calls
  --output-format <format>                          Output format
  --no-session-persistence                          Disable session persistence
  --plugin-dir <path>                               Load a plugin
  --model <model>                                   Model for the current session
  --permission-mode <mode>                          Permission mode
  --tools <tools...>                                Specify the list of available tools
  --bare                                            Minimal mode
"""


def test_extract_long_flags_finds_claude_print_flags():
    flags = extract_long_flags(CLAUDE_HELP)

    assert "--print" in flags
    assert "--max-budget-usd" in flags
    assert "--output-format" in flags
    assert "--no-session-persistence" in flags


def test_validate_flags_accepts_current_claude_required_flags():
    result = validate_flags("claude", CLAUDE_HELP, required_flags=CLAUDE_REQUIRED_FLAGS)

    assert result.ok is True
    assert result.missing_required_flags == []
    assert result.available_flags["--max-budget-usd"] is True


def test_validate_flags_rejects_draft_max_cost_flag_when_help_lacks_it():
    result = validate_flags("claude", CLAUDE_HELP, required_flags=("--max-cost-usd",))

    assert result.ok is False
    assert result.missing_required_flags == ["--max-cost-usd"]
    assert result.available_flags["--max-cost-usd"] is False
```

- [ ] **Step 2: Run the flag tests and verify RED**

Run:

```bash
python -m pytest tests/agent/test_cmh_subprocess_flags.py -q -o 'addopts='
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent.cmh_subprocess'`.

- [ ] **Step 3: Add the minimal package and flag verifier implementation**

Create `agent/cmh_subprocess/__init__.py`:

```python
"""CMH subprocess wrapper foundation.

Local foundation only. This package does not activate live routing,
Telegram sends, gateway behavior, cron, daemon, MCP, deploy, merge, or
production mutation.
"""
```

Create `agent/cmh_subprocess/flags.py`:

```python
"""CLI flag verification for CMH subprocess wrapper foundations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

CLAUDE_REQUIRED_FLAGS: tuple[str, ...] = (
    "--print",
    "--max-budget-usd",
    "--output-format",
    "--no-session-persistence",
)

CLAUDE_OPTIONAL_FLAGS: tuple[str, ...] = (
    "--plugin-dir",
    "--model",
    "--permission-mode",
    "--tools",
    "--bare",
)

CODEX_REQUIRED_FLAGS_UNRESOLVED: tuple[str, ...] = ()

_LONG_FLAG_RE = re.compile(r"(?<![\w-])--[a-zA-Z0-9][a-zA-Z0-9-]*")


@dataclass(frozen=True)
class FlagValidationResult:
    cli_name: str
    ok: bool
    required_flags: tuple[str, ...]
    optional_flags: tuple[str, ...]
    available_flags: dict[str, bool]
    missing_required_flags: list[str]


def extract_long_flags(help_text: str) -> set[str]:
    """Return long CLI flags found in help output or verified docs."""
    return set(_LONG_FLAG_RE.findall(help_text or ""))


def validate_flags(
    cli_name: str,
    help_text: str,
    required_flags: Iterable[str],
    optional_flags: Iterable[str] = (),
) -> FlagValidationResult:
    """Validate required and optional flags against a text evidence source."""
    required = tuple(required_flags)
    optional = tuple(optional_flags)
    found = extract_long_flags(help_text)
    requested = required + optional
    available = {flag: flag in found for flag in requested}
    missing = [flag for flag in required if flag not in found]
    return FlagValidationResult(
        cli_name=cli_name,
        ok=not missing,
        required_flags=required,
        optional_flags=optional,
        available_flags=available,
        missing_required_flags=missing,
    )
```

- [ ] **Step 4: Run the flag tests and verify GREEN**

Run:

```bash
python -m pytest tests/agent/test_cmh_subprocess_flags.py -q -o 'addopts='
```

Expected: PASS, 3 tests.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add agent/cmh_subprocess/__init__.py agent/cmh_subprocess/flags.py tests/agent/test_cmh_subprocess_flags.py
git commit -m "feat: add CMH subprocess flag verification"
```

## Task 2: Envelope tracking foundation

**Files:**
- Create: `agent/cmh_subprocess/result.py`
- Create: `agent/cmh_subprocess/envelope.py`
- Create: `tests/agent/test_cmh_subprocess_envelope.py`

- [ ] **Step 1: Write failing tests for envelope defaults, increments, reset, and cap**

Create `tests/agent/test_cmh_subprocess_envelope.py`:

```python
from datetime import datetime, timedelta, timezone

from agent.cmh_subprocess.envelope import (
    ENVELOPE_STATE_FILENAME,
    EnvelopeDecision,
    allocation_cap,
    check_budget,
    default_envelope_state,
    envelope_state_path,
    increment_usage,
    load_envelope_state,
    save_envelope_state,
)


def test_default_envelope_caps_are_85_percent():
    state = default_envelope_state()

    assert allocation_cap(state["anthropic_max"]) == 191
    assert allocation_cap(state["chatgpt_pro"]) == 170


def test_envelope_state_path_uses_hermes_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    assert envelope_state_path() == tmp_path / "state" / ENVELOPE_STATE_FILENAME


def test_load_missing_state_returns_defaults_without_writing(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    state = load_envelope_state()

    assert state["anthropic_max"]["envelope_messages_used_5h"] == 0
    assert not envelope_state_path().exists()


def test_increment_usage_starts_window_and_persists(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    now = datetime(2026, 5, 17, 20, 0, tzinfo=timezone.utc)
    state = default_envelope_state()

    updated = increment_usage(state, "anthropic_max", now=now)
    save_envelope_state(updated)
    reloaded = load_envelope_state()

    assert reloaded["anthropic_max"]["envelope_messages_used_5h"] == 1
    assert reloaded["anthropic_max"]["window_start_iso"] == now.isoformat()
    assert reloaded["anthropic_max"]["last_invocation_iso"] == now.isoformat()


def test_increment_usage_resets_after_five_hours():
    start = datetime(2026, 5, 17, 20, 0, tzinfo=timezone.utc)
    later = start + timedelta(hours=5, minutes=1)
    state = default_envelope_state()
    state["anthropic_max"]["window_start_iso"] = start.isoformat()
    state["anthropic_max"]["envelope_messages_used_5h"] = 190

    updated = increment_usage(state, "anthropic_max", now=later)

    assert updated["anthropic_max"]["envelope_messages_used_5h"] == 1
    assert updated["anthropic_max"]["window_start_iso"] == later.isoformat()


def test_budget_blocks_non_priority_at_cap():
    state = default_envelope_state()
    state["anthropic_max"]["envelope_messages_used_5h"] = 191

    decision = check_budget(state, "anthropic_max", priority=False)

    assert decision == EnvelopeDecision(
        allowed=False,
        reason="budget_blocked",
        used=191,
        cap=191,
        available=0,
    )


def test_budget_allows_priority_at_cap_with_reason():
    state = default_envelope_state()
    state["anthropic_max"]["envelope_messages_used_5h"] = 191

    decision = check_budget(state, "anthropic_max", priority=True)

    assert decision.allowed is True
    assert decision.reason == "priority_override"
    assert decision.available == 0
```

- [ ] **Step 2: Run envelope tests and verify RED**

Run:

```bash
python -m pytest tests/agent/test_cmh_subprocess_envelope.py -q -o 'addopts='
```

Expected: FAIL with missing `agent.cmh_subprocess.envelope`.

- [ ] **Step 3: Add structured result and envelope implementation**

Create `agent/cmh_subprocess/result.py`:

```python
"""Shared result types for CMH subprocess wrapper foundations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PreflightResult:
    status: str
    ok: bool
    message: str
    argv: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)
```

Create `agent/cmh_subprocess/envelope.py`:

```python
"""Profile-aware envelope tracking for local subprocess wrapper foundations."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home

ENVELOPE_STATE_FILENAME = "envelope_tracking.json"
WINDOW_DURATION = timedelta(hours=5)

_DEFAULT_STATE: dict[str, dict[str, Any]] = {
    "anthropic_max": {
        "envelope_total_messages_per_5h": 225,
        "envelope_allocation_hermes_pct": 85,
        "envelope_messages_used_5h": 0,
        "window_start_iso": None,
        "last_invocation_iso": None,
        "halt_flag_active": False,
    },
    "chatgpt_pro": {
        "envelope_total_messages_per_5h": 200,
        "envelope_allocation_hermes_pct": 85,
        "envelope_messages_used_5h": 0,
        "window_start_iso": None,
        "last_invocation_iso": None,
        "halt_flag_active": False,
    },
}


@dataclass(frozen=True)
class EnvelopeDecision:
    allowed: bool
    reason: str
    used: int
    cap: int
    available: int


def envelope_state_path() -> Path:
    return get_hermes_home() / "state" / ENVELOPE_STATE_FILENAME


def default_envelope_state() -> dict[str, dict[str, Any]]:
    return copy.deepcopy(_DEFAULT_STATE)


def allocation_cap(record: dict[str, Any]) -> int:
    total = int(record.get("envelope_total_messages_per_5h", 0))
    pct = int(record.get("envelope_allocation_hermes_pct", 0))
    return (total * pct) // 100


def load_envelope_state(path: Path | None = None) -> dict[str, dict[str, Any]]:
    state_path = path or envelope_state_path()
    if not state_path.exists():
        return default_envelope_state()
    with state_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    state = default_envelope_state()
    for key, defaults in state.items():
        if isinstance(data.get(key), dict):
            defaults.update(data[key])
    return state


def save_envelope_state(state: dict[str, dict[str, Any]], path: Path | None = None) -> None:
    state_path = path or envelope_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def increment_usage(
    state: dict[str, dict[str, Any]],
    envelope_name: str,
    *,
    now: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    current = now or datetime.now(timezone.utc)
    updated = copy.deepcopy(state)
    record = updated[envelope_name]
    window_start = _parse_iso(record.get("window_start_iso"))
    if window_start is None or current - window_start >= WINDOW_DURATION:
        record["window_start_iso"] = current.isoformat()
        record["envelope_messages_used_5h"] = 0
    record["envelope_messages_used_5h"] = int(record.get("envelope_messages_used_5h", 0)) + 1
    record["last_invocation_iso"] = current.isoformat()
    return updated


def check_budget(
    state: dict[str, dict[str, Any]],
    envelope_name: str,
    *,
    priority: bool = False,
) -> EnvelopeDecision:
    record = state[envelope_name]
    used = int(record.get("envelope_messages_used_5h", 0))
    cap = allocation_cap(record)
    available = max(cap - used, 0)
    if used >= cap and not priority:
        return EnvelopeDecision(False, "budget_blocked", used, cap, available)
    if used >= cap and priority:
        return EnvelopeDecision(True, "priority_override", used, cap, available)
    return EnvelopeDecision(True, "within_budget", used, cap, available)
```

- [ ] **Step 4: Run envelope tests and verify GREEN**

Run:

```bash
python -m pytest tests/agent/test_cmh_subprocess_envelope.py -q -o 'addopts='
```

Expected: PASS, 7 tests.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add agent/cmh_subprocess/result.py agent/cmh_subprocess/envelope.py tests/agent/test_cmh_subprocess_envelope.py
git commit -m "feat: add CMH subprocess envelope tracking"
```

## Task 3: Halt flag foundation

**Files:**
- Create: `agent/cmh_subprocess/halt_flags.py`
- Create: `tests/agent/test_cmh_subprocess_halt_flags.py`

- [ ] **Step 1: Write failing tests for halt flags**

Create `tests/agent/test_cmh_subprocess_halt_flags.py`:

```python
import json

from agent.cmh_subprocess.halt_flags import (
    HALT_FLAGS_FILENAME,
    default_halt_flags,
    halt_flags_path,
    is_halted,
    load_halt_flags,
    save_halt_flags,
)


def test_missing_halt_file_means_not_halted(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    assert load_halt_flags().flags == default_halt_flags()
    assert is_halted("cowork_headless").halted is False


def test_halt_path_uses_hermes_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    assert halt_flags_path() == tmp_path / "state" / HALT_FLAGS_FILENAME


def test_all_halt_blocks_every_class(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    save_halt_flags({"all": True, "cowork_headless": False, "codex_auto_dispatch": False, "hermes_telegram_acks": False})

    decision = is_halted("codex_auto_dispatch")

    assert decision.halted is True
    assert decision.active_flag == "all"


def test_class_halt_blocks_matching_class_only(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    save_halt_flags({"all": False, "cowork_headless": True, "codex_auto_dispatch": False, "hermes_telegram_acks": False})

    cowork = is_halted("cowork_headless")
    codex = is_halted("codex_auto_dispatch")

    assert cowork.halted is True
    assert cowork.active_flag == "cowork_headless"
    assert codex.halted is False


def test_malformed_halt_file_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    path = halt_flags_path()
    path.parent.mkdir(parents=True)
    path.write_text("{not-json", encoding="utf-8")

    state = load_halt_flags()
    decision = is_halted("cowork_headless")

    assert state.malformed is True
    assert decision.halted is True
    assert decision.active_flag == "state_error"
    assert str(path) in decision.message
```

- [ ] **Step 2: Run halt flag tests and verify RED**

Run:

```bash
python -m pytest tests/agent/test_cmh_subprocess_halt_flags.py -q -o 'addopts='
```

Expected: FAIL with missing `agent.cmh_subprocess.halt_flags`.

- [ ] **Step 3: Implement halt flag module**

Create `agent/cmh_subprocess/halt_flags.py`:

```python
"""Profile-aware halt flags for CMH subprocess wrapper foundations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from hermes_constants import get_hermes_home

HALT_FLAGS_FILENAME = "cmh_halt_flags.json"


@dataclass(frozen=True)
class HaltState:
    flags: dict[str, bool]
    malformed: bool = False
    error: str = ""
    path: Path | None = None


@dataclass(frozen=True)
class HaltDecision:
    halted: bool
    active_flag: str | None
    message: str


def default_halt_flags() -> dict[str, bool]:
    return {
        "cowork_headless": False,
        "codex_auto_dispatch": False,
        "hermes_telegram_acks": False,
        "all": False,
    }


def halt_flags_path() -> Path:
    return get_hermes_home() / "state" / HALT_FLAGS_FILENAME


def load_halt_flags(path: Path | None = None) -> HaltState:
    state_path = path or halt_flags_path()
    if not state_path.exists():
        return HaltState(default_halt_flags(), path=state_path)
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return HaltState(default_halt_flags(), malformed=True, error=str(exc), path=state_path)
    flags = default_halt_flags()
    if isinstance(data, dict):
        for key in flags:
            flags[key] = bool(data.get(key, flags[key]))
    return HaltState(flags, path=state_path)


def save_halt_flags(flags: dict[str, bool], path: Path | None = None) -> None:
    state_path = path or halt_flags_path()
    merged = default_halt_flags()
    merged.update({key: bool(value) for key, value in flags.items() if key in merged})
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def is_halted(class_name: str, path: Path | None = None) -> HaltDecision:
    state = load_halt_flags(path=path)
    if state.malformed:
        return HaltDecision(True, "state_error", f"Malformed halt flag state at {state.path}: {state.error}")
    if state.flags.get("all"):
        return HaltDecision(True, "all", "Global halt flag is active")
    if state.flags.get(class_name):
        return HaltDecision(True, class_name, f"Halt flag is active for {class_name}")
    return HaltDecision(False, None, "No halt flag active")
```

- [ ] **Step 4: Run halt flag tests and verify GREEN**

Run:

```bash
python -m pytest tests/agent/test_cmh_subprocess_halt_flags.py -q -o 'addopts='
```

Expected: PASS, 5 tests.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add agent/cmh_subprocess/halt_flags.py tests/agent/test_cmh_subprocess_halt_flags.py
git commit -m "feat: add CMH subprocess halt flags"
```

## Task 4: Wrapper preflight foundation

**Files:**
- Create: `agent/cmh_subprocess/wrappers.py`
- Create: `tests/agent/test_cmh_subprocess_wrappers.py`

- [ ] **Step 1: Write failing tests for wrapper preflight ordering and outcomes**

Create `tests/agent/test_cmh_subprocess_wrappers.py`:

```python
from pathlib import Path

from agent.cmh_subprocess.envelope import default_envelope_state, save_envelope_state
from agent.cmh_subprocess.halt_flags import save_halt_flags
from agent.cmh_subprocess.wrappers import (
    CLAUDE_HELP_EVIDENCE,
    prepare_claude_print_invocation,
    prepare_codex_print_invocation,
)


def test_halt_prevents_binary_lookup(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    save_halt_flags({"all": True})

    result = prepare_claude_print_invocation("Summarize status", binary_resolver=lambda _: "/missing/should/not/be/used")

    assert result.status == "halted"
    assert result.ok is False
    assert result.details["active_flag"] == "all"


def test_codex_missing_binary_is_clean_result(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    result = prepare_codex_print_invocation("Explain this code", binary_resolver=lambda _: None)

    assert result.status == "missing_binary"
    assert result.ok is False
    assert "codex" in result.message


def test_claude_missing_verified_flags_blocks(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    result = prepare_claude_print_invocation(
        "Summarize status",
        binary_resolver=lambda _: "/bin/claude",
        help_text="Usage: claude --print",
    )

    assert result.status == "missing_required_flag"
    assert result.ok is False
    assert result.details["missing_required_flags"] == ["--max-budget-usd", "--output-format", "--no-session-persistence"]


def test_claude_budget_cap_blocks_non_priority(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    state = default_envelope_state()
    state["anthropic_max"]["envelope_messages_used_5h"] = 191
    save_envelope_state(state)

    result = prepare_claude_print_invocation(
        "Summarize status",
        binary_resolver=lambda _: "/bin/claude",
        help_text=CLAUDE_HELP_EVIDENCE,
    )

    assert result.status == "budget_blocked"
    assert result.ok is False
    assert result.details["used"] == 191
    assert result.details["cap"] == 191


def test_claude_preflight_assembles_safe_argv(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    result = prepare_claude_print_invocation(
        "Summarize status",
        binary_resolver=lambda _: "/bin/claude",
        help_text=CLAUDE_HELP_EVIDENCE,
        max_budget_usd="0.01",
    )

    assert result.ok is True
    assert result.status == "ready"
    assert result.argv == (
        "/bin/claude",
        "--print",
        "--max-budget-usd",
        "0.01",
        "--output-format",
        "text",
        "--no-session-persistence",
        "Summarize status",
    )


def test_claude_preflight_does_not_create_state_files_unless_checks_need_existing_state(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    result = prepare_claude_print_invocation(
        "Summarize status",
        binary_resolver=lambda _: "/bin/claude",
        help_text=CLAUDE_HELP_EVIDENCE,
    )

    assert result.ok is True
    assert not (tmp_path / "state" / "envelope_tracking.json").exists()
    assert not (tmp_path / "state" / "cmh_halt_flags.json").exists()
```

- [ ] **Step 2: Run wrapper tests and verify RED**

Run:

```bash
python -m pytest tests/agent/test_cmh_subprocess_wrappers.py -q -o 'addopts='
```

Expected: FAIL with missing `agent.cmh_subprocess.wrappers`.

- [ ] **Step 3: Implement wrapper preflight helpers**

Create `agent/cmh_subprocess/wrappers.py`:

```python
"""Disabled-by-default wrapper preflight helpers for CMH subprocess routing."""

from __future__ import annotations

import shutil
from collections.abc import Callable

from agent.cmh_subprocess.envelope import check_budget, load_envelope_state
from agent.cmh_subprocess.flags import CLAUDE_REQUIRED_FLAGS, validate_flags
from agent.cmh_subprocess.halt_flags import is_halted
from agent.cmh_subprocess.result import PreflightResult

CLAUDE_HELP_EVIDENCE = """
Usage: claude [options] [prompt]
  -p, --print                                       Print response and exit
  --max-budget-usd <amount>                         Maximum dollar amount to spend on API calls
  --output-format <format>                          Output format
  --no-session-persistence                          Disable session persistence
"""

BinaryResolver = Callable[[str], str | None]


def _default_binary_resolver(name: str) -> str | None:
    return shutil.which(name)


def prepare_claude_print_invocation(
    prompt: str,
    *,
    binary_resolver: BinaryResolver | None = None,
    help_text: str | None = None,
    priority: bool = False,
    max_budget_usd: str = "0.01",
) -> PreflightResult:
    """Prepare a Claude print invocation without running it."""
    halt = is_halted("cowork_headless")
    if halt.halted:
        return PreflightResult(
            status="halted",
            ok=False,
            message=halt.message,
            details={"active_flag": halt.active_flag},
        )

    resolver = binary_resolver or _default_binary_resolver
    binary = resolver("claude")
    if not binary:
        return PreflightResult("missing_binary", False, "Required binary 'claude' was not found on PATH")

    evidence = help_text or CLAUDE_HELP_EVIDENCE
    flags = validate_flags("claude", evidence, required_flags=CLAUDE_REQUIRED_FLAGS)
    if not flags.ok:
        return PreflightResult(
            status="missing_required_flag",
            ok=False,
            message="Claude flag evidence is missing required flags",
            details={"missing_required_flags": flags.missing_required_flags},
        )

    budget = check_budget(load_envelope_state(), "anthropic_max", priority=priority)
    if not budget.allowed:
        return PreflightResult(
            status="budget_blocked",
            ok=False,
            message="Anthropic Max envelope allocation is exhausted",
            details={"used": budget.used, "cap": budget.cap, "available": budget.available},
        )

    argv = (
        binary,
        "--print",
        "--max-budget-usd",
        max_budget_usd,
        "--output-format",
        "text",
        "--no-session-persistence",
        prompt,
    )
    return PreflightResult(
        status="ready",
        ok=True,
        message="Claude print invocation is ready but not executed",
        argv=argv,
        details={"budget_reason": budget.reason},
    )


def prepare_codex_print_invocation(
    prompt: str,
    *,
    binary_resolver: BinaryResolver | None = None,
    priority: bool = False,
) -> PreflightResult:
    """Prepare a Codex print invocation without running it.

    Codex flags remain unresolved until verified docs or local help exist.
    """
    halt = is_halted("codex_auto_dispatch")
    if halt.halted:
        return PreflightResult(
            status="halted",
            ok=False,
            message=halt.message,
            details={"active_flag": halt.active_flag},
        )

    resolver = binary_resolver or _default_binary_resolver
    binary = resolver("codex")
    if not binary:
        return PreflightResult("missing_binary", False, "Required binary 'codex' was not found on PATH")

    budget = check_budget(load_envelope_state(), "chatgpt_pro", priority=priority)
    if not budget.allowed:
        return PreflightResult(
            status="budget_blocked",
            ok=False,
            message="ChatGPT Pro envelope allocation is exhausted",
            details={"used": budget.used, "cap": budget.cap, "available": budget.available},
        )

    return PreflightResult(
        status="missing_verified_flags",
        ok=False,
        message="Codex print flags are not verified in this A-slice",
        details={"binary": binary, "prompt_length": len(prompt)},
    )
```

- [ ] **Step 4: Run wrapper tests and verify GREEN**

Run:

```bash
python -m pytest tests/agent/test_cmh_subprocess_wrappers.py -q -o 'addopts='
```

Expected: PASS, 6 tests.

- [ ] **Step 5: Run all subprocess package tests so far**

Run:

```bash
python -m pytest \
  tests/agent/test_cmh_subprocess_flags.py \
  tests/agent/test_cmh_subprocess_envelope.py \
  tests/agent/test_cmh_subprocess_halt_flags.py \
  tests/agent/test_cmh_subprocess_wrappers.py \
  -q -o 'addopts='
```

Expected: PASS, all tests.

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add agent/cmh_subprocess/wrappers.py tests/agent/test_cmh_subprocess_wrappers.py
git commit -m "feat: add CMH subprocess wrapper preflight"
```

## Task 5: Budget display formatter

**Files:**
- Create: `agent/cmh_subprocess/budget_display.py`
- Create: `tests/agent/test_cmh_subprocess_budget_display.py`

- [ ] **Step 1: Write failing tests for budget display formatting**

Create `tests/agent/test_cmh_subprocess_budget_display.py`:

```python
from agent.cmh_subprocess.budget_display import format_budget_status
from agent.cmh_subprocess.envelope import default_envelope_state
from agent.cmh_subprocess.halt_flags import default_halt_flags


def test_budget_status_formats_default_state_without_secrets():
    output = format_budget_status(default_envelope_state(), default_halt_flags())

    assert "Cowork envelope: 0/191 used, 191 available, window not started" in output
    assert "Codex envelope: 0/170 used, 170 available, window not started" in output
    assert "Halt flags: all=false, cowork_headless=false, codex_auto_dispatch=false" in output
    assert "API_KEY" not in output
    assert "TOKEN" not in output
    assert "SECRET" not in output


def test_budget_status_formats_used_counts_and_window():
    state = default_envelope_state()
    state["anthropic_max"]["envelope_messages_used_5h"] = 5
    state["anthropic_max"]["window_start_iso"] = "2026-05-17T20:00:00+00:00"
    flags = default_halt_flags()
    flags["cowork_headless"] = True

    output = format_budget_status(state, flags)

    assert "Cowork envelope: 5/191 used, 186 available, window started 2026-05-17T20:00:00+00:00" in output
    assert "cowork_headless=true" in output
```

- [ ] **Step 2: Run budget display tests and verify RED**

Run:

```bash
python -m pytest tests/agent/test_cmh_subprocess_budget_display.py -q -o 'addopts='
```

Expected: FAIL with missing `agent.cmh_subprocess.budget_display`.

- [ ] **Step 3: Implement pure budget display formatter**

Create `agent/cmh_subprocess/budget_display.py`:

```python
"""Pure budget status formatting for CMH subprocess wrapper foundations."""

from __future__ import annotations

from typing import Any

from agent.cmh_subprocess.envelope import allocation_cap


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _line(label: str, record: dict[str, Any]) -> str:
    used = int(record.get("envelope_messages_used_5h", 0))
    cap = allocation_cap(record)
    available = max(cap - used, 0)
    window = record.get("window_start_iso")
    if window:
        return f"{label} envelope: {used}/{cap} used, {available} available, window started {window}"
    return f"{label} envelope: {used}/{cap} used, {available} available, window not started"


def format_budget_status(envelope_state: dict[str, dict[str, Any]], halt_flags: dict[str, bool]) -> str:
    """Return a secret-free local budget status string."""
    lines = [
        _line("Cowork", envelope_state["anthropic_max"]),
        _line("Codex", envelope_state["chatgpt_pro"]),
        "Halt flags: "
        f"all={_bool_text(halt_flags.get('all', False))}, "
        f"cowork_headless={_bool_text(halt_flags.get('cowork_headless', False))}, "
        f"codex_auto_dispatch={_bool_text(halt_flags.get('codex_auto_dispatch', False))}",
    ]
    return "\n".join(lines)
```

- [ ] **Step 4: Run budget display tests and verify GREEN**

Run:

```bash
python -m pytest tests/agent/test_cmh_subprocess_budget_display.py -q -o 'addopts='
```

Expected: PASS, 2 tests.

- [ ] **Step 5: Commit Task 5**

Run:

```bash
git add agent/cmh_subprocess/budget_display.py tests/agent/test_cmh_subprocess_budget_display.py
git commit -m "feat: add CMH subprocess budget display"
```

## Task 6: Package exports and final verification

**Files:**
- Modify: `agent/cmh_subprocess/__init__.py`

- [ ] **Step 1: Write failing test for package exports**

Append to `tests/agent/test_cmh_subprocess_wrappers.py`:

```python

def test_package_exports_preflight_helpers():
    import agent.cmh_subprocess as cmh_subprocess

    assert callable(cmh_subprocess.prepare_claude_print_invocation)
    assert callable(cmh_subprocess.prepare_codex_print_invocation)
```

- [ ] **Step 2: Run export test and verify RED**

Run:

```bash
python -m pytest tests/agent/test_cmh_subprocess_wrappers.py::test_package_exports_preflight_helpers -q -o 'addopts='
```

Expected: FAIL with `AttributeError` for missing export.

- [ ] **Step 3: Update package exports**

Replace `agent/cmh_subprocess/__init__.py` with:

```python
"""CMH subprocess wrapper foundation.

Local foundation only. This package does not activate live routing,
Telegram sends, gateway behavior, cron, daemon, MCP, deploy, merge, or
production mutation.
"""

from agent.cmh_subprocess.budget_display import format_budget_status
from agent.cmh_subprocess.envelope import check_budget, increment_usage, load_envelope_state
from agent.cmh_subprocess.halt_flags import is_halted, load_halt_flags
from agent.cmh_subprocess.wrappers import prepare_claude_print_invocation, prepare_codex_print_invocation

__all__ = [
    "check_budget",
    "format_budget_status",
    "increment_usage",
    "is_halted",
    "load_envelope_state",
    "load_halt_flags",
    "prepare_claude_print_invocation",
    "prepare_codex_print_invocation",
]
```

- [ ] **Step 4: Run export test and verify GREEN**

Run:

```bash
python -m pytest tests/agent/test_cmh_subprocess_wrappers.py::test_package_exports_preflight_helpers -q -o 'addopts='
```

Expected: PASS.

- [ ] **Step 5: Run full A-slice test set**

Run:

```bash
python -m pytest \
  tests/agent/test_cmh_subprocess_flags.py \
  tests/agent/test_cmh_subprocess_envelope.py \
  tests/agent/test_cmh_subprocess_halt_flags.py \
  tests/agent/test_cmh_subprocess_wrappers.py \
  tests/agent/test_cmh_subprocess_budget_display.py \
  -q -o 'addopts='
```

Expected: PASS, all tests.

- [ ] **Step 6: Run focused static checks**

Run:

```bash
python -m py_compile \
  agent/cmh_subprocess/__init__.py \
  agent/cmh_subprocess/result.py \
  agent/cmh_subprocess/flags.py \
  agent/cmh_subprocess/envelope.py \
  agent/cmh_subprocess/halt_flags.py \
  agent/cmh_subprocess/wrappers.py \
  agent/cmh_subprocess/budget_display.py

git diff --check
```

Expected: both commands exit 0.

- [ ] **Step 7: Verify no activation surfaces changed**

Run:

```bash
git diff --name-only HEAD~5..HEAD | sort
```

Expected changed files are limited to:

```text
agent/cmh_subprocess/__init__.py
agent/cmh_subprocess/budget_display.py
agent/cmh_subprocess/envelope.py
agent/cmh_subprocess/flags.py
agent/cmh_subprocess/halt_flags.py
agent/cmh_subprocess/result.py
agent/cmh_subprocess/wrappers.py
tests/agent/test_cmh_subprocess_budget_display.py
tests/agent/test_cmh_subprocess_envelope.py
tests/agent/test_cmh_subprocess_flags.py
tests/agent/test_cmh_subprocess_halt_flags.py
tests/agent/test_cmh_subprocess_wrappers.py
```

If this list includes gateway, cron, MCP, send, config, launchd, vault dispatch, or provider files, stop and inspect before continuing.

- [ ] **Step 8: Commit final export task**

Run:

```bash
git add agent/cmh_subprocess/__init__.py tests/agent/test_cmh_subprocess_wrappers.py
git commit -m "chore: export CMH subprocess foundation helpers"
```

## Task 7: Closeout note

**Files:**
- Create: `docs/closeouts/2026-05-17-hermes-local-subprocess-wrapper-foundation-closeout.md`

- [ ] **Step 1: Create closeout after all tests are green**

Create `docs/closeouts/2026-05-17-hermes-local-subprocess-wrapper-foundation-closeout.md`:

```markdown
# Hermes Local Subprocess Wrapper Foundation Closeout

Date: 2026-05-17
Scope: A-slice local foundation only

## What changed

- Added `agent/cmh_subprocess/` local foundation package.
- Added CLI flag verification for Claude help evidence.
- Added profile-aware envelope state helpers.
- Added profile-aware halt flag helpers.
- Added disabled-by-default wrapper preflight helpers.
- Added pure budget display formatter.
- Added focused pytest coverage.

## Verification

- `python -m pytest tests/agent/test_cmh_subprocess_flags.py tests/agent/test_cmh_subprocess_envelope.py tests/agent/test_cmh_subprocess_halt_flags.py tests/agent/test_cmh_subprocess_wrappers.py tests/agent/test_cmh_subprocess_budget_display.py -q -o 'addopts='` passed.
- `python -m py_compile agent/cmh_subprocess/__init__.py agent/cmh_subprocess/result.py agent/cmh_subprocess/flags.py agent/cmh_subprocess/envelope.py agent/cmh_subprocess/halt_flags.py agent/cmh_subprocess/wrappers.py agent/cmh_subprocess/budget_display.py` passed.
- `git diff --check` passed.

## Activation status

No activation occurred.

Not changed:

- Telegram sends or Telegram verbs.
- Gateway callbacks, gateway restart, or gateway config.
- Cron, launchd, daemon, MCP, AgentMail, provider, or profile config.
- `~/.hermes/wrappers/` or `~/.hermes/bin/` runtime scripts.
- Cowork-headless spawn.
- Codex auto-dispatch.
- R109 fire.
- Git push, merge, deploy, or production mutation.

## Known dependencies for later phases

- Codex Wave 1.16.E verified flag docs are still required before activation.
- `codex` must be present on PATH or the Codex wrapper remains disabled.
- Any Telegram or gateway exposure requires separate exact approval.
```

- [ ] **Step 2: Verify closeout has no em dashes and no placeholders**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('docs/closeouts/2026-05-17-hermes-local-subprocess-wrapper-foundation-closeout.md')
s = p.read_text(encoding='utf-8')
for forbidden in [chr(8212), 'TB' + 'D', 'TO' + 'DO']:
    assert forbidden not in s
print('closeout ok')
PY
```

Expected: prints `closeout ok`.

- [ ] **Step 3: Commit closeout**

Run:

```bash
git add docs/closeouts/2026-05-17-hermes-local-subprocess-wrapper-foundation-closeout.md
git commit -m "docs: close out CMH subprocess foundation"
```

## Final Verification Checklist

- [ ] Every production module was added after a failing test.
- [ ] Every test was observed failing for the expected reason before implementation.
- [ ] Full A-slice pytest command passes.
- [ ] `py_compile` passes for all new modules.
- [ ] `git diff --check` passes.
- [ ] No real Claude or Codex model subprocess invocation occurred.
- [ ] No real `~/.hermes/state` file was modified by tests.
- [ ] No Telegram, gateway, cron, launchd, MCP, provider, send, deploy, merge, R-audit, or production surface changed.
- [ ] Codex missing binary remains a clean disabled result.
- [ ] Claude required flags use `--max-budget-usd`, not draft `--max-cost-usd`.

## Implementation Handoff Notes

- Use subagent-driven execution if possible, one task per worker, but keep the parent responsible for reviewing diffs and checking activation boundaries.
- Do not add the local `/budget` slash command in this A-slice unless Christopher separately asks for it. The pure formatter gives us a safe seam for that later.
- The repository currently has unrelated dirty files and one local spec commit. Implementation workers must avoid touching unrelated files.
- Before starting implementation, run `git status -sb` and record the pre-existing dirty files so they are not accidentally committed with this work.
