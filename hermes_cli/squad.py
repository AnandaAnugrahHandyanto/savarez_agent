"""tmux-backed multi-session manager for Hermes CLI.

Inspired by claude-squad's core pattern: keep a lightweight dashboard in one
terminal while each agent runs in an isolated tmux session.  Hermes already has
its own ``--worktree`` mode, so this module composes tmux + ``hermes -w`` rather
than duplicating git-worktree logic in the launcher.
"""

from __future__ import annotations

import curses
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from hermes_constants import get_hermes_home

SQUAD_DIR_NAME = "squad"
STATE_FILE_NAME = "instances.json"
TMUX_PREFIX = "hermes_squad_"
DEFAULT_HISTORY_LIMIT = "20000"


@dataclass
class SquadInstance:
    id: str
    title: str
    tmux_session: str
    cwd: str
    command: str
    created_at: str
    prompt: str | None = None


def _squad_dir() -> Path:
    path = get_hermes_home() / SQUAD_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _state_path() -> Path:
    return _squad_dir() / STATE_FILE_NAME


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-._")
    return slug[:48] or "session"


def _now_id(title: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{timestamp}-{_slug(title).lower()}"


def tmux_session_name(instance_id: str) -> str:
    # tmux treats dots specially in targets; avoid them to make attach/kill stable.
    safe = instance_id.replace(".", "_")
    return f"{TMUX_PREFIX}{safe}"


def load_instances() -> list[SquadInstance]:
    path = _state_path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    instances: list[SquadInstance] = []
    for item in raw if isinstance(raw, list) else []:
        try:
            instances.append(SquadInstance(**item))
        except TypeError:
            continue
    return instances


def save_instances(instances: Iterable[SquadInstance]) -> None:
    path = _state_path()
    data = [asdict(instance) for instance in instances]
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _run_tmux(args: Sequence[str], *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["tmux", *args],
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def ensure_tmux_available() -> None:
    if shutil.which("tmux") is None:
        raise SystemExit("Error: hermes squad requires tmux. Install tmux and try again.")


def tmux_session_exists(session_name: str) -> bool:
    result = _run_tmux(["has-session", "-t", session_name], check=False, capture=True)
    return result.returncode == 0


def prune_dead_instances(instances: list[SquadInstance] | None = None) -> list[SquadInstance]:
    instances = list(load_instances() if instances is None else instances)
    alive = [item for item in instances if tmux_session_exists(item.tmux_session)]
    if len(alive) != len(instances):
        save_instances(alive)
    return alive


def build_hermes_command(*, program: str | None = None, worktree: bool = True, extra_args: Sequence[str] = ()) -> str:
    """Build the shell command run inside each tmux session.

    ``program`` may be a full shell command for advanced users.  The default is
    the currently-running Hermes executable (or ``hermes`` when invoked as a
    module), with ``--worktree`` enabled to mirror claude-squad's isolated
    workspace model.
    """

    if program:
        base = shlex.split(program)
    else:
        executable = Path(sys.argv[0]).name
        base = [sys.argv[0] if executable and executable != "__main__.py" else "hermes"]
    if worktree and "--worktree" not in base and "-w" not in base:
        base.append("--worktree")
    base.extend(extra_args)
    return shlex.join(base)


def create_instance(
    *,
    title: str,
    cwd: str | None = None,
    command: str | None = None,
    prompt: str | None = None,
    attach: bool = False,
) -> SquadInstance:
    ensure_tmux_available()
    cwd_path = str(Path(cwd or os.getcwd()).resolve())
    instance_id = _now_id(title)
    session = tmux_session_name(instance_id)
    command = command or build_hermes_command()

    _run_tmux(["new-session", "-d", "-s", session, "-c", cwd_path, command])
    _run_tmux(["set-option", "-t", session, "history-limit", DEFAULT_HISTORY_LIMIT], check=False)
    _run_tmux(["set-option", "-t", session, "mouse", "on"], check=False)

    if prompt:
        # Give prompt_toolkit a moment to draw the prompt, then inject the first task.
        time.sleep(1.5)
        _run_tmux(["send-keys", "-t", session, prompt, "Enter"], check=False)

    instance = SquadInstance(
        id=instance_id,
        title=title,
        tmux_session=session,
        cwd=cwd_path,
        command=command,
        created_at=datetime.now(timezone.utc).isoformat(),
        prompt=prompt,
    )
    instances = prune_dead_instances()
    instances.append(instance)
    save_instances(instances)

    if attach:
        attach_instance(instance)
    return instance


def capture_preview(instance: SquadInstance, lines: int = 40) -> str:
    if not tmux_session_exists(instance.tmux_session):
        return "<dead tmux session>"
    result = _run_tmux(
        ["capture-pane", "-t", instance.tmux_session, "-p", "-S", f"-{max(lines, 1)}"],
        check=False,
        capture=True,
    )
    if result.returncode != 0:
        return (result.stderr or "<unable to capture pane>").strip()
    return result.stdout.rstrip()


def attach_instance(instance: SquadInstance) -> None:
    ensure_tmux_available()
    if not tmux_session_exists(instance.tmux_session):
        raise SystemExit(f"Error: tmux session is not running: {instance.tmux_session}")
    os.execvp("tmux", ["tmux", "attach-session", "-t", instance.tmux_session])


def kill_instance(instance_id: str) -> bool:
    instances = load_instances()
    kept: list[SquadInstance] = []
    killed = False
    for instance in instances:
        if instance.id == instance_id or instance.title == instance_id or instance.tmux_session == instance_id:
            _run_tmux(["kill-session", "-t", instance.tmux_session], check=False)
            killed = True
        else:
            kept.append(instance)
    save_instances(kept)
    return killed


def reset_instances() -> int:
    instances = load_instances()
    for instance in instances:
        _run_tmux(["kill-session", "-t", instance.tmux_session], check=False)
    save_instances([])
    return len(instances)


def _draw(stdscr, instances: list[SquadInstance], selected: int) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    left_w = max(28, min(44, width // 3))
    stdscr.addnstr(0, 0, "Hermes Squad — n:new  N:new+prompt  Enter:attach  D:kill  r:refresh  q:quit", width - 1, curses.A_BOLD)
    stdscr.hline(1, 0, curses.ACS_HLINE, width)
    stdscr.vline(2, left_w, curses.ACS_VLINE, max(0, height - 4))

    if not instances:
        stdscr.addnstr(3, 2, "No sessions yet. Press n to start one.", left_w - 3)
    for idx, instance in enumerate(instances[: max(0, height - 4)]):
        attr = curses.A_REVERSE if idx == selected else curses.A_NORMAL
        label = f"{idx + 1:>2}. {instance.title}"
        stdscr.addnstr(2 + idx, 1, label, left_w - 2, attr)
        stdscr.addnstr(2 + idx, max(1, left_w - 14), instance.id[:12], 13, attr)

    if instances:
        selected = max(0, min(selected, len(instances) - 1))
        inst = instances[selected]
        header = f"{inst.title}  cwd={inst.cwd}  cmd={inst.command}"
        stdscr.addnstr(2, left_w + 2, header, max(0, width - left_w - 3), curses.A_BOLD)
        preview = capture_preview(inst, max(1, height - 6)).splitlines()
        for row, line in enumerate(preview[: max(0, height - 5)], start=4):
            stdscr.addnstr(row, left_w + 2, line, max(0, width - left_w - 3))
    stdscr.refresh()


def _prompt(stdscr, label: str, default: str = "") -> str:
    height, width = stdscr.getmaxyx()
    curses.echo()
    try:
        stdscr.addnstr(height - 2, 0, " " * (width - 1), width - 1)
        prompt = f"{label}{f' [{default}]' if default else ''}: "
        stdscr.addnstr(height - 2, 0, prompt, width - 1, curses.A_BOLD)
        value = stdscr.getstr(height - 2, min(len(prompt), width - 2), max(1, width - len(prompt) - 2))
        text = value.decode(errors="replace").strip()
        return text or default
    finally:
        curses.noecho()


def _interactive(stdscr, args) -> None:
    curses.curs_set(0)
    stdscr.nodelay(False)
    selected = 0
    instances = prune_dead_instances()
    while True:
        if selected >= len(instances):
            selected = max(0, len(instances) - 1)
        _draw(stdscr, instances, selected)
        key = stdscr.getch()
        if key in (ord("q"), 27):
            return
        if key in (ord("r"),):
            instances = prune_dead_instances()
        elif key in (curses.KEY_DOWN, ord("j")) and instances:
            selected = min(len(instances) - 1, selected + 1)
        elif key in (curses.KEY_UP, ord("k")) and instances:
            selected = max(0, selected - 1)
        elif key in (10, 13, ord("o")) and instances:
            curses.endwin()
            attach_instance(instances[selected])
        elif key in (ord("D"), ord("d")) and instances:
            kill_instance(instances[selected].id)
            instances = prune_dead_instances()
        elif key in (ord("n"), ord("N")):
            curses.curs_set(1)
            title = _prompt(stdscr, "Session name", f"task-{len(instances) + 1}")
            prompt = None
            if key == ord("N"):
                prompt = _prompt(stdscr, "Initial prompt") or None
            curses.curs_set(0)
            command = build_hermes_command(
                program=args.program,
                worktree=not args.no_worktree,
                extra_args=args.hermes_arg or (),
            )
            create_instance(title=title, cwd=args.cwd, command=command, prompt=prompt)
            instances = prune_dead_instances()
            selected = len(instances) - 1


def list_instances() -> int:
    instances = prune_dead_instances()
    if not instances:
        print("No Hermes Squad sessions are running.")
        return 0
    for instance in instances:
        print(f"{instance.id}\t{instance.title}\t{instance.tmux_session}\t{instance.cwd}")
    return 0


def _find_instance(identifier: str) -> SquadInstance | None:
    for instance in prune_dead_instances():
        if identifier in {instance.id, instance.title, instance.tmux_session} or instance.id.startswith(identifier):
            return instance
    return None


def cmd_squad(args) -> int:
    ensure_tmux_available()
    action = getattr(args, "squad_action", None)
    if action in (None, "ui"):
        if not sys.stdin.isatty():
            print("Error: 'hermes squad' requires an interactive terminal. Use 'hermes squad list' in scripts.", file=sys.stderr)
            return 1
        curses.wrapper(_interactive, args)
        return 0
    if action == "list":
        return list_instances()
    if action == "new":
        title = args.name or f"task-{len(prune_dead_instances()) + 1}"
        command = build_hermes_command(program=args.program, worktree=not args.no_worktree, extra_args=args.hermes_arg or ())
        instance = create_instance(title=title, cwd=args.cwd, command=command, prompt=args.prompt, attach=args.attach)
        print(f"Started {instance.title}: {instance.id} ({instance.tmux_session})")
        return 0
    if action == "attach":
        if not args.identifier:
            print("Usage: hermes squad attach <id|title|tmux-session>", file=sys.stderr)
            return 1
        instance = _find_instance(args.identifier)
        if not instance:
            print(f"No Hermes Squad session matches: {args.identifier}", file=sys.stderr)
            return 1
        attach_instance(instance)
        return 0
    if action == "kill":
        if not args.identifier:
            print("Usage: hermes squad kill <id|title|tmux-session>", file=sys.stderr)
            return 1
        if kill_instance(args.identifier):
            print(f"Killed {args.identifier}")
            return 0
        print(f"No Hermes Squad session matches: {args.identifier}", file=sys.stderr)
        return 1
    if action == "reset":
        count = reset_instances()
        print(f"Killed and forgot {count} Hermes Squad session(s).")
        return 0
    print(f"Unknown squad action: {action}", file=sys.stderr)
    return 1
