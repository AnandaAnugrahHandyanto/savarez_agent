"""Prompt helpers for plan-first hard-task orchestration.

This module is intentionally pure: it does not spawn workers or call external
CLIs. Slash commands can use it to queue an execution-ready prompt into the
normal Hermes loop, preserving existing tool approval, model routing, and
platform behavior.
"""

from __future__ import annotations

import re

_MAX_SLUG_LEN = 72


def slugify_task(task: str) -> str:
    """Return a stable, filesystem-friendly slug for a task description."""
    words = re.findall(r"[a-z0-9]+", task.lower())
    slug = "-".join(words)[:_MAX_SLUG_LEN].strip("-")
    return slug or "hard-task"


def build_orchestration_prompt(task: str) -> str:
    """Build a prompt that makes Hermes run the hard-task orchestration workflow."""
    task = task.strip()
    slug = slugify_task(task)
    plan_path = f".hermes/plans/{slug}.md"

    return f"""Run this as a hard-task orchestrator mission.

Task:
{task}

Required workflow:
1. Gather prerequisite context first: repo status, relevant files, existing tests, failure logs, and acceptance criteria that can be inferred from the task.
2. Create a plan document at `{plan_path}` before implementation. Do not implement before the plan document exists.
3. The plan must include: refined spec, objectives and scope, acceptance criteria, file map, worker assignments, integration plan, verification commands, risks and assumptions, rollback plan, and checkpoint cadence.
4. Prefer Claude Code Opus as planner when available. Request `claude-opus-4-7[1m]` first, then fall back to `claude-opus-4-7`, `opus[1m]`, then `opus`. Do not claim a model was used unless command output confirms it.
5. Use independent implementation/review workers where useful: Claude/Sonnet workers with `claude-sonnet-4-6` or `claude-sonnet-4-6[1m]`, and a GPT/Hermes worker using `gpt-5.5` where appropriate.
6. For long-running tasks, monitor worker progress with objective signals: git diff, logs, checkpoint notes, test output, and changed files. Do not trust worker self-reports without verifying.
7. Keep diffs minimal and reversible. Do not broaden scope beyond the task.
8. Integrate under the parent Hermes session: inspect final diff, run agreed tests/linters/builds, and verify external side effects yourself.
9. Final report should be short: what changed, what was verified, and any unresolved risk.

Start now by creating `{plan_path}` and then proceed through the workflow without asking for confirmation unless a destructive, paid, credential, or external publishing action is required.
"""
