from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from hermes_state import SessionDB
from hermes_cli.profiles import get_active_profile_name, get_profile_dir, list_profiles


_ACTIONABLE_CONTINUATION_STATUSES = {"pending", "retry_requested", "running"}


def _to_iso(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(float(value)).isoformat()
    except Exception:
        return None


def _profile_root(profile_id: Optional[str]) -> Path:
    normalized = str(profile_id or "").strip() or get_active_profile_name()
    return get_profile_dir(normalized)


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
            return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _load_soul(profile_root: Path) -> Optional[str]:
    soul_path = profile_root / "SOUL.md"
    if not soul_path.exists():
        return None
    try:
        return soul_path.read_text(encoding="utf-8")
    except Exception:
        return None


def _count_sessions(profile_root: Path) -> int:
    db_path = profile_root / "state.db"
    if not db_path.exists():
        return 0
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM sessions")
            row = cursor.fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()
    except Exception:
        return 0


def _count_skills(profile_root: Path) -> int:
    skills_dir = profile_root / "skills"
    if not skills_dir.is_dir():
        return 0
    count = 0
    for skill_md in skills_dir.rglob("SKILL.md"):
        skill_path = str(skill_md)
        if "/.hub/" in skill_path or "/.git/" in skill_path:
            continue
        count += 1
    return count


def _read_profile_config_subset(profile_id: str) -> Optional[Dict[str, Any]]:
    profile_root = _profile_root(profile_id)
    if not profile_root.exists():
        return None

    raw = _load_yaml(profile_root / "config.yaml")
    model_cfg = raw.get("model") if isinstance(raw.get("model"), dict) else {}
    agent_cfg = raw.get("agent") if isinstance(raw.get("agent"), dict) else {}
    terminal_cfg = raw.get("terminal") if isinstance(raw.get("terminal"), dict) else {}
    display_cfg = raw.get("display") if isinstance(raw.get("display"), dict) else {}
    memory_cfg = raw.get("memory") if isinstance(raw.get("memory"), dict) else {}
    approvals_cfg = raw.get("approvals") if isinstance(raw.get("approvals"), dict) else {}
    compression_cfg = raw.get("compression") if isinstance(raw.get("compression"), dict) else {}

    return {
        "modelDefault": model_cfg.get("default"),
        "modelProvider": model_cfg.get("provider"),
        "modelBaseUrl": model_cfg.get("base_url"),
        "maxTurns": agent_cfg.get("max_turns"),
        "reasoningEffort": agent_cfg.get("reasoning_effort"),
        "toolUseEnforcement": agent_cfg.get("tool_use_enforcement"),
        "policyPreset": raw.get("ui_policy_preset"),
        "toolsets": raw.get("toolsets"),
        "terminalBackend": terminal_cfg.get("backend"),
        "terminalTimeout": terminal_cfg.get("timeout"),
        "displayCompact": display_cfg.get("compact"),
        "displayStreaming": display_cfg.get("streaming"),
        "displayShowCost": display_cfg.get("show_cost"),
        "displayPersonality": display_cfg.get("personality"),
        "memoryEnabled": memory_cfg.get("memory_enabled"),
        "userProfileEnabled": memory_cfg.get("user_profile_enabled"),
        "approvalsMode": approvals_cfg.get("mode"),
        "compressionEnabled": compression_cfg.get("enabled"),
        "compressionThreshold": compression_cfg.get("threshold"),
        "soul": _load_soul(profile_root),
    }


def _list_authority_profiles(active_profile: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for profile in list_profiles():
        config = _load_yaml(profile.path / "config.yaml")
        model_cfg = config.get("model") if isinstance(config.get("model"), dict) else {}
        model_default = model_cfg.get("default")
        policy_preset = config.get("ui_policy_preset") or "safe-chat"
        session_count = _count_sessions(profile.path)
        skill_count = _count_skills(profile.path)
        rows.append(
            {
                "id": profile.name,
                "name": profile.name,
                "modelDefault": model_default,
                "policyPreset": policy_preset,
                "sessionCount": session_count,
                "skillCount": skill_count,
                "extensionCount": 0,
                "integrationsCount": 0,
                "runtimeProvider": "real-hermes" if model_default else "unconfigured",
                "runtimeSummary": f"{model_default or 'No default model'} · {session_count} sessions · {skill_count} skills",
                "trustMode": policy_preset,
                "runtimeHealth": "healthy" if model_default else "degraded",
                "profileContextLabel": (
                    f"{profile.name} · active runtime profile"
                    if profile.name == active_profile
                    else f"{profile.name} · authority api profile"
                ),
                "workspacePath": ((config.get("terminal") or {}).get("cwd") if isinstance(config.get("terminal"), dict) else None),
                "active": profile.name == active_profile,
            }
        )
    return rows


def _open_session_db(profile_id: str) -> Optional[SessionDB]:
    profile_root = _profile_root(profile_id)
    db_path = profile_root / "state.db"
    if not db_path.exists():
        return None
    try:
        return SessionDB(db_path)
    except Exception:
        return None


def _list_sessions(profile_id: str, search: Optional[str] = None) -> List[Dict[str, Any]]:
    db = _open_session_db(profile_id)
    if db is None:
        return []
    try:
        rows = db.list_sessions_rich(limit=100, include_children=True)
    finally:
        db.close()

    query = str(search or "").strip().lower()
    sessions: List[Dict[str, Any]] = []
    for row in rows:
        preview = str(row.get("preview") or "") or None
        title = str(row.get("title") or "").strip() or ((preview or "")[:40] if preview else "Untitled session")
        hay = f"{title} {preview or ''}".lower()
        if query and query not in hay:
            continue
        archived = bool(row.get("ended_at"))
        model_config: Dict[str, Any] = {}
        raw_model_config = row.get("model_config")
        if raw_model_config:
            try:
                model_config = json.loads(raw_model_config) or {}
            except Exception:
                model_config = {}
        sessions.append(
            {
                "id": row.get("id"),
                "title": title,
                "updatedAt": _to_iso(row.get("last_active") or row.get("started_at")),
                "preview": preview,
                "workspaceLabel": "Archived" if archived else ("Forks" if row.get("parent_session_id") else "Active workspace"),
                "pinned": bool(model_config.get("pinned", False)),
                "archived": archived,
                "parentSessionId": row.get("parent_session_id"),
                "source": str(row.get("source") or "unknown").lower(),
                "profileId": profile_id,
                "model": row.get("model") or "unknown",
                "provider": model_config.get("provider", "real-hermes"),
            }
        )
    return sessions


def _get_session(profile_id: str, session_id: str) -> Optional[Dict[str, Any]]:
    db = _open_session_db(profile_id)
    if db is None:
        return None
    try:
        row = db.get_session(session_id)
        if not row:
            return None
        messages = db.get_messages(session_id)
    finally:
        db.close()

    model_config: Dict[str, Any] = {}
    raw_model_config = row.get("model_config")
    if raw_model_config:
        try:
            model_config = json.loads(raw_model_config) or {}
        except Exception:
            model_config = {}

    normalized_messages = []
    preview = None
    for index, message in enumerate(messages, start=1):
        content = message.get("content") or ""
        if preview is None and message.get("role") == "user" and content:
            preview = str(content)[:160]
        normalized_messages.append(
            {
                "id": f"{session_id}-{index}",
                "role": message.get("role"),
                "content": content,
                "createdAt": _to_iso(message.get("timestamp")),
            }
        )

    title = str(row.get("title") or "").strip() or ((preview or "")[:40] if preview else "Untitled session")
    archived = bool(row.get("ended_at"))
    return {
        "id": row.get("id"),
        "title": title,
        "updatedAt": _to_iso(row.get("started_at")),
        "preview": preview,
        "messages": normalized_messages,
        "parentSessionId": row.get("parent_session_id"),
        "loadedSkillIds": model_config.get("loadedSkillIds", []),
        "archived": archived,
        "pinned": bool(model_config.get("pinned", False)),
        "source": str(row.get("source") or "unknown").lower(),
        "profileId": profile_id,
        "settings": {
            "model": row.get("model") or "unknown",
            "provider": model_config.get("provider", "real-hermes"),
            "policyPreset": model_config.get("policyPreset", "safe-chat"),
            "memoryMode": model_config.get("memoryMode", "standard"),
        },
    }


def _read_runs(profile_id: str) -> List[Dict[str, Any]]:
    runs_path = _profile_root(profile_id) / "runtime" / "runs" / "index.json"
    if not runs_path.exists():
        return []
    try:
        payload = json.loads(runs_path.read_text(encoding="utf-8")) or {}
        runs = payload.get("runs") if isinstance(payload, dict) else []
        return runs if isinstance(runs, list) else []
    except Exception:
        return []


def _read_continuations(profile_id: str) -> Dict[str, List[Dict[str, Any]]]:
    queue_path = _profile_root(profile_id) / "runtime" / "orchestration" / "continuations.json"
    if not queue_path.exists():
        return {"continuations": [], "history": []}
    try:
        payload = json.loads(queue_path.read_text(encoding="utf-8")) or {}
        items = payload.get("items") if isinstance(payload, dict) else []
        if not isinstance(items, list):
            items = []
    except Exception:
        items = []

    actionable: List[Dict[str, Any]] = []
    history: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "unknown").strip().lower()
        if status in _ACTIONABLE_CONTINUATION_STATUSES:
            actionable.append(item)
        else:
            history.append(item)

    actionable.sort(key=lambda item: str(item.get("updatedAt") or item.get("createdAt") or ""), reverse=True)
    history.sort(key=lambda item: str(item.get("updatedAt") or item.get("createdAt") or ""), reverse=True)
    return {"continuations": actionable, "history": history}


def _get_workspaces(profile_id: str) -> Dict[str, Any]:
    profile_root = _profile_root(profile_id)
    config = _load_yaml(profile_root / "config.yaml")
    terminal_cfg = config.get("terminal") if isinstance(config.get("terminal"), dict) else {}
    known: List[Dict[str, Any]] = []
    configured_cwd = str(terminal_cfg.get("cwd") or "").strip() or None
    if configured_cwd:
        known.append(
            {
                "id": "terminal-cwd",
                "label": "Configured workspace",
                "path": configured_cwd,
                "source": "terminal.cwd",
            }
        )
    workspace_root = profile_root / "workspace"
    if workspace_root.exists():
        known.append(
            {
                "id": "profile-workspace",
                "label": "Profile workspace",
                "path": str(workspace_root),
                "source": "profile-workspace",
            }
        )
    current = known[0] if known else None
    return {"current": current, "known": known}


def get_authority_snapshot(
    *,
    profile_id: Optional[str] = None,
    search: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    selected_profile = str(profile_id or "").strip() or get_active_profile_name()
    active_profile = get_active_profile_name()
    continuations = _read_continuations(selected_profile)
    return {
        "profileId": selected_profile,
        "profiles": _list_authority_profiles(active_profile),
        "config": _read_profile_config_subset(selected_profile),
        "sessions": _list_sessions(selected_profile, search),
        "session": _get_session(selected_profile, str(session_id or "").strip()) if session_id else None,
        "runs": _read_runs(selected_profile),
        "continuations": continuations["continuations"],
        "history": continuations["history"],
        "workspaces": _get_workspaces(selected_profile),
    }
