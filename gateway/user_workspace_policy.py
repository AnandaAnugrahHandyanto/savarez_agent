"""Per-user workspace policy for gateway sessions.

Provides a generic way to confine non-owner gateway users to dedicated
workspace directories while letting trusted owner IDs retain full access.

Current behavior:
  - policy is opt-in via ``user_workspaces.enabled`` in config.yaml
  - supports platform scoping (default: Discord only)
  - owner IDs bypass restrictions
  - restricted users get a dedicated workspace tree under ``base_dir``
  - restricted users can be blocked from ``terminal`` / ``execute_code``
  - file/search tools are confined to that workspace tree
"""

from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


_PATCH_PATH_RE = re.compile(
    r"^\*\*\* (?:Add|Update|Delete) File: (.+)$",
    re.MULTILINE,
)
_PATCH_MOVE_RE = re.compile(r"^\*\*\* Move to: (.+)$", re.MULTILINE)

_POLICY_LOCK = threading.Lock()
_POLICY_BY_TASK: dict[str, "UserWorkspacePolicy"] = {}


@dataclass(frozen=True)
class UserWorkspacePolicy:
    enabled: bool
    restricted: bool
    is_owner: bool
    platform: str
    user_id: str
    user_name: str
    base_dir: str
    user_dir: str
    workspace_dir: str
    outputs_dir: str
    venv_dir: str
    tmp_dir: str
    allow_terminal: bool
    allow_execute_code: bool


def _load_config() -> dict[str, Any]:
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
        return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


def _cfg_section() -> dict[str, Any]:
    cfg = _load_config()
    raw = cfg.get("user_workspaces")
    return raw if isinstance(raw, dict) else {}


def _string_set(value: Any) -> set[str]:
    if isinstance(value, str):
        return {part.strip() for part in value.split(",") if part.strip()}
    if isinstance(value, (list, tuple, set)):
        return {str(part).strip() for part in value if str(part).strip()}
    return set()


def _bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _safe_slug(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", (value or "").strip())
    cleaned = cleaned.strip("-._")
    return cleaned or fallback


def _default_base_dir() -> str:
    try:
        from hermes_constants import get_hermes_home

        return str(get_hermes_home() / "user-workspaces")
    except Exception:
        return os.path.expanduser("~/.hermes/user-workspaces")


def _is_isolated_terminal_backend() -> bool:
    env_type = os.getenv("TERMINAL_ENV", "local").strip().lower()
    return env_type in {"docker", "modal", "vercel_sandbox", "daytona", "singularity"}


def _ensure_workspace_layout(policy: UserWorkspacePolicy) -> None:
    for path in (
        policy.base_dir,
        policy.user_dir,
        policy.workspace_dir,
        policy.outputs_dir,
        policy.venv_dir,
        policy.tmp_dir,
    ):
        Path(path).mkdir(parents=True, exist_ok=True)


def resolve_policy_for_source(source: Any) -> Optional[UserWorkspacePolicy]:
    section = _cfg_section()
    if not _bool(section.get("enabled"), False):
        return None

    platform = str(getattr(getattr(source, "platform", None), "value", "") or "").lower()
    user_id = str(getattr(source, "user_id", "") or "").strip()
    if not platform or not user_id:
        return None

    platforms = _string_set(section.get("platforms") or ["discord"])
    if platforms and platform not in platforms:
        return None

    owner_ids = _string_set(section.get("owner_user_ids"))
    trusted_ids = _string_set(section.get("trusted_user_ids"))
    is_owner = user_id in owner_ids
    is_trusted = is_owner or user_id in trusted_ids
    restricted = not is_trusted and _bool(section.get("restricted_by_default"), True)

    base_dir = os.path.realpath(
        os.path.expanduser(str(section.get("base_dir") or _default_base_dir()))
    )
    user_name = str(getattr(source, "user_name", "") or "").strip()
    user_slug = _safe_slug(user_name, f"user-{user_id}")
    user_dir = os.path.join(base_dir, platform, f"{user_slug}-{user_id}")
    workspace_dir = os.path.join(user_dir, "workspace")
    outputs_dir = os.path.join(user_dir, "outputs")
    venv_dir = os.path.join(user_dir, ".venv")
    tmp_dir = os.path.join(user_dir, "tmp")

    allow_terminal = is_trusted or (
        _bool(section.get("allow_restricted_terminal"), False)
        and _is_isolated_terminal_backend()
    )
    allow_execute_code = is_trusted or (
        _bool(section.get("allow_restricted_execute_code"), False)
        and _is_isolated_terminal_backend()
    )

    policy = UserWorkspacePolicy(
        enabled=True,
        restricted=restricted,
        is_owner=is_owner,
        platform=platform,
        user_id=user_id,
        user_name=user_name,
        base_dir=base_dir,
        user_dir=user_dir,
        workspace_dir=workspace_dir,
        outputs_dir=outputs_dir,
        venv_dir=venv_dir,
        tmp_dir=tmp_dir,
        allow_terminal=allow_terminal,
        allow_execute_code=allow_execute_code,
    )
    if restricted or _bool(section.get("create_owner_workspace"), False):
        _ensure_workspace_layout(policy)
    return policy


def apply_policy_to_task(task_id: str, source: Any) -> Optional[UserWorkspacePolicy]:
    if not task_id:
        return None
    policy = resolve_policy_for_source(source)
    if policy is None:
        return None
    with _POLICY_LOCK:
        _POLICY_BY_TASK[task_id] = policy
    if policy.restricted:
        try:
            from tools.terminal_tool import register_task_env_overrides

            register_task_env_overrides(task_id, {"cwd": policy.workspace_dir})
        except Exception:
            pass
    return policy


def get_policy_for_task(task_id: str) -> Optional[UserWorkspacePolicy]:
    if not task_id:
        return None
    with _POLICY_LOCK:
        return _POLICY_BY_TASK.get(task_id)


def resolve_task_cwd(task_id: str = "", fallback: Optional[str] = None) -> str:
    policy = get_policy_for_task(task_id)
    if policy and policy.restricted:
        return policy.workspace_dir

    try:
        from tools.terminal_tool import _task_env_overrides

        override = _task_env_overrides.get(task_id or "", {})
        cwd = override.get("cwd")
        if isinstance(cwd, str) and cwd.strip():
            return cwd
    except Exception:
        pass

    env_cwd = os.getenv("TERMINAL_CWD", "").strip()
    if env_cwd:
        return os.path.expanduser(env_cwd)
    return fallback or os.getcwd()


def _resolve_path_from_workspace(policy: UserWorkspacePolicy, raw_path: str) -> str:
    candidate = Path(raw_path or "").expanduser()
    if not candidate.is_absolute():
        candidate = Path(policy.workspace_dir) / candidate
    return str(candidate.resolve())


def _is_within_workspace(policy: UserWorkspacePolicy, raw_path: str) -> bool:
    resolved = _resolve_path_from_workspace(policy, raw_path)
    root = os.path.realpath(policy.workspace_dir)
    return resolved == root or resolved.startswith(root + os.sep)


def _extract_tool_paths(tool_name: str, args: dict[str, Any]) -> list[str]:
    if tool_name in {"read_file", "write_file"}:
        path = args.get("path")
        return [path] if isinstance(path, str) and path.strip() else []

    if tool_name == "search_files":
        path = args.get("path", ".")
        return [path] if isinstance(path, str) and path.strip() else ["."]

    if tool_name == "patch":
        mode = str(args.get("mode", "replace") or "replace").strip().lower()
        if mode == "replace":
            path = args.get("path")
            return [path] if isinstance(path, str) and path.strip() else []
        if mode == "patch":
            content = args.get("patch")
            if not isinstance(content, str) or not content.strip():
                return []
            paths = [p.strip() for p in _PATCH_PATH_RE.findall(content) if p.strip()]
            paths.extend(p.strip() for p in _PATCH_MOVE_RE.findall(content) if p.strip())
            return paths
    return []


def get_tool_block_message(
    tool_name: str,
    args: Optional[dict[str, Any]],
    task_id: str = "",
) -> Optional[str]:
    policy = get_policy_for_task(task_id)
    if policy is None or not policy.restricted:
        return None

    normalized_args = args if isinstance(args, dict) else {}

    if tool_name in {"delegate_task", "skill_manage", "cronjob", "memory"}:
        return (
            f"Access denied: restricted users cannot use the '{tool_name}' tool."
        )

    if tool_name == "terminal" and not policy.allow_terminal:
        return (
            "This user is restricted to a dedicated workspace and cannot use "
            "the terminal tool on the host machine. Use file tools inside "
            f"{policy.workspace_dir} instead."
        )

    if tool_name == "execute_code" and not policy.allow_execute_code:
        return (
            "This user is restricted to a dedicated workspace and cannot use "
            "execute_code on the host machine."
        )

    if tool_name in {"read_file", "write_file", "patch", "search_files"}:
        for raw_path in _extract_tool_paths(tool_name, normalized_args):
            if not _is_within_workspace(policy, raw_path):
                return (
                    f"Access denied: this user may only access files inside "
                    f"{policy.workspace_dir}."
                )

    return None
