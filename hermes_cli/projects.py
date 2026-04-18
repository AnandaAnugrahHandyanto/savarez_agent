"""Project OS CLI helpers for Hermes.

Implements a small local-first project operating system on top of the current
profile-scoped HERMES_HOME. Projects live under:

    <HERMES_HOME>/project-os-v1/projects/<project_id>/

The registry lives at:

    <HERMES_HOME>/project-os-v1/projects/registry.json
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_cli.colors import Colors, color
from hermes_constants import get_hermes_home

_PROJECT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _project_os_root() -> Path:
    return get_hermes_home() / "project-os-v1"


def _projects_root() -> Path:
    return _project_os_root() / "projects"


def _registry_path() -> Path:
    return _projects_root() / "registry.json"


def _detect_owner_profile() -> str:
    home = get_hermes_home().resolve()
    if home.parent.name == "profiles":
        return home.name
    return "default"


def _validate_project_id(project_id: str) -> None:
    if not _PROJECT_ID_RE.match(project_id):
        raise ValueError(
            f"Invalid project id {project_id!r}. Must match [a-z0-9][a-z0-9_-]{{1,63}}"
        )


def _read_registry() -> Dict[str, Any]:
    path = _registry_path()
    if not path.exists():
        return {
            "schema_version": "1",
            "generated_at": _iso_now(),
            "projects": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def _write_registry(payload: Dict[str, Any]) -> None:
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload["generated_at"] = _iso_now()
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _default_pairing_status(now: str) -> Dict[str, Any]:
    return {
        "state": "unpaired",
        "issued_at": None,
        "approved_at": None,
        "revoked_at": None,
        "expires_at": None,
        "device_label": None,
        "code_hint": None,
        "updated_at": now,
    }


def _git_metadata(repo_path: Optional[str]) -> Optional[Dict[str, Any]]:
    if not repo_path:
        return None
    repo = Path(repo_path)
    if not repo.exists():
        raise FileNotFoundError(f"Repo path does not exist: {repo_path}")

    def _run(*args: str) -> str:
        return subprocess.run(args, cwd=repo, capture_output=True, text=True, check=True).stdout.strip()

    commit = _run("/usr/bin/git", "rev-parse", "HEAD")
    short_commit = _run("/usr/bin/git", "rev-parse", "--short", "HEAD")
    branch = _run("/usr/bin/git", "rev-parse", "--abbrev-ref", "HEAD")
    if branch == "HEAD":
        branch = "detached-head"
    dirty = bool(_run("/usr/bin/git", "status", "--short"))

    return {
        "path": str(repo),
        "url": None,
        "branch": branch,
        "commit": commit,
        "short_commit": short_commit,
        "dirty": dirty,
    }


def _project_dir(project_id: str) -> Path:
    return _projects_root() / project_id


def _manifest_path(project_id: str) -> Path:
    return _project_dir(project_id) / "reports" / "manifest.json"


def _status_digest_path(project_id: str) -> Path:
    return _project_dir(project_id) / "reports" / "01-status-digest.md"


def _load_project_from_registry(project_id: str) -> Optional[Dict[str, Any]]:
    payload = _read_registry()
    for project in payload.get("projects", []):
        if project.get("id") == project_id:
            return project
    return None


def _load_manifest(project_id: str) -> Dict[str, Any]:
    path = _manifest_path(project_id)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_project_yaml(project_id: str) -> Dict[str, Any]:
    path = _project_dir(project_id) / "project.yaml"
    if not path.exists():
        return {}
    try:
        import yaml

        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _display_value(value: Any, default: str = "n/a") -> str:
    if value is None:
        return default
    if isinstance(value, bool):
        return str(value).lower()
    text = str(value).strip()
    return text or default


def get_project_details(project_id: str) -> Dict[str, Any]:
    project = _load_project_from_registry(project_id)
    if not project:
        raise FileNotFoundError(f"Project '{project_id}' not found")

    project_dir = _project_dir(project_id)
    project_yaml = _load_project_yaml(project_id)
    manifest = _load_manifest(project_id)
    digest_path = _status_digest_path(project_id)

    pairing_state = "unknown"
    pairing_path = project_dir / "pairing" / "status.json"
    if pairing_path.exists():
        try:
            pairing_payload = json.loads(pairing_path.read_text(encoding="utf-8"))
            pairing_state = pairing_payload.get("state") or "unknown"
        except json.JSONDecodeError:
            pairing_state = "invalid"

    repo_cfg = project_yaml.get("repo") if isinstance(project_yaml.get("repo"), dict) else {}
    repo_path = project.get("repo_path") or repo_cfg.get("path")
    repo_state: Dict[str, Any] = {
        "path": repo_path,
        "branch": repo_cfg.get("branch") if repo_path else None,
        "commit": repo_cfg.get("commit") if repo_path else None,
        "short_commit": None,
        "dirty": repo_cfg.get("dirty") if repo_path else None,
    }
    if repo_state.get("commit"):
        repo_state["short_commit"] = str(repo_state["commit"])[:7]

    repo_error = None
    if repo_path:
        try:
            repo_state = _git_metadata(repo_path)
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            repo_error = str(exc)

    return {
        "project": project,
        "project_dir": project_dir,
        "project_yaml": project_yaml,
        "manifest": manifest,
        "digest_path": digest_path,
        "pairing_state": pairing_state,
        "repo": repo_state,
        "repo_error": repo_error,
    }


def print_project_details(project_id: str) -> None:
    details = get_project_details(project_id)
    project = details["project"]
    project_dir = details["project_dir"]
    manifest = details["manifest"]
    repo = details["repo"]
    digest_path = details["digest_path"]

    print()
    print(color(f"Project: {project['id']}", Colors.BOLD, Colors.CYAN))
    print(f"Name:          {project['name']}")
    print(f"Summary:       {project['summary']}")
    print(f"Status:        {project['status']}")
    print(f"Owner profile: {project['owner_profile']}")
    print(f"Cell path:     {project_dir}")
    print(f"Created:       {_display_value(details['project_yaml'].get('created_at'))}")
    print(f"Updated:       {_display_value(details['project_yaml'].get('updated_at'))}")

    print()
    print(color("Artifacts", Colors.BOLD))
    print(f"Project config:     {project_dir / 'project.yaml'}")
    print(f"Brief:              {project_dir / 'brief.md'}")
    print(f"Executive summary:  {project_dir / 'reports' / '00-executive-summary.md'}")
    if digest_path.exists():
        digest_label = str(digest_path)
    else:
        digest_label = f"{digest_path} (not generated yet)"
    print(f"Status digest:      {digest_label}")
    print(f"Manifest:           {_manifest_path(project['id'])}")
    print(f"Manifest artifacts: {len(manifest.get('artifacts', []))}")
    print(f"Latest workflow:    {_display_value(manifest.get('workflow'))}")
    print(f"Pairing state:      {_display_value(details['pairing_state'], default='unknown')}")

    print()
    print(color("Repository", Colors.BOLD))
    print(f"Path:   {_display_value(repo.get('path'))}")
    print(f"Branch: {_display_value(repo.get('branch'))}")
    print(f"Commit: {_display_value(repo.get('short_commit') or repo.get('commit'))}")
    print(f"Dirty:  {_display_value(repo.get('dirty'))}")
    if details["repo_error"]:
        print(f"Repo check: {details['repo_error']}")
    print()


def init_project(project_id: str, name: str, summary: str, repo_path: Optional[str] = None) -> Path:
    _validate_project_id(project_id)
    if not name.strip():
        raise ValueError("Project name is required")
    if not summary.strip():
        raise ValueError("Project summary is required")

    project_dir = _project_dir(project_id)
    if project_dir.exists():
        raise FileExistsError(f"Project '{project_id}' already exists at {project_dir}")

    repo = _git_metadata(repo_path)
    now = _iso_now()
    owner_profile = _detect_owner_profile()
    config_dir = _project_os_root() / "config"

    project_yaml_lines = [
        'schema_version: "1"',
        f'id: {project_id}',
        f'name: {name}',
        f'summary: {summary}',
        'status: active',
        'priority: medium',
        f'owner_profile: {owner_profile}',
        f'project_root: {project_dir}',
        'workspace_contracts:',
        f'  path_policies: {config_dir / "path-policies.yaml"}',
        f'  modules: {config_dir / "modules.yaml"}',
        f'  modules_lock: {config_dir / "modules.lock.yaml"}',
        'repo:',
    ]
    if repo:
        project_yaml_lines.extend([
            f"  path: {repo['path']}",
            '  url: null',
            f"  branch: {repo['branch']}",
            f"  commit: {repo['commit']}",
            f"  dirty: {'true' if repo['dirty'] else 'false'}",
        ])
    else:
        project_yaml_lines.extend([
            '  path: null',
            '  url: null',
            '  branch: null',
            '  commit: null',
            '  dirty: false',
        ])
    project_yaml_lines.extend([
        'artifacts:',
        '  reports_dir: reports',
        '  tasks_dir: tasks',
        '  checkpoints_dir: checkpoints',
        '  logs_dir: logs',
        '  assets_dir: assets',
        '  approvals_file: approvals.jsonl',
        '  sync_dir: sync',
        '  pairing_dir: pairing',
        'sync:',
        '  mode: local-only',
        '  path_policies:',
        '    - path: repo',
        '      policy: git-owned',
        '    - path: reports',
        '      policy: mirror',
        '    - path: checkpoints',
        '      policy: mirror',
        '    - path: project.yaml',
        '      policy: merge',
        '    - path: memories.jsonl',
        '      policy: append-only',
        'cloudflare:',
        '  enabled: false',
        '  workspace_id: null',
        '  remote_mode: null',
        f'created_at: {now}',
        f'updated_at: {now}',
    ])
    _write(project_dir / "project.yaml", "\n".join(project_yaml_lines) + "\n")
    _write(project_dir / "brief.md", f"# {name}\n\n{summary}\n")
    _write(project_dir / "tasks" / "README.md", "# Tasks\n\nTrack next actions and operator-owned work here.\n")
    _write(project_dir / "tasks" / "next-actions.md", "# Next Actions\n\n- Review latest project digest\n- Decide whether any lightweight report artifacts should be approved\n- Refresh sync projection before mobile/operator review\n")
    _write(project_dir / "checkpoints" / "README.md", "# Checkpoints\n\nStore resumable state snapshots here.\n")
    _write(project_dir / "logs" / "README.md", "# Logs\n\nStore operator logs, run notes, and workflow outputs here.\n")
    _write(project_dir / "assets" / "README.md", "# Assets\n\nStore diagrams, screenshots, and auxiliary artifacts here.\n")
    _write(project_dir / "sync" / "README.md", "# Sync\n\nGenerated project-aware sync manifests live here.\n")
    _write(project_dir / "approvals.jsonl", "")
    _write(project_dir / "pairing" / "status.json", json.dumps(_default_pairing_status(now), indent=2) + "\n")

    short_commit = repo.get("short_commit") if repo else None
    summary_body = (
        f"# Executive Summary\n\n"
        f"Project: {name}\n"
        f"Status: active\n"
        f"Updated: {now}\n\n"
        f"## What this project is\n{summary}\n\n"
        f"## Current state\n"
        f"- Phase: kickoff\n"
        f"- Primary objective: establish a canonical Hermes Project OS cell\n"
        f"- Biggest risk: artifact drift before UI integration exists\n"
        f"- Next operator action: connect this project to Pan project views\n\n"
        f"## Evidence\n"
        f"- Repo path: {repo['path'] if repo else 'n/a'}\n"
        f"- Commit: {short_commit or 'n/a'}\n"
        f"- Generated from: hermes project init\n"
    )
    _write(project_dir / "reports" / "00-executive-summary.md", summary_body)

    manifest = {
        "project_id": project_id,
        "generated_at": now,
        "workflow": "project-kickoff",
        "artifacts": [
            "project.yaml",
            "brief.md",
            "tasks/README.md",
            "tasks/next-actions.md",
            "reports/00-executive-summary.md",
            "reports/manifest.json",
            "checkpoints/README.md",
            "logs/README.md",
            "assets/README.md",
            "approvals.jsonl",
            "pairing/status.json",
        ],
    }
    _write(_manifest_path(project_id), json.dumps(manifest, indent=2) + "\n")

    payload = _read_registry()
    payload.setdefault("projects", []).append({
        "id": project_id,
        "name": name,
        "status": "active",
        "owner_profile": owner_profile,
        "path": str(project_dir),
        "repo_path": repo.get("path") if repo else None,
        "summary": summary,
    })
    _write_registry(payload)
    return project_dir


def list_projects() -> List[Dict[str, Any]]:
    return list(_read_registry().get("projects", []))


def generate_status_digest(project_id: str) -> Path:
    project = _load_project_from_registry(project_id)
    if not project:
        raise FileNotFoundError(f"Project '{project_id}' not found")

    project_yaml_path = _project_dir(project_id) / "project.yaml"
    if not project_yaml_path.exists():
        raise FileNotFoundError(f"Missing project.yaml for '{project_id}'")
    project_yaml = project_yaml_path.read_text(encoding="utf-8")

    repo_path = project.get("repo_path")
    repo_state = {"path": repo_path or "n/a", "branch": "n/a", "commit": "n/a", "dirty": "n/a"}
    if repo_path:
        repo = _git_metadata(repo_path)
        if repo:
            repo_state = {
                "path": repo["path"],
                "branch": repo["branch"],
                "commit": repo["commit"],
                "dirty": str(repo["dirty"]).lower(),
            }

    now = _iso_now()
    body = (
        f"# Status Digest\n\n"
        f"Updated: {now}\n\n"
        f"## Current status\n"
        f"- Project: {project['name']}\n"
        f"- Status: {project['status']}\n"
        f"- Owner profile: {project['owner_profile']}\n\n"
        f"## Repo state\n"
        f"- Path: {repo_state['path']}\n"
        f"- Branch: {repo_state['branch']}\n"
        f"- Commit: {repo_state['commit']}\n"
        f"- Dirty: {repo_state['dirty']}\n\n"
        f"## Open work\n"
        f"- Connect project cell to Pan UI project routes\n"
        f"- Promote owner workflows into installed skills after prototype review\n\n"
        f"## Risks / blockers\n"
        f"- UI integration may still be incomplete for this profile\n"
        f"- Cloud sync intentionally not enabled\n\n"
        f"## Recommended next actions\n"
        f"1. Build or verify Pan project routes\n"
        f"2. Review project.yaml for completeness\n"
        f"3. Generate richer project docs if the repo is ready\n"
    )
    digest_path = _status_digest_path(project_id)
    _write(digest_path, body)

    manifest_path = _manifest_path(project_id)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if "reports/01-status-digest.md" not in manifest.get("artifacts", []):
        manifest["artifacts"].append("reports/01-status-digest.md")
    manifest["generated_at"] = now
    _write(manifest_path, json.dumps(manifest, indent=2) + "\n")
    return digest_path


def project_command(args) -> int:
    action = getattr(args, "project_action", None)

    if action is None or action == "list":
        projects = list_projects()
        if not projects:
            print(color("No projects found. Create one with 'hermes project init ...'", Colors.DIM))
            return 0

        print()
        print(f" {'Project':<18} {'Status':<10} {'Profile':<16} Summary")
        print(f" {'─'*17}  {'─'*9}  {'─'*15}  {'─'*40}")
        for project in projects:
            print(
                f" {project['id']:<18} {project['status']:<10} {project['owner_profile']:<16} "
                f"{project['summary'][:80]}"
            )
        print()
        return 0

    if action == "init":
        try:
            project_dir = init_project(
                project_id=args.project_id,
                name=args.name,
                summary=args.summary,
                repo_path=getattr(args, "repo_path", None),
            )
        except (ValueError, FileExistsError, FileNotFoundError, subprocess.CalledProcessError) as exc:
            print(color(f"Error: {exc}", Colors.RED))
            return 1
        print(color(f"Created project cell: {project_dir}", Colors.GREEN))
        return 0

    if action == "show":
        try:
            print_project_details(args.project_id)
        except FileNotFoundError as exc:
            print(color(f"Error: {exc}", Colors.RED))
            return 1
        return 0

    if action in {"digest", "status"}:
        try:
            digest_path = generate_status_digest(args.project_id)
            project = _load_project_from_registry(args.project_id)
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            print(color(f"Error: {exc}", Colors.RED))
            return 1
        print(color(f"Updated status digest: {digest_path}", Colors.GREEN))
        if project:
            print(f"Project: {project['name']}")
            print(f"Profile: {project['owner_profile']}")
            print(f"Path:    {project['path']}")
        return 0

    print(color(f"Unknown project action: {action}", Colors.RED))
    return 1
