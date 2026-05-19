"""Project registry and router for Slack/channel -> Kanban routing.

The registry lives at ``$HERMES_HOME/projects.yaml`` and maps durable project
slugs plus gateway channel IDs to Kanban boards, default workspaces, and
profile defaults.  It intentionally stays outside profile prompts/memory so
multi-project routing remains editable, diffable, and project-scoped.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import shlex
from pathlib import Path
from typing import Any, Optional

import yaml

from hermes_constants import display_hermes_home, get_hermes_home
from hermes_cli import kanban_db as kb
from hermes_cli.kanban import _parse_workspace_flag

REGISTRY_VERSION = 1


def registry_path() -> Path:
    return get_hermes_home() / "projects.yaml"


def _empty_registry() -> dict[str, Any]:
    return {"version": REGISTRY_VERSION, "defaults": {}, "projects": {}}


def load_registry(path: Optional[Path] = None) -> dict[str, Any]:
    path = path or registry_path()
    if not path.exists():
        return _empty_registry()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"project registry must be a YAML mapping: {path}")
    data.setdefault("version", REGISTRY_VERSION)
    data.setdefault("defaults", {})
    data.setdefault("projects", {})
    if not isinstance(data["projects"], dict):
        raise ValueError("projects must be a mapping")
    return data


def save_registry(registry: dict[str, Any], path: Optional[Path] = None) -> Path:
    path = path or registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    registry.setdefault("version", REGISTRY_VERSION)
    registry.setdefault("defaults", {})
    registry.setdefault("projects", {})
    path.write_text(yaml.safe_dump(registry, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def resolve_project(key: str, registry: Optional[dict[str, Any]] = None, *, platform: Optional[str] = None) -> tuple[str, dict[str, Any]]:
    """Resolve by project slug, Slack channel id, or Slack channel name."""
    if not key:
        raise KeyError("project key is required")
    registry = registry or load_registry()
    projects = registry.get("projects") or {}
    if key in projects:
        return key, dict(projects[key] or {})

    needle = str(key).lstrip("#").lower()
    for slug, project in projects.items():
        project = project or {}
        slack = project.get("slack") or {}
        candidates = {
            str(slack.get("channel_id") or "").lower(),
            str(slack.get("channel_name") or "").lstrip("#").lower(),
        }
        if platform and platform.lower() != "slack":
            continue
        if needle in candidates:
            return slug, dict(project)
    raise KeyError(f"no project found for {key!r}")


def _workspace_tuple(value: Optional[str]) -> tuple[str, Optional[str], str]:
    value = value or "scratch"
    kind, path = _parse_workspace_flag(value)
    return kind, path, value


def _default_assignee(project: dict[str, Any]) -> Optional[str]:
    for key in ("default_assignee", "default_profile"):
        if project.get(key):
            return str(project[key])
    profiles = project.get("profiles") or {}
    for key in ("orchestrator", "implementer", "researcher"):
        if profiles.get(key):
            return str(profiles[key])
    return None


def _task_title(text: str, override: Optional[str] = None) -> str:
    if override and override.strip():
        return override.strip()
    first = (text or "").strip().splitlines()[0] if (text or "").strip() else "Project-routed task"
    return first[:117] + "…" if len(first) > 120 else first


def _task_body(*, slug: str, project: dict[str, Any], text: str, platform: Optional[str], chat_id: Optional[str], thread_id: Optional[str]) -> str:
    lines: list[str] = [
        f"Project: {project.get('name') or slug}",
        f"Project slug: {slug}",
        f"Board: {project.get('board') or slug}",
    ]
    if project.get("repo"):
        lines.append(f"Repo: {project['repo']}")
    if platform or chat_id or thread_id:
        lines.append(f"Source: platform={platform or ''} chat_id={chat_id or ''} thread_id={thread_id or ''}")
    context = project.get("context") or []
    if context:
        lines += ["", "Project context:"] + [f"- {c}" for c in context]
    lines += ["", "Original request:", text.strip()]
    return "\n".join(lines).rstrip() + "\n"


def add_project(args: argparse.Namespace) -> int:
    registry = load_registry()
    projects = registry.setdefault("projects", {})
    slack: dict[str, Any] = {}
    if args.slack_channel:
        slack["channel_id"] = args.slack_channel
    if args.slack_name:
        slack["channel_name"] = args.slack_name.lstrip("#")
    if args.mention_user:
        slack["mention_user_id"] = args.mention_user
    project: dict[str, Any] = {
        "board": args.board or args.slug,
    }
    if args.name:
        project["name"] = args.name
    if args.repo:
        project["repo"] = str(Path(args.repo).expanduser())
    if args.workspace:
        project["default_workspace"] = args.workspace
    if args.assignee:
        project["default_assignee"] = args.assignee
    if slack:
        project["slack"] = slack
    projects[args.slug] = project
    path = save_registry(registry)
    kb.create_board(project["board"], name=args.name or args.slug, description=f"Project router board for {args.slug}")
    if args.json:
        print(json.dumps({"project": args.slug, "path": str(path), "data": project}, indent=2))
    else:
        print(f"Saved project {args.slug} -> board {project['board']} in {display_hermes_home()}/projects.yaml")
    return 0


def route_project(args: argparse.Namespace) -> int:
    registry = load_registry()
    if args.project:
        slug, project = resolve_project(args.project, registry)
    elif args.chat_id:
        slug, project = resolve_project(args.chat_id, registry, platform=args.platform)
    else:
        raise SystemExit("project route requires --project or --chat-id")

    board = str(project.get("board") or slug)
    kb.create_board(board, name=project.get("name") or slug, description=f"Project router board for {slug}")

    text = " ".join(args.text or []).strip()
    if not text:
        raise SystemExit("project route requires request text")
    assignee = args.assignee or _default_assignee(project)
    workspace_value = args.workspace or project.get("default_workspace") or "scratch"
    workspace_kind, workspace_path, workspace_display = _workspace_tuple(workspace_value)
    title = _task_title(text, args.title)
    body = _task_body(slug=slug, project=project, text=text, platform=args.platform, chat_id=args.chat_id, thread_id=args.thread_id)

    conn = kb.connect(board=board)
    subscribed = False
    try:
        task_id = kb.create_task(
            conn,
            title=title,
            body=body,
            assignee=assignee,
            created_by="project-router",
            workspace_kind=workspace_kind,
            workspace_path=workspace_path,
        )
        if args.platform and args.chat_id:
            kb.add_notify_sub(
                conn,
                task_id=task_id,
                platform=args.platform.lower(),
                chat_id=str(args.chat_id),
                thread_id=args.thread_id,
                user_id=getattr(args, "user_id", None),
            )
            subscribed = True
    finally:
        conn.close()

    result = {
        "task_id": task_id,
        "project": slug,
        "board": board,
        "title": title,
        "assignee": assignee,
        "workspace": workspace_display,
        "subscribed": subscribed,
    }
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Routed {slug} -> {board}/{task_id}")
        print(f"  title: {title}")
        print(f"  assignee: {assignee or '(unassigned)'}")
        print(f"  workspace: {workspace_display}")
        if subscribed:
            print(f"  subscribed: {args.platform}:{args.chat_id}{(':'+args.thread_id) if args.thread_id else ''}")
    return 0


def project_command(args: argparse.Namespace) -> int:
    action = getattr(args, "project_action", None)
    if action in (None, ""):
        print(f"Project registry: {display_hermes_home()}/projects.yaml")
        return 0
    if action in ("path",):
        print(str(registry_path()))
        return 0
    if action in ("list", "ls"):
        reg = load_registry()
        projects = reg.get("projects") or {}
        if args.json:
            print(json.dumps(projects, indent=2))
        else:
            if not projects:
                print(f"No projects yet. Add one with `hermes project add ...` ({display_hermes_home()}/projects.yaml).")
            for slug, project in projects.items():
                slack = (project or {}).get("slack") or {}
                print(f"{slug:20s} board={(project or {}).get('board') or slug:20s} slack={slack.get('channel_id') or '-'} workspace={(project or {}).get('default_workspace') or 'scratch'}")
        return 0
    if action == "show":
        slug, project = resolve_project(args.key, load_registry(), platform="slack")
        if args.json:
            print(json.dumps({"slug": slug, **project}, indent=2))
        else:
            print(yaml.safe_dump({slug: project}, sort_keys=False, allow_unicode=True).rstrip())
        return 0
    if action == "add":
        return add_project(args)
    if action == "route":
        return route_project(args)
    raise SystemExit(f"unknown project action: {action}")


def build_parser(parent_subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    parser = parent_subparsers.add_parser("project", help="Project registry and Slack/channel router")
    sub = parser.add_subparsers(dest="project_action")
    sub.add_parser("path", help="Print projects.yaml path")
    p_list = sub.add_parser("list", aliases=["ls"], help="List registered projects")
    p_list.add_argument("--json", action="store_true")
    p_show = sub.add_parser("show", help="Show a project by slug or Slack channel")
    p_show.add_argument("key")
    p_show.add_argument("--json", action="store_true")
    p_add = sub.add_parser("add", help="Add/update a project mapping")
    p_add.add_argument("slug")
    p_add.add_argument("--board", default=None)
    p_add.add_argument("--name", default=None)
    p_add.add_argument("--repo", default=None)
    p_add.add_argument("--workspace", default="scratch")
    p_add.add_argument("--slack-channel", default=None)
    p_add.add_argument("--slack-name", default=None)
    p_add.add_argument("--assignee", default=None)
    p_add.add_argument("--mention-user", default=None)
    p_add.add_argument("--json", action="store_true")
    p_route = sub.add_parser("route", help="Route request text into the mapped Kanban board")
    p_route.add_argument("text", nargs="*")
    p_route.add_argument("--platform", default="slack")
    p_route.add_argument("--chat-id", default=None)
    p_route.add_argument("--thread-id", default=None)
    p_route.add_argument("--user-id", default=None)
    p_route.add_argument("--project", default=None)
    p_route.add_argument("--assignee", default=None)
    p_route.add_argument("--workspace", default=None)
    p_route.add_argument("--title", default=None)
    p_route.add_argument("--json", action="store_true")
    return parser


def run_slash(command_text: str) -> str:
    argv = shlex.split(command_text or "")
    parser = argparse.ArgumentParser(prog="/project")
    sub = parser.add_subparsers(dest="_root")
    project_parser = build_parser(sub)
    project_parser.set_defaults(func=project_command)
    args = parser.parse_args(["project", *argv])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        project_command(args)
    return buf.getvalue().rstrip()
