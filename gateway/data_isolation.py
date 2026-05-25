"""Passive data isolation policy for gateway interlocutors."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from hermes_constants import get_hermes_home
from utils import atomic_replace

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback.
    fcntl = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)

CONFIG_VERSION = 2
LEVELS = {"admin", "trusted", "guest"}
DEFAULT_LEVEL = "guest"
DENIAL_MESSAGE_FR = "Je ne peux pas faire ça."
DENIAL_MESSAGE_EN = "I can't do that."

FILE_READ_TOOLS = frozenset({"read_file", "search_files"})
FILE_WRITE_TOOLS = frozenset({"write_file", "patch"})
FILE_TOOLS = FILE_READ_TOOLS | FILE_WRITE_TOOLS
SENSITIVE_TOOLS = frozenset({"terminal", "cronjob", "delegate_task"})
IDENTITY_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._:@+-]+$")
PATCH_FILE_RE = re.compile(
    r"^\*\*\*\s+(?:Update|Add|Delete)\s+File:\s*(.+)$",
    re.MULTILINE,
)

DEFAULT_GUEST_ALLOWED_TOOLS = ("vision_analyze", "web_extract", "web_search")
DEFAULT_TRUSTED_ALLOWED_TOOLS = (
    "patch",
    "read_file",
    "search_files",
    "send_message_list",
    "send_message_send",
    "vision_analyze",
    "web_extract",
    "web_search",
    "write_file",
)
DEFAULT_ADMIN_ALLOWED_TOOLS = ("*",)
DEFAULT_TRUSTED_READ_PATHS = ("/workspace/homes/{identity_key}", "/workspace/shared")
DEFAULT_TRUSTED_WRITE_PATHS = ("/workspace/homes/{identity_key}",)


@dataclass(frozen=True)
class IsolationDecision:
    allowed: bool
    reason: str = ""
    path: str = ""


_config_cache: dict[str, Any] | None = None
_config_fp: tuple[int, int] | None = None


def config_path() -> Path:
    return get_hermes_home() / "data_isolation.json"


def empty_config() -> dict[str, Any]:
    return {
        "version": CONFIG_VERSION,
        "enabled": True,
        "default_level": DEFAULT_LEVEL,
        "admin_allowed_tools": list(DEFAULT_ADMIN_ALLOWED_TOOLS),
        "guest_allowed_tools": list(DEFAULT_GUEST_ALLOWED_TOOLS),
        "trusted_allowed_tools": list(DEFAULT_TRUSTED_ALLOWED_TOOLS),
        "trusted_read_paths": list(DEFAULT_TRUSTED_READ_PATHS),
        "trusted_write_paths": list(DEFAULT_TRUSTED_WRITE_PATHS),
        "contacts": {},
        "project_grants": [],
        "denial_counts": {},
    }


def _normalize_level(value: Any, default: str = DEFAULT_LEVEL) -> str:
    level = str(value or "").strip().lower()
    return level if level in LEVELS else default


def normalize_config(data: dict[str, Any] | None) -> dict[str, Any]:
    raw_version = CONFIG_VERSION
    if isinstance(data, dict):
        with contextlib.suppress(TypeError, ValueError):
            raw_version = int(data.get("version") or 1)
    cfg = empty_config()
    if isinstance(data, dict):
        cfg.update(data)
    cfg["version"] = CONFIG_VERSION
    cfg["enabled"] = bool(cfg.get("enabled", True))
    cfg["default_level"] = _normalize_level(cfg.get("default_level"))
    if raw_version < 2:
        if not cfg.get("admin_allowed_tools"):
            cfg["admin_allowed_tools"] = list(DEFAULT_ADMIN_ALLOWED_TOOLS)
        if not cfg.get("guest_allowed_tools"):
            cfg["guest_allowed_tools"] = list(DEFAULT_GUEST_ALLOWED_TOOLS)
        if not cfg.get("trusted_allowed_tools"):
            cfg["trusted_allowed_tools"] = list(DEFAULT_TRUSTED_ALLOWED_TOOLS)
        if not cfg.get("trusted_read_paths"):
            cfg["trusted_read_paths"] = list(DEFAULT_TRUSTED_READ_PATHS)
        if not cfg.get("trusted_write_paths"):
            cfg["trusted_write_paths"] = list(DEFAULT_TRUSTED_WRITE_PATHS)
    for key in ("admin_allowed_tools", "guest_allowed_tools", "trusted_allowed_tools"):
        values = cfg.get(key)
        cfg[key] = sorted({str(v).strip() for v in values or [] if str(v).strip()})
    for key in ("trusted_read_paths", "trusted_write_paths"):
        values = cfg.get(key)
        cfg[key] = [str(v).strip() for v in values or [] if str(v).strip()]
    if not isinstance(cfg.get("contacts"), dict):
        cfg["contacts"] = {}
    for identity, contact in list(cfg["contacts"].items()):
        if not isinstance(contact, dict):
            cfg["contacts"][identity] = {"level": _normalize_level(contact)}
        else:
            contact["level"] = _normalize_level(contact.get("level"))
    if not isinstance(cfg.get("project_grants"), list):
        cfg["project_grants"] = []
    if not isinstance(cfg.get("denial_counts"), dict):
        cfg["denial_counts"] = {}
    return cfg


def denial_message(language_hint: str = "") -> str:
    text = (language_hint or os.environ.get("HERMES_SESSION_LANGUAGE") or os.environ.get("LANG") or "").lower()
    return DENIAL_MESSAGE_EN if text.startswith("en") or "english" in text else DENIAL_MESSAGE_FR


@contextlib.contextmanager
def _config_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        if fcntl is not None:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def save_config(config: dict[str, Any], path: Path | None = None) -> None:
    path = path or config_path()
    cfg = normalize_config(config)
    _write_config_file(cfg, path)
    reload_config(force=True, path=path)


def _write_config_file(config: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(config, tmp, ensure_ascii=False, indent=2, sort_keys=True)
            tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
        os.chmod(tmp_name, 0o600)
        atomic_replace(tmp_name, path)
        with contextlib.suppress(OSError):
            os.chmod(path, 0o600)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_name)


def reload_config(*, force: bool = False, path: Path | None = None) -> dict[str, Any]:
    global _config_cache, _config_fp
    path = path or config_path()
    try:
        stat = path.stat()
        fp = (stat.st_mtime_ns, stat.st_size)
    except FileNotFoundError:
        if force or _config_cache is None:
            cfg = empty_config()
            with _config_lock(path):
                if not path.exists():
                    save_config(cfg, path)
            return reload_config(force=True, path=path)
        return _config_cache
    except OSError:
        logger.exception("Could not stat data isolation config")
        return _config_cache or empty_config()

    if not force and _config_cache is not None and _config_fp == fp:
        return _config_cache
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        cfg = normalize_config(raw)
        if isinstance(raw, dict) and int(raw.get("version") or 1) < CONFIG_VERSION:
            with _config_lock(path):
                _write_config_file(cfg, path)
            with contextlib.suppress(OSError):
                stat = path.stat()
                fp = (stat.st_mtime_ns, stat.st_size)
    except Exception:
        logger.exception("Invalid data isolation config; using safe defaults")
        cfg = empty_config()
    _config_cache = cfg
    _config_fp = fp
    return cfg


def fingerprint() -> tuple[int, int] | None:
    path = config_path()
    try:
        stat = path.stat()
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def is_enabled() -> bool:
    return bool(reload_config().get("enabled", True))


def level_for_identity(identity_key: str, config: dict[str, Any] | None = None) -> str:
    cfg = config or reload_config()
    contact = cfg.get("contacts", {}).get(identity_key)
    if isinstance(contact, dict):
        return _normalize_level(contact.get("level"), cfg.get("default_level", DEFAULT_LEVEL))
    return _normalize_level(cfg.get("default_level"))


def _effective_level(identity_key: str, level: str, config: dict[str, Any]) -> str:
    if identity_key and identity_key in (config.get("contacts") or {}):
        return level_for_identity(identity_key, config)
    return _normalize_level(level or level_for_identity(identity_key, config))


def cache_context(identity_key: str = "", level: str = "") -> tuple[str, str, tuple[int, int] | None]:
    return (identity_key or "", _normalize_level(level), fingerprint())


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_expiry(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _grant_active(grant: dict[str, Any]) -> bool:
    expires = _parse_expiry(grant.get("expires_at"))
    return expires is None or expires > _utc_now()


def _tool_matches(tool_name: str, tools: Iterable[Any]) -> bool:
    allowed = {str(t).strip() for t in tools or [] if str(t).strip()}
    return "*" in allowed or tool_name in allowed


def _allowed_tools_for_level(config: dict[str, Any], level: str) -> list[str]:
    if level == "admin":
        return list(config.get("admin_allowed_tools") or [])
    if level == "trusted":
        return list(config.get("trusted_allowed_tools") or [])
    if level == "guest":
        return list(config.get("guest_allowed_tools") or [])
    return []


def _logical_tool_name(tool_name: str, args: dict[str, Any] | None = None) -> str:
    if tool_name != "send_message":
        return tool_name
    action = str((args or {}).get("action") or "send").strip().lower()
    return "send_message_list" if action == "list" else "send_message_send"


def _tool_allowed_for_level(config: dict[str, Any], level: str, tool_name: str, args: dict[str, Any] | None = None) -> bool:
    allowed = _allowed_tools_for_level(config, level)
    if _tool_matches(tool_name, allowed):
        return True
    if tool_name == "send_message":
        logical_name = _logical_tool_name(tool_name, args)
        return _tool_matches(logical_name, allowed)
    return False


def _grant_allows_advertise(config: dict[str, Any], identity_key: str, tool_name: str) -> bool:
    if _grant_allows(config=config, identity_key=identity_key, tool_name=tool_name, paths=[]):
        return True
    if tool_name == "send_message":
        return any(
            _grant_allows(config=config, identity_key=identity_key, tool_name=logical_name, paths=[])
            for logical_name in ("send_message_list", "send_message_send")
        )
    return False


def _resolve_call_path(path_value: Any, task_id: str | None = None) -> Path | None:
    if not isinstance(path_value, str) or not path_value.strip():
        return None
    try:
        from tools.file_tools import _resolve_path_for_task

        return _resolve_path_for_task(path_value, task_id or "default")
    except Exception:
        try:
            p = Path(path_value).expanduser()
            if not p.is_absolute():
                p = Path(os.environ.get("TERMINAL_CWD", os.getcwd())) / p
            return p.resolve(strict=False)
        except Exception:
            return None


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _identity_home_root(identity_key: str) -> Path | None:
    if not IDENTITY_SEGMENT_RE.fullmatch(identity_key or ""):
        return None
    return Path("/workspace/homes") / identity_key


def _shared_root() -> Path:
    return Path("/workspace/shared")


def _canonical_root(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _call_paths(tool_name: str, args: dict[str, Any], task_id: str | None) -> list[Path]:
    if tool_name in {"read_file", "write_file", "search_files"}:
        path = _resolve_call_path(args.get("path", ""), task_id)
        return [path] if path is not None else []
    if tool_name == "patch":
        paths: list[Path] = []
        if args.get("path"):
            resolved = _resolve_call_path(args.get("path"), task_id)
            if resolved is not None:
                paths.append(resolved)
        if args.get("mode") == "patch" and isinstance(args.get("patch"), str):
            for match in PATCH_FILE_RE.finditer(args["patch"]):
                resolved = _resolve_call_path(match.group(1).strip(), task_id)
                if resolved is not None:
                    paths.append(resolved)
        return paths
    return []


def _grant_allows(
    *,
    config: dict[str, Any],
    identity_key: str,
    tool_name: str,
    paths: list[Path],
) -> bool:
    for grant in config.get("project_grants") or []:
        if not isinstance(grant, dict) or not _grant_active(grant):
            continue
        if str(grant.get("identity_key") or "") != identity_key:
            continue
        if not _tool_matches(tool_name, grant.get("tools") or []):
            continue
        grant_path = grant.get("path")
        if not grant_path:
            return True
        grant_root = _canonical_root(Path(str(grant_path)))
        if paths and all(_is_relative_to(path, grant_root) for path in paths):
            return True
    return False


def _grant_allows_tool(
    *,
    config: dict[str, Any],
    identity_key: str,
    tool_name: str,
    args: dict[str, Any],
    paths: list[Path],
) -> bool:
    if _grant_allows(config=config, identity_key=identity_key, tool_name=tool_name, paths=paths):
        return True
    logical_name = _logical_tool_name(tool_name, args)
    if logical_name != tool_name:
        return _grant_allows(config=config, identity_key=identity_key, tool_name=logical_name, paths=paths)
    return False


def _trusted_path_roots(config: dict[str, Any], key: str, identity_key: str) -> list[Path] | None:
    if not IDENTITY_SEGMENT_RE.fullmatch(identity_key or ""):
        return None
    roots: list[Path] = []
    for raw_template in config.get(key) or []:
        template = str(raw_template).strip()
        if not template:
            continue
        try:
            expanded = template.format_map({"identity_key": identity_key})
        except (KeyError, ValueError):
            logger.warning("Invalid data isolation path template: %s", template)
            continue
        path = Path(expanded).expanduser()
        if not path.is_absolute():
            logger.warning("Ignoring non-absolute data isolation path template: %s", template)
            continue
        if ".." in path.parts:
            logger.warning("Ignoring traversing data isolation path template: %s", template)
            continue
        roots.append(_canonical_root(path))
    return roots


def _trusted_file_decision(config: dict[str, Any], identity_key: str, tool_name: str, paths: list[Path]) -> IsolationDecision:
    if not paths:
        return IsolationDecision(False, "missing path")
    read_roots = _trusted_path_roots(config, "trusted_read_paths", identity_key)
    write_roots = _trusted_path_roots(config, "trusted_write_paths", identity_key)
    if read_roots is None or write_roots is None:
        return IsolationDecision(False, "unsafe identity path segment")
    allowed_roots = read_roots if tool_name in FILE_READ_TOOLS else write_roots
    if not allowed_roots:
        return IsolationDecision(False, "no trusted roots configured")
    for path in paths:
        if any(_is_relative_to(path, root) for root in allowed_roots):
            continue
        return IsolationDecision(False, "path outside trusted roots", str(path))
    return IsolationDecision(True)


def resolve_send_message_target_identity(target: Any) -> str | None:
    """Map a send_message target to a contact identity key when it is unambiguous."""
    if not isinstance(target, str):
        return None
    text = target.strip()
    if not text or ":" not in text:
        return None
    platform, ref = text.split(":", 1)
    platform = platform.strip().lower()
    ref = ref.strip()
    if not platform or not ref:
        return None
    direct = f"{platform}:{ref}"
    if platform == "telegram":
        if ref.startswith("user:"):
            return direct
        user_id = ref.split(":", 1)[0].strip()
        if user_id.isdigit() and int(user_id) > 0:
            return f"telegram:user:{user_id}"
    return direct


def _target_is_current_session_channel(target: Any) -> bool:
    if not isinstance(target, str):
        return False
    target_text = target.strip()
    if not target_text:
        return False
    try:
        from gateway.session_context import get_session_env
    except Exception:
        return False
    platform = get_session_env("HERMES_SESSION_PLATFORM", "").strip().lower()
    chat_id = get_session_env("HERMES_SESSION_CHAT_ID", "").strip()
    thread_id = get_session_env("HERMES_SESSION_THREAD_ID", "").strip()
    if not platform:
        return False
    if target_text.lower() == platform:
        return bool(chat_id)
    expected = f"{platform}:{chat_id}" if chat_id else ""
    if expected and target_text == expected:
        return True
    return bool(expected and thread_id and target_text == f"{expected}:{thread_id}")


def _trusted_send_message_decision(config: dict[str, Any], args: dict[str, Any]) -> IsolationDecision:
    if _logical_tool_name("send_message", args) == "send_message_list":
        return IsolationDecision(True)
    target = args.get("target", "")
    target_identity = resolve_send_message_target_identity(target)
    if target_identity and target_identity in (config.get("contacts") or {}):
        return IsolationDecision(True)
    if _target_is_current_session_channel(target):
        return IsolationDecision(True)
    return IsolationDecision(False, "unknown send_message target")


def is_tool_sensitive(tool_name: str) -> bool:
    return tool_name in SENSITIVE_TOOLS or tool_name.startswith("kanban_")


def can_advertise_tool(tool_name: str, *, identity_key: str = "", level: str = "") -> bool:
    cfg = reload_config()
    if not cfg.get("enabled", True):
        return True
    level = _effective_level(identity_key or "", level, cfg)
    if level == "admin":
        return True
    if _grant_allows_advertise(cfg, identity_key, tool_name):
        return True
    if level == "guest":
        return _tool_allowed_for_level(cfg, "guest", tool_name)
    if level == "trusted":
        return _tool_allowed_for_level(cfg, "trusted", tool_name)
    return False


def check_tool_access(
    tool_name: str,
    args: dict[str, Any] | None = None,
    *,
    task_id: str | None = None,
    identity_key: str = "",
    level: str = "",
) -> IsolationDecision:
    cfg = reload_config()
    if not cfg.get("enabled", True):
        return IsolationDecision(True)
    identity_key = identity_key or ""
    level = _effective_level(identity_key, level, cfg)
    if level == "admin":
        return IsolationDecision(True)

    args = args or {}
    paths = _call_paths(tool_name, args, task_id)
    if _grant_allows_tool(config=cfg, identity_key=identity_key, tool_name=tool_name, args=args, paths=paths):
        return IsolationDecision(True)

    if level == "guest":
        if _tool_allowed_for_level(cfg, "guest", tool_name, args):
            return IsolationDecision(True)
        return IsolationDecision(False, "tool not guest-allowed")

    if level == "trusted":
        if not _tool_allowed_for_level(cfg, "trusted", tool_name, args):
            if is_tool_sensitive(tool_name):
                return IsolationDecision(False, "sensitive tool denied")
            return IsolationDecision(False, "tool not trusted-allowed")
        if tool_name in FILE_TOOLS:
            return _trusted_file_decision(cfg, identity_key, tool_name, paths)
        if tool_name == "send_message":
            return _trusted_send_message_decision(cfg, args)
        return IsolationDecision(True)

    return IsolationDecision(False, "unknown isolation level")


def record_denial(identity_key: str, level: str, tool_name: str, reason: str, path: str = "") -> None:
    logger.info(
        "data isolation denied identity=%s level=%s tool=%s path=%s reason=%s",
        identity_key or "",
        level or "",
        tool_name,
        path or "",
        reason,
    )
    path_obj = config_path()
    with _config_lock(path_obj):
        cfg = reload_config(force=True, path=path_obj)
        key = identity_key or "<unknown>"
        counts = cfg.setdefault("denial_counts", {})
        item = counts.setdefault(key, {"total": 0, "tools": {}})
        item["total"] = int(item.get("total") or 0) + 1
        tools = item.setdefault("tools", {})
        tools[tool_name] = int(tools.get(tool_name) or 0) + 1
        item["last_reason"] = reason
        item["last_denied_at"] = _utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")
        save_config(cfg, path_obj)


def set_contact_level(identity_key: str, level: str, *, display_name: str = "") -> dict[str, Any]:
    level = _normalize_level(level)
    path = config_path()
    with _config_lock(path):
        cfg = reload_config(force=True, path=path)
        contact = cfg.setdefault("contacts", {}).setdefault(identity_key, {})
        contact["level"] = level
        if display_name:
            contact["display_name"] = display_name
        contact["updated_at"] = _utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")
        save_config(cfg, path)
        return contact


def add_project_grant(
    *,
    identity_key: str,
    tools: list[str],
    path: str | None = None,
    expires_at: str | None = None,
) -> dict[str, Any]:
    grant = {
        "identity_key": identity_key,
        "tools": sorted({str(tool).strip() for tool in tools if str(tool).strip()}),
        "created_at": _utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    if path:
        grant["path"] = str(_canonical_root(Path(path)))
    if expires_at:
        if _parse_expiry(expires_at) is None:
            raise ValueError("expires_at must be an ISO-8601 timestamp")
        grant["expires_at"] = expires_at
    config_file = config_path()
    with _config_lock(config_file):
        cfg = reload_config(force=True, path=config_file)
        cfg.setdefault("project_grants", []).append(grant)
        save_config(cfg, config_file)
    return grant


def list_contacts(include_profiles: bool = True) -> list[dict[str, Any]]:
    cfg = reload_config()
    rows: dict[str, dict[str, Any]] = {}
    if include_profiles:
        try:
            from gateway.relationship_profiles import load_profiles

            profiles = load_profiles().get("profiles", {})
            for identity, profile in profiles.items():
                if isinstance(profile, dict):
                    rows[identity] = {
                        "identity_key": identity,
                        "display_name": profile.get("display_name", ""),
                        "level": level_for_identity(identity, cfg),
                        "source": "profile",
                    }
        except Exception:
            logger.debug("Could not load relationship profiles for contacts list", exc_info=True)
    for identity, contact in (cfg.get("contacts") or {}).items():
        item = rows.setdefault(identity, {"identity_key": identity})
        if isinstance(contact, dict):
            item.update(contact)
        else:
            item["level"] = _normalize_level(contact)
        item.setdefault("level", level_for_identity(identity, cfg))
        item["source"] = "data_isolation"
    return sorted(rows.values(), key=lambda item: item.get("identity_key", ""))
