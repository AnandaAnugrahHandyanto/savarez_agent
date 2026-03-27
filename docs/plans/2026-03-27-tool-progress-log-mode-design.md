# `log` Tool Progress Mode — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `"log"` as a fifth `tool_progress` option that writes timestamped tool-call lines to `~/.hermes/logs/tool_calls.log` without sending any messages to the messaging platform chat.

**Architecture:** A new async coroutine `write_tool_log()` drains a dedicated `log_queue` and writes to a `RotatingFileHandler`. The gateway's `/verbose` command cycle is extended from 4 to 5 modes. The CLI is unchanged — `log` mode is gateway-only.

**Tech Stack:** Python asyncio, `logging.handlers.RotatingFileHandler`, PyYAML, `queue.Queue`.

---

## Task 1: Add `log` to the `/verbose` command description

**Files:**
- Modify: `hermes_cli/commands.py:90`

**Step 1: Update the CommandDef description**

```python
# Before
CommandDef("verbose", "Cycle tool progress display: off -> new -> all -> verbose",

# After
CommandDef("verbose", "Cycle tool progress display: off -> new -> all -> verbose -> log",
```

**Step 2: Commit**

```bash
git add hermes_cli/commands.py
git commit -m "docs: update /verbose description to include log mode"
```

---

## Task 2: Add `log` to the setup wizard

**Files:**
- Modify: `hermes_cli/setup.py:2297-2315`

**Step 1: Add the log option description**

```python
# In the Tool Progress Display section, after the "verbose" print_info line add:
print_info("  log     — Silent in chat; write every tool call to ~/.hermes/logs/tool_calls.log")
```

**Step 2: Add `"log"` to the validation check**

```python
# Before
if mode.lower() in ("off", "new", "all", "verbose"):

# After
if mode.lower() in ("off", "new", "all", "verbose", "log"):
```

**Step 3: Commit**

```bash
git add hermes_cli/setup.py
git commit -m "feat(setup): add log option to tool progress mode wizard"
```

---

## Task 3: Update the deprecated env var comment

**Files:**
- Modify: `hermes_cli/config.py:912`

**Step 1: Update the comment**

```python
# Before
# now configured via display.tool_progress in config.yaml (off|new|all|verbose).

# After
# now configured via display.tool_progress in config.yaml (off|new|all|verbose|log).
```

**Step 2: Commit**

```bash
git add hermes_cli/config.py
git commit -m "docs: update deprecated env var comment to include log mode"
```

---

## Task 4: Implement `log` mode in `gateway/run.py` — core logic

**Files:**
- Modify: `gateway/run.py:4904-5068` (progress mode setup + callback + send_progress_messages)
- Modify: `gateway/run.py:5452-5454` (start log task alongside progress task)
- Modify: `gateway/run.py:5601-5629` (cancel log task in finally block)

**Step 1: Read the exact block to edit**

Read `gateway/run.py` lines 4904–5068 and 5448–5460 and 5601–5630.

**Step 2: After `tool_progress_enabled = progress_mode != "off"` add:**

```python
# log mode is separate — it writes to a file instead of the chat
log_mode_enabled = progress_mode == "log"

# Queue for tool-call log file writes (only used when progress_mode == "log")
log_queue = queue.Queue() if log_mode_enabled else None
```

**Step 3: In `progress_callback`, after the `if not progress_queue: return` guard, add the log-mode branch before the "new" mode check:**

```python
# "log" mode: write to file without sending chat messages
if progress_mode == "log":
    if log_queue:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        preview_str = f'"{preview}"' if preview else ""
        log_line = f"{timestamp}  {tool_name}: {preview_str}".rstrip()
        log_queue.put(log_line)
    return
```

You need to add `from datetime import datetime` at the top of the handler or use `import datetime`. Add it alongside the existing `import json as _json` inside the verbose branch.

**Step 4: Extend the `send_progress_messages` `finally` block (line 5601) to also cancel the log task:**

```python
# Before
if progress_task:
    progress_task.cancel()
interrupt_monitor.cancel()

# After
if progress_task:
    progress_task.cancel()
if log_task:
    log_task.cancel()
interrupt_monitor.cancel()
```

**Step 5: In the task-waiting loop (line 5624), add `log_task` to the list:**

```python
# Before
for task in [progress_task, interrupt_monitor, tracking_task]:

# After
for task in [progress_task, log_task, interrupt_monitor, tracking_task]:
```

**Step 6: Commit**

```bash
git add gateway/run.py
git commit -m "feat(gateway): add log mode for tool_progress — writes to tool_calls.log"
```

---

## Task 5: Add the `write_tool_log()` coroutine and start/cancel it

**Files:**
- Modify: `gateway/run.py` — add `write_tool_log()` coroutine after `send_progress_messages()`, start it at line 5453, declare `log_task` at line 5452

**Step 1: Add `write_tool_log()` coroutine after `send_progress_messages()` (after line 5068)**

```python
async def write_tool_log():
    """Drains log_queue and writes timestamped tool-call lines to tool_calls.log."""
    if not log_queue:
        return

    log_dir = _hermes_home / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    from logging.handlers import RotatingFileHandler
    from agent.redact import RedactingFormatter
    file_handler = RotatingFileHandler(
        log_dir / 'tool_calls.log',
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
    )
    file_handler.setFormatter(RedactingFormatter('%(message)s'))
    tool_logger = logging.getLogger("hermes.tool_calls")
    tool_logger.setLevel(logging.INFO)
    tool_logger.addHandler(file_handler)

    try:
        while True:
            try:
                line = log_queue.get_nowait()
                tool_logger.info("%s", line)
            except queue.Empty:
                await asyncio.sleep(0.3)
            except asyncio.CancelledError:
                # Drain remaining entries before exit
                while not log_queue.empty():
                    try:
                        line = log_queue.get_nowait()
                        tool_logger.info("%s", line)
                    except queue.Empty:
                        break
                return
            except Exception as e:
                logger.error("write_tool_log error: %s", e)
                await asyncio.sleep(1)
    finally:
        tool_logger.removeHandler(file_handler)
        file_handler.close()
```

**Step 2: At line 5452, add `log_task = None` and start the log task**

```python
# After "progress_task = None"
log_task = None
if tool_progress_enabled:
    progress_task = asyncio.create_task(send_progress_messages())

# After the progress_task start block, add:
if log_mode_enabled:
    log_task = asyncio.create_task(write_tool_log())
```

**Step 3: Verify `logging` is already imported at the top of the file** — grep for `import logging` in `gateway/run.py`. If not present, add `import logging` near the top.

**Step 4: Commit**

```bash
git add gateway/run.py
git commit -m "feat(gateway): add write_tool_log coroutine and wire it into the agent run task"
```

---

## Task 6: Extend the `/verbose` command cycle to include `log`

**Files:**
- Modify: `gateway/run.py:3926-3933`

**Step 1: Update the cycle and descriptions**

```python
# Before
cycle = ["off", "new", "all", "verbose"]
descriptions = {
    "off": "⚙️ Tool progress: **OFF** — no tool activity shown.",
    "new": "⚙️ Tool progress: **NEW** — shown when tool changes.",
    "all": "⚙️ Tool progress: **ALL** — every tool call shown.",
    "verbose": "⚙️ Tool progress: **VERBOSE** — full args and results.",
}

# After
cycle = ["off", "new", "all", "verbose", "log"]
descriptions = {
    "off": "⚙️ Tool progress: **OFF** — no tool activity shown.",
    "new": "⚙️ Tool progress: **NEW** — shown when tool changes.",
    "all": "⚙️ Tool progress: **ALL** — every tool call shown.",
    "verbose": "⚙️ Tool progress: **VERBOSE** — full args and results.",
    "log": "⚙️ Tool progress: **LOG** — silent in chat; writing to tool_calls.log.",
}
```

**Step 2: Commit**

```bash
git add gateway/run.py
git commit -m "feat(gateway): add log to /verbose cycle and descriptions"
```

---

## Task 7: Write tests for `log` mode

**Files:**
- Modify: `tests/gateway/test_verbose_command.py`
- Create: `tests/gateway/test_tool_log_mode.py`

### Test in `test_verbose_command.py`

**Step 1: Update `test_cycles_through_all_modes`**

```python
# In test_verbose_command.py, change:
# off -> new -> all -> verbose -> off
# to:
# off -> new -> all -> verbose -> log -> off

expected = ["new", "all", "verbose", "log", "off"]
```

**Step 2: Run to verify**

```bash
python -m pytest tests/gateway/test_verbose_command.py -v
```

### New file `tests/gateway/test_tool_log_mode.py`

**Step 1: Write the test file**

```python
"""Tests for log mode in gateway tool_progress."""

import asyncio
import importlib
import sys
import time
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, SendResult
from gateway.session import SessionSource


class NoSendAdapter(BasePlatformAdapter):
    """Adapter that records whether any message was sent — log mode should send nothing."""
    def __init__(self):
        super().__init__(PlatformConfig(enabled=True, token="fake-token"), Platform.TELEGRAM)
        self.sent = []

    async def connect(self) -> bool:
        return True

    async def disconnect(self) -> None:
        return None

    async def send(self, chat_id, content, reply_to=None, metadata=None) -> SendResult:
        self.sent.append(content)
        return SendResult(success=True, message_id="msg-1")

    async def edit_message(self, chat_id, message_id, content) -> SendResult:
        return SendResult(success=True, message_id=message_id)

    async def send_typing(self, chat_id, metadata=None) -> None:
        pass

    async def get_chat_info(self, chat_id: str):
        return {"id": chat_id}


class FakeAgentLog:
    def __init__(self, **kwargs):
        self.tool_progress_callback = kwargs.get("tool_progress_callback")
        self.tools = []

    def run_conversation(self, message, conversation_history=None, task_id=None):
        if self.tool_progress_callback:
            self.tool_progress_callback("terminal", "ls -la")
            time.sleep(0.1)
            self.tool_progress_callback("read_file", "setup.py")
        return {"final_response": "done", "messages": [], "api_calls": 1}


def _make_runner(adapter):
    gateway_run = importlib.import_module("gateway.run")
    GatewayRunner = gateway_run.GatewayRunner
    runner = object.__new__(GatewayRunner)
    runner.adapters = {Platform.TELEGRAM: adapter}
    runner._voice_mode = {}
    runner._prefill_messages = []
    runner._ephemeral_system_prompt = ""
    runner._reasoning_config = None
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._session_db = None
    runner._running_agents = {}
    runner.hooks = MagicMock()
    runner.hooks.loaded_hooks = False
    return runner


@pytest.mark.asyncio
async def test_log_mode_writes_to_file(monkeypatch, tmp_path: Path):
    """log mode writes timestamped tool calls to tool_calls.log and sends nothing to chat."""
    monkeypatch.setenv("HERMES_TOOL_PROGRESS_MODE", "log")

    fake_dotenv = types.ModuleType("dotenv")
    fake_dotenv.load_dotenv = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "dotenv", fake_dotenv)

    fake_run_agent = types.ModuleType("run_agent")
    fake_run_agent.AIAgent = FakeAgentLog
    monkeypatch.setitem(sys.modules, "run_agent", fake_run_agent)

    adapter = NoSendAdapter()
    runner = _make_runner(adapter)
    gateway_run = importlib.import_module("gateway.run")
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "fake"})

    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="-1001",
        chat_type="private",
        thread_id=None,
    )

    result = await runner._run_agent(
        message="hello",
        context_prompt="",
        history=[],
        source=source,
        session_id="sess-log-1",
        session_key="agent:main:telegram:private:-1001",
    )

    assert result["final_response"] == "done"
    # log mode sends nothing to the chat
    assert adapter.sent == [], f"Expected no messages in log mode, got: {adapter.sent}"

    # But tool_calls.log should exist and contain the tool calls
    log_file = tmp_path / "logs" / "tool_calls.log"
    assert log_file.exists(), f"Expected tool_calls.log to exist at {log_file}"

    content = log_file.read_text(encoding="utf-8")
    # Each line should have a timestamp prefix and tool name
    assert "terminal:" in content
    assert "read_file:" in content
    # Verify timestamp format (YYYY-MM-DD HH:MM:SS  tool_name:)
    import re
    timestamp_pattern = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}  \w+:")
    lines = [l for l in content.strip().split("\n") if l]
    assert all(timestamp_pattern.match(line) for line in lines), \
        f"Not all lines match timestamp format: {lines}"


@pytest.mark.asyncio
async def test_log_mode_not_enabled_when_other_mode(monkeypatch, tmp_path: Path):
    """When tool_progress is 'all', no tool_calls.log should be created."""
    monkeypatch.setenv("HERMES_TOOL_PROGRESS_MODE", "all")

    fake_dotenv = types.ModuleType("dotenv")
    fake_dotenv.load_dotenv = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "dotenv", fake_dotenv)

    fake_run_agent = types.ModuleType("run_agent")
    fake_run_agent.AIAgent = FakeAgentLog
    monkeypatch.setitem(sys.modules, "run_agent", fake_run_agent)

    adapter = NoSendAdapter()
    runner = _make_runner(adapter)
    gateway_run = importlib.import_module("gateway.run")
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "fake"})

    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="-1002",
        chat_type="private",
        thread_id=None,
    )

    result = await runner._run_agent(
        message="hello",
        context_prompt="",
        history=[],
        source=source,
        session_id="sess-all-1",
        session_key="agent:main:telegram:private:-1002",
    )

    log_file = tmp_path / "logs" / "tool_calls.log"
    assert not log_file.exists(), "tool_calls.log should NOT exist when mode is 'all'"
```

**Step 2: Run the new tests**

```bash
python -m pytest tests/gateway/test_tool_log_mode.py -v
```

Expected: both tests pass.

**Step 3: Run the updated verbose command tests**

```bash
python -m pytest tests/gateway/test_verbose_command.py -v
```

Expected: all tests pass.

**Step 4: Commit**

```bash
git add tests/gateway/test_tool_log_mode.py tests/gateway/test_verbose_command.py
git commit -m "test: add tool_log_mode tests and update verbose cycle test"
```

---

## Task 8: Run full test suite

**Step 1: Run the full test suite**

```bash
source venv/bin/activate && python -m pytest tests/ -q --tb=short 2>&1 | tail -20
```

Expected: all tests pass. If any fail, investigate and fix.

**Step 2: Commit any fixes**

---

## Summary of Files Changed

| File | Change |
|------|--------|
| `hermes_cli/commands.py:90` | Update `/verbose` description to include `log` |
| `hermes_cli/setup.py:2297-2315` | Add `log` to setup wizard options and validation |
| `hermes_cli/config.py:912` | Update deprecated env var comment to include `log` |
| `gateway/run.py` | Add `log_mode_enabled`, `log_queue`, `write_tool_log()` coroutine, extend cycle, wire task lifecycle |
| `tests/gateway/test_verbose_command.py` | Update cycle test to include `log` |
| `tests/gateway/test_tool_log_mode.py` | New test file for `log` mode behavior |
