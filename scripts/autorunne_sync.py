from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable

WORKFLOW_ROOT_NAME = ".autorunne"
WORKFLOW_ROOT_DISPLAY = ".autorunne"
CORE_FILE_TEMPLATES: Dict[str, str] = {
    "README.md": """# Autorunne Workspace

This directory is the local-first Autorunne workspace for this repository.

## Read order before multi-step work
1. `NEXT_ACTION.md`
2. `TASKS.md`
3. `DECISIONS.md`
4. `PROJECT_CONTEXT.md`
5. `snapshots/latest.json`

## Update rule
- Put stable project truth in the shared markdown files.
- Put adapter-specific notes in `agents/`.
- Refresh `snapshots/latest.json` with `python scripts/autorunne_sync.py --init` before a new implementation session.
- Keep this directory local-first and excluded from git by default.
""",
    "PROJECT_CONTEXT.md": """# Project Context

- Project: {project_name}
- Role: Hermes Agent open-source codebase
- Current local workflow mode: self-hosting Autorunne under `.autorunne/`
- Primary use now: Hermes is the chat/task entrypoint; Claude/Codex/Hermes share the same project workflow state through this directory.

## Working assumptions
- Python project with large pytest suite
- `AGENTS.md` remains the primary architecture guide
- `.autorunne/` stores project-state memory, not global user preferences
""",
    "TASKS.md": """# Tasks

## In Progress
- [ ] Finish the first self-hosting Autorunne workflow kernel slice for this repo
- [ ] Use Hermes through Autorunne to keep improving Autorunne itself

## Next Candidates
- [ ] Add smarter repo scanning and task refresh heuristics
- [ ] Add export/doctor/adopt style commands once the local kernel loop is stable
- [ ] Add bugfix/session append helpers for faster day-to-day use
""",
    "DECISIONS.md": """# Decisions

## Accepted
- The shared Autorunne project state lives in `.autorunne/`.
- Hermes is the chat/task front desk, not the only memory store.
- Shared project memory must be readable by Hermes, Claude Code, and Codex.
- Keep `.autorunne/` local-first and excluded from git by default via `.git/info/exclude`.
""",
    "SESSION_LOG.md": """# Session Log

- {timestamp}: Initialized the self-hosting Autorunne kernel for this repository.
""",
    "NEXT_ACTION.md": """# Next Action

1. Refresh the workflow snapshot with `python scripts/autorunne_sync.py --init`.
2. Read `TASKS.md`, `DECISIONS.md`, and `snapshots/latest.json`.
3. Use Hermes chat to continue the next highest-value workflow improvement or bugfix.
""",
    "RULES.md": """# Rules

- Do not treat `.autorunne/` as public release output.
- Update shared files only when the information will help the next session resume work faster.
- Put durable project-state truth here; keep user/global preferences in Hermes memory, not this repo.
- Prefer concise, high-signal updates over raw transcript dumps.
""",
    "config.json": """{{
  "workflow_root": ".autorunne",
  "mode": "local-first",
  "shared_agents": ["hermes", "claude-code", "codex"],
  "snapshot_file": ".autorunne/snapshots/latest.json"
}}
""",
    "agents/common.md": """# Shared Agent Workflow Adapter

Before multi-step work:
1. Read `.autorunne/NEXT_ACTION.md`
2. Read `.autorunne/TASKS.md`
3. Read `.autorunne/DECISIONS.md`
4. Read `.autorunne/PROJECT_CONTEXT.md`
5. Read `.autorunne/snapshots/latest.json`

After meaningful work:
- refresh snapshot
- update `TASKS.md`
- append one concise line to `SESSION_LOG.md`
- set the next concrete step in `NEXT_ACTION.md`
""",
    "agents/hermes.md": """# Hermes Adapter

Use Hermes as the chat/task front desk for this repo.
- Start from `.autorunne/agents/common.md`
- Use repo tools to inspect, patch, test, and verify
- After each completed slice, update the shared workflow files so future Hermes sessions can resume immediately
""",
    "agents/claude-code.md": """# Claude Code Adapter

Claude Code should treat `.autorunne/` as the shared project memory layer.
- Read `.autorunne/agents/common.md` first
- Follow shared project truth from the common markdown files
- Do not create a separate parallel project-memory scheme unless explicitly requested
""",
    "agents/codex.md": """# Codex Adapter

Codex should use `.autorunne/` as the project-state memory source.
- Read `.autorunne/agents/common.md` first
- Consult `snapshots/latest.json` before major edits
- Update shared workflow files after verified progress so other agents stay aligned
""",
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def render_template(relative_path: str, project_name: str) -> str:
    template = CORE_FILE_TEMPLATES[relative_path]
    return template.format(project_name=project_name, timestamp=_timestamp())


def workflow_root(repo_root: Path) -> Path:
    return repo_root / WORKFLOW_ROOT_NAME


def ensure_workflow_structure(repo_root: Path) -> list[Path]:
    created: list[Path] = []
    root = workflow_root(repo_root)
    (root / "agents").mkdir(parents=True, exist_ok=True)
    (root / "snapshots").mkdir(parents=True, exist_ok=True)

    for relative_path in CORE_FILE_TEMPLATES:
        path = root / relative_path
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render_template(relative_path, repo_root.name), encoding="utf-8")
            created.append(path)
    return created


def ensure_git_exclude(repo_root: Path) -> Path | None:
    exclude_path = repo_root / ".git" / "info" / "exclude"
    if not exclude_path.exists():
        return None

    existing = exclude_path.read_text(encoding="utf-8")
    lines = [line.rstrip("\n") for line in existing.splitlines()]
    if WORKFLOW_ROOT_DISPLAY not in lines and f"{WORKFLOW_ROOT_DISPLAY}/" not in lines:
        if existing and not existing.endswith("\n"):
            existing += "\n"
        existing += f"{WORKFLOW_ROOT_DISPLAY}/\n"
        exclude_path.write_text(existing, encoding="utf-8")
    return exclude_path


def read_git_branch(repo_root: Path) -> str:
    head_path = repo_root / ".git" / "HEAD"
    if head_path.exists():
        head_text = head_path.read_text(encoding="utf-8").strip()
        if head_text.startswith("ref:"):
            return head_text.rsplit("/", 1)[-1]
        if head_text:
            return head_text[:7]
    return "unknown"


def relative_display(path: Path, repo_root: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def _safe_run(command: Iterable[str], repo_root: Path) -> str:
    try:
        completed = subprocess.run(
            list(command),
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return ""
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    return stdout or stderr


def collect_workflow_files(repo_root: Path) -> list[str]:
    root = workflow_root(repo_root)
    files = [WORKFLOW_ROOT_DISPLAY]
    if not root.exists():
        return files
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files.append(relative_display(path, repo_root))
    snapshot_entry = f"{WORKFLOW_ROOT_DISPLAY}/snapshots/latest.json"
    if snapshot_entry not in files:
        files.append(snapshot_entry)
    return files


def detect_recommended_commands(repo_root: Path) -> list[str]:
    commands: list[str] = []
    if (repo_root / "venv" / "bin" / "activate").exists() and (repo_root / "tests").exists():
        commands.append("source venv/bin/activate && python -m pytest tests/ -q")
    elif (repo_root / "tests").exists():
        commands.append("python -m pytest tests/ -q")
    if (repo_root / "AGENTS.md").exists():
        commands.append("read AGENTS.md before major changes")
    commands.append("python scripts/autorunne_sync.py --init")
    return commands


def collect_snapshot(repo_root: Path) -> dict:
    root = workflow_root(repo_root)
    has_git_repo = (repo_root / ".git").exists()
    git_status = _safe_run(["git", "status", "--short"], repo_root) if has_git_repo else ""
    recent_commit = _safe_run(["git", "log", "-1", "--pretty=%h %s"], repo_root) if has_git_repo else ""
    snapshot = {
        "generated_at": _timestamp(),
        "project_name": repo_root.name,
        "repo_root": str(repo_root.resolve()),
        "workflow_root": WORKFLOW_ROOT_DISPLAY,
        "has_git_repo": has_git_repo,
        "git_branch": read_git_branch(repo_root) if has_git_repo else "none",
        "git_clean": git_status == "",
        "git_status_summary": git_status.splitlines(),
        "recent_commit": recent_commit,
        "paths": {
            "project_context": f"{WORKFLOW_ROOT_DISPLAY}/PROJECT_CONTEXT.md",
            "tasks": f"{WORKFLOW_ROOT_DISPLAY}/TASKS.md",
            "decisions": f"{WORKFLOW_ROOT_DISPLAY}/DECISIONS.md",
            "session_log": f"{WORKFLOW_ROOT_DISPLAY}/SESSION_LOG.md",
            "next_action": f"{WORKFLOW_ROOT_DISPLAY}/NEXT_ACTION.md",
            "rules": f"{WORKFLOW_ROOT_DISPLAY}/RULES.md",
            "agents": f"{WORKFLOW_ROOT_DISPLAY}/agents",
            "snapshot": f"{WORKFLOW_ROOT_DISPLAY}/snapshots/latest.json",
        },
        "workflow_files": collect_workflow_files(repo_root),
        "recommended_commands": detect_recommended_commands(repo_root),
        "repo_markers": {
            "has_agents_md": (repo_root / "AGENTS.md").exists(),
            "has_claude_md": (repo_root / "CLAUDE.md").exists(),
            "has_tests_dir": (repo_root / "tests").exists(),
            "has_pyproject": (repo_root / "pyproject.toml").exists(),
        },
    }
    return snapshot


def write_snapshot(repo_root: Path, snapshot: dict) -> Path:
    snapshot_path = workflow_root(repo_root) / "snapshots" / "latest.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return snapshot_path


def bootstrap_workflow(repo_root: Path) -> dict:
    created = ensure_workflow_structure(repo_root)
    exclude_path = ensure_git_exclude(repo_root)
    snapshot = collect_snapshot(repo_root)
    snapshot_path = write_snapshot(repo_root, snapshot)
    return {
        "repo_root": repo_root,
        "workflow_root": workflow_root(repo_root),
        "created_files": created,
        "exclude_path": exclude_path,
        "snapshot_path": snapshot_path,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap and refresh the local Autorunne kernel")
    parser.add_argument("--root", default=".", help="Repository root to bootstrap")
    parser.add_argument("--init", action="store_true", help="Create missing workflow files and refresh snapshot")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.root).resolve()
    if not args.init:
        print("Autorunne bootstrap is explicit: rerun with --init to create or refresh .autorunne state.")
        return 2
    result = bootstrap_workflow(repo_root)
    print(f"workflow_root={result['workflow_root']}")
    print(f"snapshot_path={result['snapshot_path']}")
    print(f"created_files={len(result['created_files'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
