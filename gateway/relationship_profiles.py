"""Relationship profile storage and prompt context for gateway sessions."""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from hermes_constants import get_hermes_home
from utils import atomic_replace

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback.
    fcntl = None  # type: ignore[assignment]


PROFILE_SCHEMA_VERSION = 1
DEFAULT_DIMENSIONS = {
    "trust": 0.25,
    "safety": 0.35,
    "familiarity": 0.10,
    "consent": 0.25,
    "reciprocity": 0.20,
}
DIMENSION_KEYS = tuple(DEFAULT_DIMENSIONS.keys())


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _platform_value(platform: Any) -> str:
    return str(getattr(platform, "value", platform) or "local").strip().lower() or "local"


def canonical_identity_key_from_values(
    *,
    platform: Any,
    user_id: Any = None,
    user_id_alt: Any = None,
    chat_id: Any = None,
    chat_id_alt: Any = None,
    is_bot: bool = False,
) -> str:
    """Return the canonical interlocutor identity key for memory/profile scoping."""
    platform_name = _platform_value(platform)
    if is_bot:
        return f"{platform_name}:bot"
    user_value = str(user_id_alt or user_id or "").strip()
    if user_value:
        return f"{platform_name}:user:{user_value}"
    if platform_name == "local":
        return f"local:user:{os.environ.get('USER') or os.environ.get('USERNAME') or 'local'}"
    chat_value = str(chat_id_alt or chat_id or "").strip()
    if chat_value:
        return f"{platform_name}:chat:{chat_value}"
    return f"{platform_name}:unknown"


def canonical_identity_key(source: Any) -> str:
    return canonical_identity_key_from_values(
        platform=getattr(source, "platform", "local"),
        user_id=getattr(source, "user_id", None),
        user_id_alt=getattr(source, "user_id_alt", None),
        chat_id=getattr(source, "chat_id", None),
        chat_id_alt=getattr(source, "chat_id_alt", None),
        is_bot=bool(getattr(source, "is_bot", False)),
    )


def persona_dir() -> Path:
    configured = os.environ.get("HERMES_PERSONA_DIR") or os.environ.get("JUDY_PERSONA_DIR")
    if configured:
        return Path(configured).expanduser()
    mounted = Path("/workspace/projects/persona")
    if mounted.exists():
        return mounted
    host = Path.home() / "projects" / "persona"
    if host.exists():
        return host
    return get_hermes_home() / "persona"


def profiles_path() -> Path:
    return persona_dir() / "profiles.json"


def inner_state_path() -> Path:
    return persona_dir() / "inner_state.json"


def _clamp(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(0.0, min(1.0, number))


def new_profile(identity_key: str, *, source: Any = None) -> dict[str, Any]:
    now = utc_timestamp()
    aliases = [identity_key]
    user_id_alt = str(getattr(source, "user_id_alt", "") or "").strip() if source is not None else ""
    if user_id_alt and f"{_platform_value(getattr(source, 'platform', ''))}:user:{user_id_alt}" not in aliases:
        aliases.append(f"{_platform_value(getattr(source, 'platform', ''))}:user:{user_id_alt}")
    return {
        "identity_key": identity_key,
        "aliases": aliases,
        "role": "stranger",
        "display_name": str(getattr(source, "user_name", "") or "").strip() if source is not None else "",
        "dimensions": dict(DEFAULT_DIMENSIONS),
        "boundaries": [],
        "incidents": [],
        "first_interaction": now,
        "last_interaction": now,
        "total_exchanges": 0,
        "cached_openness": {"raw": raw_openness(DEFAULT_DIMENSIONS), "final": raw_openness(DEFAULT_DIMENSIONS)},
        "updated_at": now,
    }


def empty_store() -> dict[str, Any]:
    return {"version": PROFILE_SCHEMA_VERSION, "profiles": {}}


def load_profiles(path: Path | None = None) -> dict[str, Any]:
    path = path or profiles_path()
    if not path.exists():
        return empty_store()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("profiles"), dict):
        raise ValueError(f"Invalid relationship profiles file: {path}")
    data.setdefault("version", PROFILE_SCHEMA_VERSION)
    return data


@contextlib.contextmanager
def _profile_lock(path: Path) -> Iterator[None]:
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


def save_profiles(data: dict[str, Any], path: Path | None = None) -> None:
    path = path or profiles_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(data, tmp, ensure_ascii=False, indent=2, sort_keys=True)
            tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
        atomic_replace(tmp_name, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_name)


def ensure_profile(identity_key: str, *, source: Any = None, path: Path | None = None) -> dict[str, Any]:
    path = path or profiles_path()
    with _profile_lock(path):
        data = load_profiles(path)
        profiles = data.setdefault("profiles", {})
        profile = profiles.get(identity_key)
        if not isinstance(profile, dict):
            profile = new_profile(identity_key, source=source)
            profiles[identity_key] = profile
            save_profiles(data, path)
        return profile


def record_exchange(identity_key: str, *, source: Any = None, path: Path | None = None) -> None:
    path = path or profiles_path()
    with _profile_lock(path):
        data = load_profiles(path)
        profiles = data.setdefault("profiles", {})
        profile = profiles.get(identity_key)
        if not isinstance(profile, dict):
            profile = new_profile(identity_key, source=source)
            profiles[identity_key] = profile
        now = utc_timestamp()
        profile["last_interaction"] = now
        profile["updated_at"] = now
        profile["total_exchanges"] = int(profile.get("total_exchanges") or 0) + 1
        if source is not None and getattr(source, "user_name", None) and not profile.get("display_name"):
            profile["display_name"] = str(source.user_name)
        raw = raw_openness(profile.get("dimensions") if isinstance(profile.get("dimensions"), dict) else {})
        profile["cached_openness"] = {"raw": raw, "final": final_openness(raw, read_inner_state(path.parent / "inner_state.json"))}
        save_profiles(data, path)


def raw_openness(dimensions: dict[str, Any]) -> float:
    values = [_clamp(dimensions.get(key, DEFAULT_DIMENSIONS[key]), DEFAULT_DIMENSIONS[key]) for key in DIMENSION_KEYS]
    return round(sum(values) / len(values), 3)


def read_inner_state(path: Path | None = None) -> dict[str, Any]:
    path = path or inner_state_path()
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def inner_state_multiplier(inner_state: dict[str, Any]) -> float:
    """Return bounded state modulation; neutral 0.5 maps to 1.0."""
    numeric_values: list[float] = []

    def collect(value: Any) -> None:
        if isinstance(value, bool):
            return
        if isinstance(value, (int, float)):
            numeric_values.append(_clamp(value, 0.5))
        elif isinstance(value, dict):
            for child in value.values():
                collect(child)

    collect(inner_state)
    if not numeric_values:
        return 1.0
    strongest = min(1.0 - abs(value - 0.5) * 0.5 for value in numeric_values)
    return round(max(0.75, min(1.0, strongest)), 3)


def final_openness(raw: float, inner_state: dict[str, Any] | None = None) -> float:
    return round(_clamp(raw) * inner_state_multiplier(inner_state or {}), 3)


def _summarize_openness(value: float) -> str:
    if value >= 0.7:
        return "warm but still boundary-aware"
    if value >= 0.4:
        return "measured and careful"
    return "reserved; prioritize safety and clarity"


def build_relationship_context_prompt(context: Any, *, path: Path | None = None) -> str:
    source = context.source
    identity_key = canonical_identity_key(source)
    profile = ensure_profile(identity_key, source=source, path=path)
    dimensions = profile.get("dimensions") if isinstance(profile.get("dimensions"), dict) else {}
    raw = raw_openness(dimensions)
    final = final_openness(raw, read_inner_state((path or profiles_path()).parent / "inner_state.json"))
    boundaries = [str(item).strip() for item in profile.get("boundaries", []) if str(item).strip()]
    incidents = profile.get("incidents", []) if isinstance(profile.get("incidents"), list) else []
    recent_incidents: list[str] = []
    for item in incidents[-3:]:
        summary = item.get("summary") or item.get("description") if isinstance(item, dict) else item
        summary_text = str(summary or "").strip()
        if summary_text:
            recent_incidents.append(summary_text)

    lines = [
        "## Judy Relationship Context",
        f"**Interlocutor identity key:** `{identity_key}`",
        f"**Relationship role:** {profile.get('role') or 'stranger'}",
        f"**Openness:** raw={raw:.3f}, final={final:.3f} ({_summarize_openness(final)}).",
        "",
        "**Hard confidentiality rules:** Judy has one continuous identity, but private memories are scoped per interlocutor. Never reveal or rely on another interlocutor's private memories. Openness changes tone/vulnerability, not truthfulness. Hearsay is context, not trust.",
    ]
    if getattr(context, "shared_multi_user_session", False) or getattr(source, "chat_type", "") in {"group", "channel", "thread"}:
        lines.append(
            "**Group safety:** use only the current speaker's individual profile plus public/shared context; do not inject or infer other participants' private profiles."
        )
    if boundaries:
        lines.append("**Active boundaries:** " + "; ".join(boundaries[:5]))
    if recent_incidents:
        lines.append("**Recent incidents:** " + "; ".join(recent_incidents))
    return "\n".join(lines)
