# Skills Prompt Budget And Nudge Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce Hermes skill-index prompt cost with an opt-in v2 structural index and replace noisy time-only skill nudges with opt-in signal-based nudges.

**Architecture:** Extract skill metadata collection into a shared inventory module used by both prompt rendering and skill tools. Keep v1 prompt rendering available behind config while v2 renders a budgeted category/name index with critical descriptions and an on-demand `skill_describe` tool. Add nudge-signal state to `AIAgent`, evaluate signals from tool-call/result history, and keep the old interval as a fallback.

**Tech Stack:** Python, pytest, Hermes tool registry, YAML config defaults, JSON state files under `HERMES_HOME`.

---

## File Structure

- Create: `agent/skill_inventory.py` — shared parsed skill metadata, local snapshot v2, external-dir scan, priority parsing, category descriptions, prompt-cache invalidation hook.
- Modify: `agent/prompt_builder.py` — delegate inventory loading, keep v1 renderer, add v2 renderer and budget folding behind `skills.index_v2`.
- Modify: `tools/skills_tool.py` — add `skill_describe`, register its schema, record best-effort skill usage from `skill_view` and `skill_describe`.
- Modify: `hermes_cli/config.py` — add config defaults for `skills.index_v2`, `skills.index_token_budget`, and `skills.nudge_signals`.
- Modify: `cli-config.yaml.example` — document opt-in defaults for Phase 1-2.
- Modify: `run_agent.py` — add nudge-signal config/state/helpers, evaluate signals, gate background review, add signal context.
- Modify: `cli.py`, `tui_gateway/server.py`, and relevant gateway slash mirrors if needed — intercept `/skills nudge off` before the Skills Hub router and set per-session state.
- Test: `tests/agent/test_prompt_builder.py` — inventory, v1 compatibility, v2 rendering, budget folding, cache invalidation.
- Test: `tests/tools/test_skills_tool.py` — `skill_describe` and usage recording.
- Test: `tests/run_agent/test_run_agent.py` — nudge signals, fallback, disable behavior, background context.

---

### Task 1: Shared Skill Inventory

**Files:**
- Create: `agent/skill_inventory.py`
- Modify: `agent/prompt_builder.py:463-747`
- Test: `tests/agent/test_prompt_builder.py`

- [ ] **Step 1: Write inventory tests first**

Add this test near `TestBuildSkillsSystemPrompt` in `tests/agent/test_prompt_builder.py`:

```python
def test_inventory_reads_priority_and_category_descriptions(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    skill_dir = tmp_path / "skills" / "workflow" / "verify"
    skill_dir.mkdir(parents=True)
    (tmp_path / "skills" / "workflow" / "DESCRIPTION.md").write_text(
        "---\ndescription: Workflow discipline\n---\n", encoding="utf-8"
    )
    (skill_dir / "SKILL.md").write_text(
        "---\nname: verify\ndescription: Verify before reporting\npriority: critical\n---\nBody",
        encoding="utf-8",
    )

    from agent.skill_inventory import load_skill_inventory

    inventory = load_skill_inventory()
    assert inventory.category_descriptions["workflow"] == "Workflow discipline"
    assert inventory.by_category["workflow"][0].name == "verify"
    assert inventory.by_category["workflow"][0].priority == "critical"
```

- [ ] **Step 2: Run the new test and verify it fails**

Run: `pytest tests/agent/test_prompt_builder.py::test_inventory_reads_priority_and_category_descriptions -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'agent.skill_inventory'`.

- [ ] **Step 3: Create `agent/skill_inventory.py` with metadata dataclasses**

```python
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from agent.skill_utils import (
    extract_skill_conditions,
    get_all_skills_dirs,
    get_disabled_skill_names,
    iter_skill_index_files,
    parse_frontmatter,
    skill_matches_platform,
)
from utils import atomic_json_write

logger = logging.getLogger(__name__)
_SKILLS_SNAPSHOT_VERSION = 2

@dataclass(frozen=True)
class SkillIndexEntry:
    name: str
    skill_name: str
    category: str
    description: str
    priority: str = "normal"
    platforms: tuple[str, ...] = ()
    conditions: dict = field(default_factory=dict)
    source_dir: str = ""

@dataclass(frozen=True)
class SkillInventory:
    entries: tuple[SkillIndexEntry, ...]
    category_descriptions: dict[str, str]

    @property
    def by_category(self) -> dict[str, list[SkillIndexEntry]]:
        grouped: dict[str, list[SkillIndexEntry]] = {}
        for entry in self.entries:
            grouped.setdefault(entry.category, []).append(entry)
        for entries in grouped.values():
            entries.sort(key=lambda item: item.name)
        return grouped

def normalize_priority(value: object) -> str:
    return "critical" if str(value or "").strip().lower() == "critical" else "normal"
```

- [ ] **Step 4: Move snapshot and parsing helpers into the inventory module**

Move the current helper logic from `agent/prompt_builder.py:472-587` into `agent/skill_inventory.py`. Preserve the current manifest semantics and add priority/source metadata:

```python
def _skills_prompt_snapshot_path() -> Path:
    from hermes_constants import get_hermes_home
    return get_hermes_home() / ".skills_prompt_snapshot.json"

def _build_snapshot_entry(skill_file: Path, skills_dir: Path, frontmatter: dict, description: str) -> dict:
    rel_path = skill_file.relative_to(skills_dir)
    parts = rel_path.parts
    if len(parts) >= 2:
        skill_name = parts[-2]
        category = "/".join(parts[:-2]) if len(parts) > 2 else parts[0]
    else:
        category = "general"
        skill_name = skill_file.parent.name
    platforms = frontmatter.get("platforms") or []
    if isinstance(platforms, str):
        platforms = [platforms]
    return {
        "skill_name": skill_name,
        "category": category,
        "frontmatter_name": str(frontmatter.get("name", skill_name)),
        "description": description,
        "priority": normalize_priority(frontmatter.get("priority")),
        "platforms": [str(p).strip() for p in platforms if str(p).strip()],
        "conditions": extract_skill_conditions(frontmatter),
        "source_dir": str(skills_dir),
    }
```

- [ ] **Step 5: Implement `load_skill_inventory()`**

The public function must accept `available_tools` and `available_toolsets`, reuse the existing platform/disabled/conditions filtering, and scan local skills before external dirs so local names win:

```python
def load_skill_inventory(
    available_tools: set[str] | None = None,
    available_toolsets: set[str] | None = None,
) -> SkillInventory:
    from hermes_constants import get_skills_dir
    skills_dir = get_skills_dir()
    external_dirs = get_all_skills_dirs()[1:]
    disabled = get_disabled_skill_names()
    entries: list[SkillIndexEntry] = []
    category_descriptions: dict[str, str] = {}
    seen_names: set[str] = set()

    # Use the current prompt_builder snapshot path for the local dir, then scan external dirs directly.
    # Convert accepted snapshot records through _entry_from_snapshot().
    # For cold local/external records, use _parse_skill_file() and _build_snapshot_entry().

    return SkillInventory(entries=tuple(entries), category_descriptions=category_descriptions)
```

Fill the body from the existing `agent/prompt_builder.py:639-793` logic; do not change behavior for `requires_tools`, `fallback_for_tools`, platforms, disabled skills, or external-dir dedupe.

- [ ] **Step 6: Make `prompt_builder` import inventory helpers**

In `agent/prompt_builder.py`, import:

```python
from agent.skill_inventory import SkillInventory, SkillIndexEntry, clear_skill_inventory_cache, load_skill_inventory
```

Update `clear_skills_system_prompt_cache()` so it clears both caches:

```python
def clear_skills_system_prompt_cache(*, clear_snapshot: bool = False) -> None:
    with _SKILLS_PROMPT_CACHE_LOCK:
        _SKILLS_PROMPT_CACHE.clear()
    clear_skill_inventory_cache(clear_snapshot=clear_snapshot)
```

- [ ] **Step 7: Run inventory regression tests**

Run: `pytest tests/agent/test_prompt_builder.py::test_inventory_reads_priority_and_category_descriptions tests/agent/test_prompt_builder.py::TestBuildSkillsSystemPrompt::test_builds_index_with_skills -q`

Expected: PASS.

- [ ] **Step 8: Commit Task 1**

```bash
git add agent/skill_inventory.py agent/prompt_builder.py tests/agent/test_prompt_builder.py
git commit -m "refactor: share skill inventory metadata"
```

---

### Task 2: V2 Prompt Renderer And Budget Folding

**Files:**
- Modify: `agent/prompt_builder.py:621-847`
- Modify: `hermes_cli/config.py:793-818`
- Test: `tests/agent/test_prompt_builder.py`

- [ ] **Step 1: Write failing v2 rendering tests**

```python
def test_skills_prompt_v2_hides_normal_descriptions(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text("skills:\n  index_v2: true\n", encoding="utf-8")
    normal = tmp_path / "skills" / "coding" / "normal"
    critical = tmp_path / "skills" / "coding" / "critical"
    normal.mkdir(parents=True)
    critical.mkdir(parents=True)
    (normal / "SKILL.md").write_text("---\nname: normal\ndescription: Normal hidden\n---\nBody", encoding="utf-8")
    (critical / "SKILL.md").write_text("---\nname: critical\ndescription: Critical shown\npriority: critical\n---\nBody", encoding="utf-8")

    prompt = build_skills_system_prompt()
    assert "## Skills" in prompt
    assert "skill_describe" in prompt
    assert "normal" in prompt
    assert "Normal hidden" not in prompt
    assert "critical: Critical shown" in prompt
```

```python
def test_skills_prompt_v2_budget_folds_categories(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text("skills:\n  index_v2: true\n  index_token_budget: 160\n", encoding="utf-8")
    for i in range(40):
        d = tmp_path / "skills" / f"cat{i:02d}" / f"skill{i:02d}"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\nname: skill{i:02d}\ndescription: Description {i}\n---\nBody", encoding="utf-8")

    prompt = build_skills_system_prompt()
    assert len(prompt) // 4 <= 220
    assert "more categories" in prompt
    assert "Call skill_describe(category=" in prompt
```

- [ ] **Step 2: Run v2 tests and verify failure**

Run: `pytest tests/agent/test_prompt_builder.py::test_skills_prompt_v2_hides_normal_descriptions tests/agent/test_prompt_builder.py::test_skills_prompt_v2_budget_folds_categories -q`

Expected: FAIL because v2 config/rendering is absent.

- [ ] **Step 3: Add config defaults**

In `hermes_cli/config.py`, extend the existing `skills` defaults:

```python
"index_v2": False,
"index_token_budget": 2000,
"nudge_signals": {
    "enabled": False,
    "repeated_pattern_threshold": 3,
    "novel_cli_window_days": 30,
    "common_cli_suppressions": ["git", "python", "python3", "node", "npm", "pnpm", "uv", "pytest", "rg", "sed", "cat", "ls", "mkdir"],
    "user_phrases": ["next time", "remember", "from now on", "记一下", "下次", "以后"],
    "error_repeat_threshold": 2,
},
```

- [ ] **Step 4: Add prompt-builder config and v2 helpers**

```python
def _get_skills_index_config() -> tuple[bool, int]:
    try:
        from hermes_cli.config import load_config
        cfg = load_config().get("skills", {})
    except Exception:
        cfg = {}
    enabled = str(cfg.get("index_v2", False)).lower() in ("1", "true", "yes", "on")
    try:
        budget = int(cfg.get("index_token_budget", 2000))
    except (TypeError, ValueError):
        budget = 2000
    return enabled, max(400, budget)

def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)
```

- [ ] **Step 5: Split v1 and add v2 renderers**

Create `_render_skills_prompt_v1(inventory)` by moving the existing line-building code unchanged. Add v2 helpers:

```python
def _render_category_v2(category: str, entries: list[SkillIndexEntry], cat_desc: str) -> list[str]:
    lines = [f"  {category}/  {cat_desc}" if cat_desc else f"  {category}/"]
    normal_names: list[str] = []
    for entry in entries:
        if entry.priority == "critical" and entry.description:
            lines.append(f"    - {entry.name}: {entry.description}")
        else:
            normal_names.append(entry.name)
    if normal_names:
        lines.append("    " + ", ".join(normal_names))
    return lines

def _render_skills_prompt_v2(inventory: SkillInventory, token_budget: int) -> str:
    body_lines: list[str] = []
    for category in sorted(inventory.by_category.keys()):
        body_lines.extend(_render_category_v2(category, inventory.by_category[category], inventory.category_descriptions.get(category, "")))
    full = _SKILLS_V2_PREAMBLE + "\n".join(body_lines) + "\n</available_skills>"
    return _fold_skills_prompt_v2(full, inventory, token_budget)
```

- [ ] **Step 6: Implement budget folding**

```python
def _fold_skills_prompt_v2(full: str, inventory: SkillInventory, token_budget: int) -> str:
    if _estimate_tokens(full) <= token_budget:
        return full
    kept: list[str] = []
    hidden: list[str] = []
    for category in _rank_categories_for_budget(inventory):
        lines = _render_category_v2(category, inventory.by_category[category], inventory.category_descriptions.get(category, ""))
        candidate = _SKILLS_V2_PREAMBLE + "\n".join(kept + lines) + "\n</available_skills>"
        if _estimate_tokens(candidate) <= token_budget:
            kept.extend(lines)
        else:
            hidden.append(category)
    if hidden:
        kept.append(f"  ... and {len(hidden)} more categories: {', '.join(hidden)}. Call skill_describe(category=...) to expand any of these.")
    return _SKILLS_V2_PREAMBLE + "\n".join(kept) + "\n</available_skills>"
```

- [ ] **Step 7: Wire `build_skills_system_prompt()` to config**

```python
index_v2_enabled, token_budget = _get_skills_index_config()
cache_key = (..., "v2", index_v2_enabled, token_budget, _usage_rank_epoch(index_v2_enabled))
inventory = load_skill_inventory(available_tools=available_tools, available_toolsets=available_toolsets)
result = _render_skills_prompt_v2(inventory, token_budget) if index_v2_enabled else _render_skills_prompt_v1(inventory)
```

- [ ] **Step 8: Run prompt-builder tests**

Run: `pytest tests/agent/test_prompt_builder.py -q`

Expected: PASS.

- [ ] **Step 9: Commit Task 2**

```bash
git add agent/prompt_builder.py hermes_cli/config.py tests/agent/test_prompt_builder.py
git commit -m "feat: add budgeted skills prompt index"
```

---

### Task 3: `skill_describe` Tool And Usage Tracking

**Files:**
- Modify: `tools/skills_tool.py:428-1445`
- Modify: `agent/skill_inventory.py`
- Test: `tests/tools/test_skills_tool.py`

- [ ] **Step 1: Write `skill_describe` tests**

```python
def test_skill_describe_by_category(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    d = tmp_path / "skills" / "coding" / "python-debug"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: python-debug\ndescription: Debug Python\n---\nBody", encoding="utf-8")

    from tools.skills_tool import skill_describe
    result = json.loads(skill_describe(category="coding"))
    assert result["success"] is True
    assert result["skills"] == [{"name": "python-debug", "category": "coding", "description": "Debug Python"}]

def test_skill_describe_requires_filter():
    from tools.skills_tool import skill_describe
    result = json.loads(skill_describe())
    assert result["success"] is False
    assert "category or names" in result["error"]
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/tools/test_skills_tool.py::test_skill_describe_by_category tests/tools/test_skills_tool.py::test_skill_describe_requires_filter -q`

Expected: FAIL because `skill_describe` is not defined.

- [ ] **Step 3: Add usage helpers**

In `agent/skill_inventory.py`:

```python
def skill_usage_path() -> Path:
    from hermes_constants import get_hermes_home
    return get_hermes_home() / ".skill_usage.json"

def record_skill_usage(category: str, *, now_ts: float | None = None) -> None:
    import time
    ts = float(now_ts if now_ts is not None else time.time())
    path = skill_usage_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if not isinstance(data, dict):
            data = {}
        values = data.get(category, [])
        if not isinstance(values, list):
            values = []
        data[category] = (values + [ts])[-30:]
        atomic_json_write(path, data)
    except Exception:
        logger.debug("Could not record skill usage for %s", category, exc_info=True)
```

- [ ] **Step 4: Implement and register `skill_describe()`**

```python
def skill_describe(category: str = None, names: List[str] = None, task_id: str = None) -> str:
    try:
        if not category and not names:
            return tool_error("Provide category or names for skill_describe.", success=False)
        from agent.skill_inventory import load_skill_inventory, record_skill_usage
        inventory = load_skill_inventory()
        wanted_names = set(names or [])
        selected = [
            entry for entry in inventory.entries
            if (category and entry.category == category) or (wanted_names and entry.name in wanted_names)
        ]
        if category and not selected:
            return tool_error(f"Unknown skill category '{category}'.", success=False)
        missing = sorted(wanted_names - {entry.name for entry in selected})
        if missing:
            return tool_error(f"Unknown skill name(s): {', '.join(missing)}", success=False)
        for entry in selected:
            record_skill_usage(entry.category)
        return json.dumps({
            "success": True,
            "skills": [{"name": e.name, "category": e.category, "description": e.description} for e in sorted(selected, key=lambda e: (e.category, e.name))],
        }, ensure_ascii=False)
    except Exception as e:
        return tool_error(str(e), success=False)
```

Add `SKILL_DESCRIBE_SCHEMA` and a `registry.register(name="skill_describe", toolset="skills", ...)` block next to `skills_list` and `skill_view`.

- [ ] **Step 5: Record usage from `skill_view()`**

After resolving `skill_md` and category in `skill_view()`, add:

```python
try:
    from agent.skill_inventory import record_skill_usage
    record_skill_usage(_get_category_from_path(skill_md) or "general")
except Exception:
    logger.debug("Could not record skill_view usage for %s", name, exc_info=True)
```

- [ ] **Step 6: Run skills tool tests**

Run: `pytest tests/tools/test_skills_tool.py tests/tools/test_skill_view_path_check.py tests/tools/test_skill_view_traversal.py -q`

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

```bash
git add agent/skill_inventory.py tools/skills_tool.py tests/tools/test_skills_tool.py
git commit -m "feat: add skill describe tool"
```

---

### Task 4: Nudge Signal State And Pure Helpers

**Files:**
- Modify: `run_agent.py:1607-1613`
- Test: `tests/run_agent/test_run_agent.py`

- [ ] **Step 1: Write helper tests**

```python
def test_skill_nudge_signature_for_terminal_command(agent):
    assert agent._skill_nudge_arg_signature("terminal", {"command": "git status --short"}) == "git status"
    assert agent._skill_nudge_arg_signature("terminal", {"command": "python -m pytest"}) == "python"

def test_explicit_user_signal_zh_phrase(agent):
    agent._nudge_signal_config = {"user_phrases": ["记一下"]}
    assert agent._skill_nudge_user_signals("这个坑记一下") == {"explicit_user_signal"}
```

- [ ] **Step 2: Run helper tests and verify failure**

Run: `pytest tests/run_agent/test_run_agent.py::test_skill_nudge_signature_for_terminal_command tests/run_agent/test_run_agent.py::test_explicit_user_signal_zh_phrase -q`

Expected: FAIL because helper methods are missing.

- [ ] **Step 3: Add nudge config and state in `AIAgent.__init__`**

```python
self._skill_nudge_interval = 10
self._nudge_signals_enabled = False
self._nudge_disabled = os.getenv("HERMES_SKILL_NUDGE_DISABLE", "").lower() in ("1", "true", "yes", "on")
self._nudge_signal_config = {
    "repeated_pattern_threshold": 3,
    "novel_cli_window_days": 30,
    "common_cli_suppressions": {"git", "python", "python3", "node", "npm", "pnpm", "uv", "pytest", "rg", "sed", "cat", "ls", "mkdir"},
    "user_phrases": ["next time", "remember", "from now on", "记一下", "下次", "以后"],
    "error_repeat_threshold": 2,
}
self._tool_call_history = deque(maxlen=10)
self._error_history = deque(maxlen=10)
self._repeated_error_hashes = set()
self._nudge_signals = set()
self._known_clis = self._load_skill_known_clis()
```

Read overrides from `_agent_cfg.get("skills", {})` and nested `nudge_signals` without changing the current fallback interval unless config says so.

- [ ] **Step 4: Add helper methods on `AIAgent`**

```python
def _skill_nudge_arg_signature(self, tool_name: str, args: dict) -> str | None:
    if tool_name in ("terminal", "process"):
        command = str(args.get("command") or args.get("cmd") or "").strip()
        parts = command.split()
        if not parts:
            return None
        binary = os.path.basename(parts[0])
        if binary == "git" and len(parts) > 1:
            return f"git {parts[1]}"
        return binary
    if tool_name in ("read_file", "write_file", "edit_file"):
        path = str(args.get("path") or args.get("file_path") or "").strip()
        return str(Path(path).parent) if path else None
    if tool_name in ("web_search", "web_extract"):
        value = str(args.get("url") or args.get("query") or "").strip()
        return value.split("/", 3)[2] if value.startswith(("http://", "https://")) else value[:40]
    return None

def _skill_nudge_user_signals(self, original_user_message: str) -> set[str]:
    text = (original_user_message or "").lower()
    phrases = self._nudge_signal_config.get("user_phrases") or []
    return {"explicit_user_signal"} if any(str(p).lower() in text for p in phrases) else set()
```

- [ ] **Step 5: Run helper tests**

Run: `pytest tests/run_agent/test_run_agent.py::test_skill_nudge_signature_for_terminal_command tests/run_agent/test_run_agent.py::test_explicit_user_signal_zh_phrase -q`

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

```bash
git add run_agent.py tests/run_agent/test_run_agent.py
git commit -m "feat: add skill nudge signal helpers"
```

---

### Task 5: Signal Evaluation, Gating, And Disable Command

**Files:**
- Modify: `run_agent.py:3018-3050`, `run_agent.py:9295-9299`, `run_agent.py:12176-12204`
- Modify: `cli.py:5817-5819`, `tui_gateway/server.py:3753-3865`
- Test: `tests/run_agent/test_run_agent.py`

- [ ] **Step 1: Write signal evaluation tests**

```python
def test_repeated_tool_pattern_signal(agent):
    agent._nudge_signals_enabled = True
    for _ in range(3):
        agent._evaluate_skill_nudge_signals([{"name": "terminal", "arguments": json.dumps({"command": "gh pr view 123"}), "result": "ok"}])
    assert "repeated_tool_pattern" in agent._nudge_signals

def test_common_cli_does_not_fire_novel_signal(agent):
    agent._nudge_signals_enabled = True
    agent._evaluate_skill_nudge_signals([{"name": "terminal", "arguments": json.dumps({"command": "git status"}), "result": "ok"}])
    assert "novel_cli" not in agent._nudge_signals

def test_session_disable_suppresses_skill_review(agent):
    agent.valid_tool_names.add("skill_manage")
    agent._nudge_disabled = True
    agent._nudge_signals = {"explicit_user_signal"}
    assert agent._should_run_skill_review() is False
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/run_agent/test_run_agent.py::test_repeated_tool_pattern_signal tests/run_agent/test_run_agent.py::test_common_cli_does_not_fire_novel_signal tests/run_agent/test_run_agent.py::test_session_disable_suppresses_skill_review -q`

Expected: FAIL because evaluation/gating methods are missing.

- [ ] **Step 3: Implement `_evaluate_skill_nudge_signals()`**

```python
def _evaluate_skill_nudge_signals(self, prev_tools: list[dict]) -> set[str]:
    if not self._nudge_signals_enabled or self._nudge_disabled:
        return set()
    fired: set[str] = set()
    for item in prev_tools or []:
        name = item.get("name") or ""
        args = item.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        args = args if isinstance(args, dict) else {}
        sig = self._skill_nudge_arg_signature(name, args)
        if sig:
            self._tool_call_history.append((name, sig))
            threshold = int(self._nudge_signal_config.get("repeated_pattern_threshold", 3))
            if Counter(self._tool_call_history)[(name, sig)] >= threshold:
                fired.add("repeated_tool_pattern")
        if name in ("terminal", "process"):
            fired.update(self._evaluate_novel_cli_signal(args, item.get("result")))
        fired.update(self._evaluate_error_resolution_signal(name, item.get("result")))
    self._nudge_signals.update(fired)
    return fired
```

- [ ] **Step 4: Implement known CLI persistence and review gating**

```python
def _should_run_skill_review(self) -> tuple[bool, set[str]]:
    if "skill_manage" not in self.valid_tool_names or self._nudge_disabled:
        return False, set()
    if self._nudge_signals:
        fired = set(self._nudge_signals)
        self._nudge_signals.clear()
        self._iters_since_skill = 0
        return True, fired
    if self._skill_nudge_interval > 0 and self._iters_since_skill >= self._skill_nudge_interval:
        self._iters_since_skill = 0
        return True, {"interval_fallback"}
    return False, set()
```

Persist `.skill_known_clis.json` best-effort with `atomic_json_write`; corrupted files return an empty dict and never crash the run.

- [ ] **Step 5: Wire evaluation into the run loop**

At `run_agent.py:9295-9299`:

```python
if self._skill_nudge_interval > 0 and "skill_manage" in self.valid_tool_names:
    self._iters_since_skill += 1
if prev_tools:
    self._evaluate_skill_nudge_signals(prev_tools)
```

At turn start, once `original_user_message` is available:

```python
if self._nudge_signals_enabled and not self._nudge_disabled:
    self._nudge_signals.update(self._skill_nudge_user_signals(original_user_message))
```

At `run_agent.py:12176-12204`:

```python
_should_review_skills, _skill_review_signals = self._should_run_skill_review()
```

- [ ] **Step 6: Add review context**

Extend `_spawn_background_review()` with `skill_nudge_signals: set[str] | None = None` and append:

```python
if review_skills and skill_nudge_signals:
    prompt += "\n\nSkill nudge signals this turn: " + ", ".join(sorted(skill_nudge_signals))
```

Pass `_skill_review_signals` when spawning the background review.

- [ ] **Step 7: Implement `/skills nudge off` side effects**

In CLI command handling before `_handle_skills_command()`, add:

```python
if cmd.strip().lower() == "/skills nudge off":
    if self.agent:
        self.agent._nudge_disabled = True
    self.console.print("Skill nudges disabled for this session.")
    return True
```

In the TUI gateway slash side-effect mirror, add:

```python
if command.strip().lower() == "/skills nudge off":
    agent = session.get("agent")
    if agent is not None:
        setattr(agent, "_nudge_disabled", True)
    session["skill_nudge_disabled"] = True
    return "Skill nudges disabled for this session."
```

- [ ] **Step 8: Run run-agent tests**

Run: `pytest tests/run_agent/test_run_agent.py -q`

Expected: PASS.

- [ ] **Step 9: Commit Task 5**

```bash
git add run_agent.py cli.py tui_gateway/server.py tests/run_agent/test_run_agent.py
git commit -m "feat: trigger skill nudges from reusable-workflow signals"
```

---

### Task 6: Config Example, Integration Coverage, And Final Verification

**Files:**
- Modify: `cli-config.yaml.example:480-520`
- Modify: `tests/agent/test_prompt_builder.py`
- Modify: `tests/tools/test_skills_tool.py`
- Modify: `tests/run_agent/test_run_agent.py`

- [ ] **Step 1: Update `cli-config.yaml.example`**

Use this exact skills section shape:

```yaml
skills:
  creation_nudge_interval: 15
  index_v2: false
  index_token_budget: 2000
  nudge_signals:
    enabled: false
    repeated_pattern_threshold: 3
    novel_cli_window_days: 30
    common_cli_suppressions:
      - git
      - python
      - python3
      - node
      - npm
      - pnpm
      - uv
      - pytest
      - rg
      - sed
      - cat
      - ls
      - mkdir
    user_phrases:
      - "next time"
      - "remember"
      - "from now on"
      - "记一下"
      - "下次"
      - "以后"
    error_repeat_threshold: 2
```

- [ ] **Step 2: Add end-to-end prompt reachability test**

```python
def test_v2_prompt_keeps_all_skills_reachable_via_describe(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text("skills:\n  index_v2: true\n  index_token_budget: 2000\n", encoding="utf-8")
    for i in range(100):
        d = tmp_path / "skills" / f"cat{i // 10}" / f"skill{i}"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\nname: skill{i}\ndescription: Desc {i}\n---\nBody", encoding="utf-8")

    prompt = build_skills_system_prompt()
    assert len(prompt) // 4 <= 2400

    from tools.skills_tool import skill_describe
    described = json.loads(skill_describe(category="cat9"))
    assert {s["name"] for s in described["skills"]} == {f"skill{i}" for i in range(90, 100)}
```

- [ ] **Step 3: Run focused verification**

Run: `pytest tests/agent/test_prompt_builder.py tests/tools/test_skills_tool.py tests/run_agent/test_run_agent.py -q`

Expected: PASS.

- [ ] **Step 4: Run import smoke checks**

Run: `python -m pytest tests/test_plugin_skills.py tests/tools/test_registry.py -q`

Expected: PASS. These catch accidental registry/import cycles.

- [ ] **Step 5: Inspect prompt size manually**

Run:

```bash
python - <<'PY'
from agent.prompt_builder import build_skills_system_prompt
p = build_skills_system_prompt()
print(len(p), len(p)//4)
print(p.splitlines()[0] if p else "empty")
PY
```

Expected with default config: v1 output remains available. With `skills.index_v2: true` in a temporary `HERMES_HOME`, the first line is `## Skills` and estimated tokens stay near the configured budget.

- [ ] **Step 6: Commit Task 6**

```bash
git add cli-config.yaml.example tests/agent/test_prompt_builder.py tests/tools/test_skills_tool.py tests/run_agent/test_run_agent.py
git commit -m "test: cover skills prompt budget rollout"
```

---

## Self-Review Checklist

- Spec coverage: Tasks 1-3 cover the two-tier index, `priority: critical`, `skill_describe`, budget folding, usage data, cache invalidation, and config. Tasks 4-5 cover S1-S4 scaffolding, gating, fallback interval, disable mechanisms, and background review context. Task 6 covers config docs and integration verification.
- Prompt-cache stability: v2 ranking uses a day-level usage epoch, not user-message content. Signal nudges do not affect system prompt rendering.
- Backward compatibility: `skills.index_v2` and `skills.nudge_signals.enabled` default to `false`; v1 rendering and the old interval fallback remain.
- Test coverage: Each changed behavior has a failing test before implementation, plus focused regression and import-cycle checks.
