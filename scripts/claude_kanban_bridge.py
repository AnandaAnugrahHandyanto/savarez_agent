#!/usr/bin/env python3
"""Claude CLI Kanban Bridge.

Dispatches a single Kanban task by spawning ``claude --print`` as a
subprocess, then writes the outcome back to the Kanban DB using the
same ``complete_task`` / ``block_task`` primitives that native Hermes
workers use.

Why this exists
---------------
The Hermes ``anthropic`` provider bills against Anthropic's "extra
usage" bucket, which requires separate API credits.  The ``claude``
CLI bills against the chat-session bucket — the same one a logged-in
claude.ai Max user gets when they open Claude Code.  This bridge lets
Kanban workers run entirely on Max-plan session quota with zero extra
billing setup.

Usage
-----
    python3 scripts/claude_kanban_bridge.py --task <task-id> [--board <slug>]

Environment variables (all optional, injected by the dispatcher)
-----------------------------------------------------------------
HERMES_KANBAN_TASK     Task id (overridden by --task when both present)
HERMES_KANBAN_BOARD    Board slug (overridden by --board when both present)
HERMES_KANBAN_DB       Full path to the DB file (board resolution fallback)
HERMES_REPO_ROOT       Absolute path to the Hermes repo root for artifact
                       paths.  Defaults to /home/josep/.local/share/hermes-agent.

Collaboration gates (respected by the spawned claude process)
-------------------------------------------------------------
  destructive  push  restart  config  billing  security  scope  dirty-stash

The bridge instructs claude to pause at these gates for user confirmation
before proceeding.  It never applies / pops / drops stashes.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_TIMEOUT_SECONDS = 600
_DEFAULT_HERMES_REPO_ROOT = "/home/josep/.local/share/hermes-agent"

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATE = """\
# Kanban task {task_id} — {board} board

**Title:** {title}

**Board:** {board}

**Task ID:** {task_id}

## Task body

{body}

---

## Instructions

You are executing this Kanban task as a claude-cli-bridge worker.

1. **Do the work** described above thoroughly.
2. When finished, emit a concise final summary (3–10 sentences) covering
   what was done, key decisions made, and any caveats or follow-up items.
   The summary is the last thing you write — it becomes the task's official
   completion record in the Kanban board.
3. **Artifact evidence:** if you produce any files or artifacts, write a
   copy or reference to them under:
       ~/.hermes/audits/{audit_ts}-{task_id}/
   Create that directory if it does not exist.  This gives auditors a
   timestamped record tied to the task.

## Collaboration gates — ALWAYS pause for user confirmation before:

- **destructive** — deleting / overwriting data or files irreversibly
- **push** — pushing commits to a remote or publishing a release
- **restart** — restarting services, containers, or system processes
- **config** — changing machine-level or account-level configuration
- **billing** — any action that incurs real-money cost
- **security** — changing credentials, secrets, or access-control rules
- **scope** — starting work that is outside the stated task description
- **dirty-stash** — touching the git stash when the working tree is dirty

## Stash rule — NEVER apply / pop / drop / clear stashes under any
circumstances.  If the working tree has uncommitted changes that block
progress, pause and ask the user.

---

Begin working on the task now.
"""


def _build_prompt(
    task_id: str,
    board: str,
    title: str,
    body: str | None,
    audit_ts: str,
) -> str:
    return _PROMPT_TEMPLATE.format(
        task_id=task_id,
        board=board,
        title=title,
        body=body.strip() if body and body.strip() else "(no body provided)",
        audit_ts=audit_ts,
    )


# ---------------------------------------------------------------------------
# DB helpers — thin wrappers around kanban_db primitives
# ---------------------------------------------------------------------------

def _connect_board(board: str | None):
    """Return a live sqlite3 connection to the board's kanban DB."""
    from hermes_cli import kanban_db as kb  # noqa: PLC0415
    return kb.connect(board=board)


def _fetch_task(conn, task_id: str):
    from hermes_cli import kanban_db as kb  # noqa: PLC0415
    task = kb.get_task(conn, task_id)
    if task is None:
        raise ValueError(f"Task {task_id!r} not found in the kanban DB")
    return task


def _complete(conn, task_id: str, summary: str, metadata: dict) -> None:
    from hermes_cli import kanban_db as kb  # noqa: PLC0415
    kb.complete_task(conn, task_id, summary=summary, metadata=metadata)


def _block(conn, task_id: str, reason: str) -> None:
    from hermes_cli import kanban_db as kb  # noqa: PLC0415
    kb.block_task(conn, task_id, reason=reason)


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def run(task_id: str, board: str | None, *, timeout: int = _DEFAULT_TIMEOUT_SECONDS) -> int:
    """Execute the bridge logic.  Returns 0 on success, non-zero on failure."""
    audit_ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    # --- fetch task ---
    with contextlib.closing(_connect_board(board)) as conn:
        task = _fetch_task(conn, task_id)

    effective_board = board or os.environ.get("HERMES_KANBAN_BOARD", "default")
    prompt = _build_prompt(
        task_id=task_id,
        board=effective_board,
        title=task.title,
        body=task.body,
        audit_ts=audit_ts,
    )

    # --- invoke claude CLI ---
    claude_bin = _find_claude()
    cmd = [claude_bin, "--print", "--output-format", "text"]

    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        _log_error(f"claude subprocess timed out after {timeout}s for task {task_id}")
        stderr_bytes = exc.stderr
        if isinstance(stderr_bytes, bytes):
            stderr_snippet = stderr_bytes.decode("utf-8", errors="replace")[:500]
        else:
            stderr_snippet = (stderr_bytes or "")[:500]
        with contextlib.closing(_connect_board(board)) as conn:
            _block(
                conn,
                task_id,
                reason=(
                    f"bridge-error: claude subprocess timed out after {timeout}s. "
                    f"stderr: {stderr_snippet}"
                ),
            )
        return 1
    except FileNotFoundError:
        _log_error("'claude' CLI not found on PATH. Install Claude Code to use this bridge.")
        with contextlib.closing(_connect_board(board)) as conn:
            _block(
                conn,
                task_id,
                reason="bridge-error: 'claude' CLI not found on PATH",
            )
        return 1

    stdout = result.stdout or ""
    stderr = result.stderr or ""

    if result.returncode != 0:
        _log_error(
            f"claude exited with code {result.returncode} for task {task_id}. "
            f"stderr: {stderr[:500]}"
        )
        with contextlib.closing(_connect_board(board)) as conn:
            _block(
                conn,
                task_id,
                reason=(
                    f"bridge-error: claude exited with code {result.returncode}. "
                    f"stderr: {stderr[:500]}"
                ),
            )
        return result.returncode

    # --- success path ---
    summary = stdout.strip()
    metadata = {
        "executor": "claude-cli-bridge",
        "claude_exit_code": result.returncode,
        "audit_dir": str(
            Path.home() / ".hermes" / "audits" / f"{audit_ts}-{task_id}"
        ),
        "board": effective_board,
    }

    with contextlib.closing(_connect_board(board)) as conn:
        _complete(conn, task_id, summary=summary, metadata=metadata)

    _log_info(f"Task {task_id} completed successfully via claude-cli-bridge.")
    return 0


def _find_claude() -> str:
    """Return the path to the ``claude`` CLI, or raise FileNotFoundError."""
    import shutil  # noqa: PLC0415
    path = shutil.which("claude")
    if path:
        return path
    raise FileNotFoundError("'claude' not found on PATH")


def _log_info(msg: str) -> None:
    print(f"[claude-kanban-bridge] INFO: {msg}", file=sys.stderr)


def _log_error(msg: str) -> None:
    print(f"[claude-kanban-bridge] ERROR: {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dispatch a Kanban task via the claude CLI subprocess bridge.",
    )
    parser.add_argument(
        "--task",
        default=os.environ.get("HERMES_KANBAN_TASK", ""),
        help="Kanban task id (e.g. t_abc123). Also read from HERMES_KANBAN_TASK env.",
    )
    parser.add_argument(
        "--board",
        default=os.environ.get("HERMES_KANBAN_BOARD", None),
        help="Board slug. Also read from HERMES_KANBAN_BOARD env.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.environ.get("HERMES_BRIDGE_TIMEOUT", str(_DEFAULT_TIMEOUT_SECONDS))),
        help=f"Max seconds to wait for claude (default {_DEFAULT_TIMEOUT_SECONDS}).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not args.task:
        print(
            "error: --task / HERMES_KANBAN_TASK is required",
            file=sys.stderr,
        )
        return 2
    return run(args.task, args.board or None, timeout=args.timeout)


if __name__ == "__main__":
    sys.exit(main())
