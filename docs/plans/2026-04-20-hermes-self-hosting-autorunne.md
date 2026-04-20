# Hermes Self-Hosting Autorunne Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Make the current `hermes-agent` repo use a local-first `.autorunne/` memory kernel so Hermes can act as the chat/task entrypoint while Claude/Codex/Hermes share the same project workflow state.

**Architecture:** Add a deterministic bootstrap/sync script that creates and refreshes a `.autorunne/` directory in the repo, seed the repo with shared workflow documents, and wire the existing `AGENTS.md`/Claude entry context to consult that local Autorunne memory before multi-step work. Keep it local-first and git-excluded by default.

**Tech Stack:** Python 3.11, pathlib, json, subprocess, pytest.

---

### Task 1: Add failing tests for workflow bootstrap and snapshot generation

**Objective:** Define the first usable behavior before implementation.

**Files:**
- Create: `tests/scripts/test_autorunne_sync.py`
- Modify: none

**Step 1: Write failing tests**
- bootstrap creates `.autorunne/` core files and `snapshots/latest.json`
- bootstrap adds `.autorunne/` to `.git/info/exclude` only once
- snapshot records repo name, branch, git cleanliness, and key paths

**Step 2: Run test to verify failure**
Run: `source venv/bin/activate && python -m pytest tests/scripts/test_autorunne_sync.py -q`
Expected: FAIL because `scripts/autorunne_sync.py` does not exist yet.

**Step 3: Commit**
Deferred until implementation passes.

### Task 2: Implement deterministic bootstrap/sync script

**Objective:** Provide a real local tool we can run in this repo now.

**Files:**
- Create: `scripts/autorunne_sync.py`
- Test: `tests/scripts/test_autorunne_sync.py`

**Step 1: Implement minimal code to satisfy tests**
- expose helper functions importable from tests
- create missing workflow files only
- refresh `snapshots/latest.json`
- ensure `.git/info/exclude` contains `.autorunne/`
- support CLI usage: `python scripts/autorunne_sync.py --init`

**Step 2: Run targeted tests**
Run: `source venv/bin/activate && python -m pytest tests/scripts/test_autorunne_sync.py -q`
Expected: PASS.

### Task 3: Seed this repo with shared local workflow files

**Objective:** Make the current repo immediately usable through the new workflow.

**Files:**
- Create: `.autorunne/README.md`
- Create: `.autorunne/PROJECT_CONTEXT.md`
- Create: `.autorunne/TASKS.md`
- Create: `.autorunne/DECISIONS.md`
- Create: `.autorunne/SESSION_LOG.md`
- Create: `.autorunne/NEXT_ACTION.md`
- Create: `.autorunne/RULES.md`
- Create: `.autorunne/config.json`
- Create: `.autorunne/agents/common.md`
- Create: `.autorunne/agents/hermes.md`
- Create: `.autorunne/agents/claude-code.md`
- Create: `.autorunne/agents/codex.md`

**Step 1: Seed files with concise, practical content**
- shared truth in common markdown files
- adapter notes for Hermes/Claude/Codex
- initial tasks focused on self-hosting workflow improvements

**Step 2: Run bootstrap script**
Run: `source venv/bin/activate && python scripts/autorunne_sync.py --init`
Expected: workflow tree present, snapshot refreshed, exclude rule installed.

### Task 4: Wire project context to the Autorunne workflow kernel

**Objective:** Ensure future Hermes/Claude sessions know to read `.autorunne/` first.

**Files:**
- Modify: `AGENTS.md`
- Create: `CLAUDE.md`

**Step 1: Patch `AGENTS.md`**
Add a compact section telling agents to consult `.autorunne/README.md`, `NEXT_ACTION.md`, `TASKS.md`, `DECISIONS.md`, and `snapshots/latest.json` before multi-step work.

**Step 2: Add `CLAUDE.md`**
Mirror the shared workflow instructions for Claude Code.

### Task 5: Verify end-to-end usage

**Objective:** Confirm the repo now has a usable self-hosting workflow loop.

**Files:**
- Modify: `.autorunne/SESSION_LOG.md`
- Modify: `.autorunne/NEXT_ACTION.md` (if needed after verification)

**Step 1: Run tests**
Run: `source venv/bin/activate && python -m pytest tests/scripts/test_autorunne_sync.py -q`
Expected: PASS.

**Step 2: Run script manually**
Run: `source venv/bin/activate && python scripts/autorunne_sync.py --init`
Expected: printed summary with workflow root and snapshot path.

**Step 3: Record session result**
Append the bootstrap outcome to `SESSION_LOG.md` and set the next concrete action in `NEXT_ACTION.md`.
