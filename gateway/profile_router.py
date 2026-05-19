"""Profile-aware ingress routing for gateway messages.

This module implements the first, deliberately conservative slice of the
"one Telegram bot as ingress router to multiple Hermes profiles" feature:
route matching plus subprocess dispatch into a target profile's isolated
``HERMES_HOME``.  Keeping execution in a subprocess avoids mutating process-wide
profile state in the long-running gateway.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from hermes_constants import get_default_hermes_root


_PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


@dataclass(frozen=True)
class ProfileRoute:
    """A configured ingress route to a Hermes profile."""

    profile: str
    name: str = ""
    chat_id: str | None = None
    thread_id: str | None = None
    user_id: str | None = None
    username: str | None = None
    chat_type: str | None = None
    text_prefix: str | None = None
    command: str | None = None
    strip_prefix: bool = True
    pass_media: bool = False
    timeout_seconds: float = 1800.0


@dataclass(frozen=True)
class RoutedProfilePayload:
    """Text plus optional CLI media attachment for profile dispatch."""

    text: str
    image_path: str | None = None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def is_safe_profile_name(profile: str) -> bool:
    """Return True when *profile* is a plain Hermes profile directory name.

    Profile routes are configured by operators, but they still feed directly
    into ``HERMES_HOME`` for a child process. Keep that value constrained to a
    single profile directory under ``<root>/profiles``: no absolute paths, path
    separators, ``..`` segments, or shell-ish surprises.
    """
    return bool(_PROFILE_NAME_RE.fullmatch(profile or "")) and profile != "default"


def load_profile_routes(config: Mapping[str, Any] | None, platform: str = "telegram") -> list[ProfileRoute]:
    """Load ingress profile routes from config.yaml-shaped data.

    Supported shapes (Telegram first, but platform-parametric for later):

    ```yaml
    telegram:
      profile_routes:
        - profile: sasha
          chat_id: 12345
        - profile: research
          thread_id: 2
        - profile: coder
          text_prefix: /coder
          strip_prefix: true
    ```

    Also accepts ``gateway.profile_routes.<platform>`` for users who prefer to
    keep cross-platform routing under one top-level section.
    """
    if not isinstance(config, Mapping):
        return []

    candidates: list[Any] = []
    platform_cfg = config.get(platform)
    if isinstance(platform_cfg, Mapping):
        candidates.extend(_as_list(platform_cfg.get("profile_routes")))

    gateway_cfg = config.get("gateway")
    if isinstance(gateway_cfg, Mapping):
        profile_routes = gateway_cfg.get("profile_routes")
        if isinstance(profile_routes, Mapping):
            candidates.extend(_as_list(profile_routes.get(platform)))
        else:
            candidates.extend(_as_list(profile_routes))

    routes: list[ProfileRoute] = []
    for idx, raw in enumerate(candidates):
        if not isinstance(raw, Mapping):
            continue
        profile = _as_str(raw.get("profile"))
        if not profile or not is_safe_profile_name(profile):
            # The default profile is the current gateway; routing to it would
            # recurse/duplicate work rather than isolate anything. Unsafe names
            # are ignored so route config cannot escape <root>/profiles.
            continue
        try:
            timeout = float(raw.get("timeout_seconds", raw.get("timeout", 1800.0)))
        except (TypeError, ValueError):
            timeout = 1800.0
        routes.append(
            ProfileRoute(
                profile=profile,
                name=_as_str(raw.get("name")) or f"route-{idx + 1}",
                chat_id=_as_str(raw.get("chat_id")),
                thread_id=_as_str(raw.get("thread_id")),
                user_id=_as_str(raw.get("user_id")),
                username=_as_str(raw.get("username")),
                chat_type=_as_str(raw.get("chat_type")),
                text_prefix=_as_str(raw.get("text_prefix")),
                command=_normalize_command(_as_str(raw.get("command"))),
                strip_prefix=bool(raw.get("strip_prefix", True)),
                pass_media=bool(raw.get("pass_media", False)),
                timeout_seconds=max(1.0, timeout),
            )
        )
    return routes


def _normalize_command(command: str | None) -> str | None:
    if not command:
        return None
    return command.strip().lstrip("/").split("@", 1)[0].lower() or None


def _event_command(event: Any) -> str | None:
    try:
        cmd = event.get_command()
    except Exception:
        cmd = None
    return _normalize_command(cmd)


def _matches_field(expected: str | None, actual: Any) -> bool:
    return expected is None or expected == str(actual)


def _text_matches_prefix(text: str, prefix: str) -> bool:
    """Match a route prefix only at a command/token boundary."""
    stripped = (text or "").strip()
    if not stripped.startswith(prefix):
        return False
    if len(stripped) == len(prefix):
        return True
    return stripped[len(prefix)] in {" ", "\t", "\n", "\r", "/", "_"}


def match_profile_route(event: Any, routes: Sequence[ProfileRoute]) -> ProfileRoute | None:
    """Return the first profile route matching a gateway MessageEvent."""
    source = getattr(event, "source", None)
    if source is None:
        return None
    text = getattr(event, "text", "") or ""
    cmd = _event_command(event)

    for route in routes:
        if not _matches_field(route.chat_id, getattr(source, "chat_id", None)):
            continue
        if not _matches_field(route.thread_id, getattr(source, "thread_id", None)):
            continue
        if not _matches_field(route.user_id, getattr(source, "user_id", None)):
            continue
        if not _matches_field(route.chat_type, getattr(source, "chat_type", None)):
            continue
        if route.username:
            actual_username = (getattr(source, "user_name", "") or "").lstrip("@")
            if route.username.lstrip("@") != actual_username:
                continue
        if route.command and route.command != cmd:
            continue
        if route.text_prefix and not _text_matches_prefix(text, route.text_prefix):
            continue
        return route
    return None


def routed_text(event: Any, route: ProfileRoute) -> str:
    """Return message text to send to the target profile."""
    text = getattr(event, "text", "") or ""
    if route.text_prefix and route.strip_prefix:
        stripped = text.strip()
        if _text_matches_prefix(stripped, route.text_prefix):
            text = stripped[len(route.text_prefix):].lstrip()
    return text


def _is_image_media(mime_type: str, path: str) -> bool:
    """Return True when a routed media item should be treated as an image."""
    if (mime_type or "").lower().startswith("image/"):
        return True
    return Path(path).suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def routed_profile_payload(event: Any, route: ProfileRoute) -> RoutedProfilePayload:
    """Build text and opt-in media attachment for profile subprocess dispatch.

    Media forwarding is intentionally route-local and opt-in via ``pass_media``.
    The Hermes CLI currently accepts one explicit ``--image`` attachment in
    single-query mode, so the first image is attached natively and every cached
    media path is also summarized in text for tools/manual inspection.
    """
    text = routed_text(event, route)
    media_urls = list(getattr(event, "media_urls", None) or [])
    media_types = list(getattr(event, "media_types", None) or [])
    if not route.pass_media or not media_urls:
        return RoutedProfilePayload(text=text)

    first_image: str | None = None
    lines = ["[Telegram media attachments forwarded by ingress router:]"]
    for idx, url in enumerate(media_urls, start=1):
        mime_type = str(media_types[idx - 1]) if idx - 1 < len(media_types) else ""
        label = "file"
        note = ""
        if _is_image_media(mime_type, str(url)):
            label = "image"
            if first_image is None:
                first_image = str(url)
                note = " (attached via --image)"
        elif mime_type.startswith("audio/"):
            label = "audio"
        elif mime_type.startswith("video/"):
            label = "video"
        elif mime_type.startswith(("application/", "text/")):
            label = "document"
        mime_note = f"; mime={mime_type}" if mime_type else ""
        lines.append(f"- {label} {idx}: {url}{note}{mime_note}")

    media_note = "\n".join(lines)
    if text.strip():
        text = f"{text.rstrip()}\n\n{media_note}"
    else:
        text = f"Please inspect the attached Telegram media.\n\n{media_note}"
    return RoutedProfilePayload(text=text, image_path=first_image)


PROFILE_SCOPED_COMMANDS = frozenset({"new", "reset", "status", "help", "commands"})


def parse_profile_scoped_command(event: Any, route: ProfileRoute) -> tuple[str, str] | None:
    """Parse route-scoped control commands for a prefix route.

    For a route with ``text_prefix: /coder``, accepts conservative forms that
    are clearly commands rather than ordinary prompts:

    - ``/coder/new``
    - ``/coder_new`` (Telegram-safe command spelling)
    - ``/coder /new``

    It intentionally does not treat ``/coder new feature`` as a command; that
    remains a normal prompt to the coder profile.
    """
    prefix = route.text_prefix
    if not prefix:
        return None
    text = (getattr(event, "text", "") or "").strip()
    if not _text_matches_prefix(text, prefix):
        return None

    suffix = text[len(prefix):]
    if not suffix:
        return None

    command_text: str | None = None
    if suffix.startswith("/"):
        command_text = suffix[1:]
    elif suffix.startswith("_"):
        command_text = suffix[1:]
    elif suffix.startswith(" "):
        stripped = suffix.lstrip()
        if stripped.startswith("/"):
            command_text = stripped[1:]

    if not command_text:
        return None

    parts = command_text.split(maxsplit=1)
    command = _normalize_command(parts[0])
    if command not in PROFILE_SCOPED_COMMANDS:
        return None
    args = parts[1].strip() if len(parts) > 1 else ""
    return command, args


def profile_home(profile: str, *, root: Path | None = None) -> Path:
    """Resolve a named Hermes profile to its HERMES_HOME path."""
    if not is_safe_profile_name(profile):
        raise ValueError(f"Unsafe Hermes profile name: {profile!r}")
    base = root or get_default_hermes_root()
    profiles_dir = (base / "profiles").resolve()
    home = (profiles_dir / profile).resolve()
    if home.parent != profiles_dir:
        raise ValueError(f"Hermes profile escapes profiles directory: {profile!r}")
    return home


def _profile_has_telegram_token(home: Path) -> bool:
    """Return True if a routed profile appears to own a Telegram bot token.

    Do not return or log token values; this is purely a presence check so the
    ingress gateway can warn operators about likely 409 long-polling conflicts.
    """
    env_path = home / ".env"
    if env_path.exists():
        try:
            for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                key, value = stripped.split("=", 1)
                if key.strip() == "TELEGRAM_BOT_TOKEN" and value.strip().strip("'\""):
                    return True
        except OSError:
            pass

    config_path = home / "config.yaml"
    if config_path.exists():
        try:
            text = config_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        # Intentionally shallow: avoid importing yaml on the gateway hot path and
        # avoid exposing values. This catches the common accidental token clone.
        if "TELEGRAM_BOT_TOKEN" in text or "bot_token" in text or "telegram_token" in text:
            return True
    return False


def validate_profile_routes(
    routes: Sequence[ProfileRoute],
    *,
    root: Path | None = None,
) -> list[str]:
    """Return non-fatal operator warnings for configured profile routes."""
    warnings: list[str] = []
    seen_names: set[str] = set()
    base = root or get_default_hermes_root()

    for route in routes:
        if route.name in seen_names:
            warnings.append(
                f"duplicate route name '{route.name}' in telegram.profile_routes; "
                "route/session diagnostics may be ambiguous"
            )
        seen_names.add(route.name)

        try:
            home = profile_home(route.profile, root=base)
        except ValueError:
            warnings.append(
                f"unsafe profile name '{route.profile}' in telegram.profile_routes; route '{route.name}' ignored"
            )
            continue
        if not home.exists():
            warnings.append(
                f"profile '{route.profile}' not found at {home}; route '{route.name}' will fail if matched"
            )
            continue

        if _profile_has_telegram_token(home):
            warnings.append(
                f"profile '{route.profile}' has TELEGRAM_BOT_TOKEN configured; "
                "routed profiles should not also run Telegram polling with the ingress bot token"
            )

    return warnings


RouteSessionMap = dict[tuple[str, str, str], str]


def profile_route_sessions_path(
    *,
    root: Path | None = None,
    path: Path | None = None,
) -> Path:
    """Return the persistent route→child-session map path."""
    if path is not None:
        return path
    base = root or get_default_hermes_root()
    return base / "gateway" / "profile-router-sessions.json"


def load_profile_route_sessions(
    *,
    root: Path | None = None,
    path: Path | None = None,
) -> RouteSessionMap:
    """Load persisted route→child-session mappings.

    The on-disk shape is a list of records instead of stringified tuple keys so
    operators can inspect/edit it without knowing Python repr details.
    Malformed records are ignored; routing can always start fresh.
    """
    session_path = profile_route_sessions_path(root=root, path=path)
    try:
        raw = json.loads(session_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    records = raw.get("sessions") if isinstance(raw, dict) else None
    if not isinstance(records, list):
        return {}

    sessions: RouteSessionMap = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        profile = _as_str(record.get("profile"))
        route = _as_str(record.get("route"))
        gateway_session_key = _as_str(record.get("gateway_session_key"))
        child_session_id = _as_str(record.get("child_session_id"))
        if not (profile and route and gateway_session_key and child_session_id):
            continue
        sessions[(profile, route, gateway_session_key)] = child_session_id
    return sessions


def save_profile_route_sessions(
    sessions: Mapping[tuple[str, str, str], str],
    *,
    root: Path | None = None,
    path: Path | None = None,
) -> None:
    """Persist route→child-session mappings atomically."""
    session_path = profile_route_sessions_path(root=root, path=path)
    session_path.parent.mkdir(parents=True, exist_ok=True)

    records = []
    for key, child_session_id in sorted(sessions.items()):
        if len(key) != 3:
            continue
        profile, route, gateway_session_key = key
        child_session_id = _as_str(child_session_id)
        if not child_session_id:
            continue
        records.append(
            {
                "profile": str(profile),
                "route": str(route),
                "gateway_session_key": str(gateway_session_key),
                "child_session_id": child_session_id,
            }
        )

    payload = {"version": 1, "sessions": records}
    tmp_path = session_path.with_name(f".{session_path.name}.{os.getpid()}.{id(payload)}.tmp")
    try:
        tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp_path.replace(session_path)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def build_profile_subprocess_command(
    *,
    text: str,
    source_tag: str,
    resume: str | None = None,
    image_path: str | None = None,
) -> list[str]:
    """Build the Hermes CLI command used for isolated profile dispatch."""
    executable = shutil.which("hermes")
    if executable:
        cmd = [executable, "chat", "--quiet", "--source", source_tag]
    else:
        cmd = [sys.executable, "-m", "hermes_cli.main", "chat", "--quiet", "--source", source_tag]
    if resume:
        cmd.extend(["--resume", resume])
    if image_path:
        cmd.extend(["--image", image_path])
    cmd.extend(["--query", text])
    return cmd


_SESSION_ID_RE = re.compile(r"(?:Session ID|session_id)[:=]\s*([A-Za-z0-9_.:-]+)")


_SAFE_ENV_EXACT_KEYS = {
    "HOME",
    "LANG",
    "LOGNAME",
    "PATH",
    "SHELL",
    "SSL_CERT_FILE",
    "TERM",
    "TMPDIR",
    "USER",
    "VIRTUAL_ENV",
    "REQUESTS_CA_BUNDLE",
}
_SAFE_ENV_PREFIXES = ("LC_",)


def build_profile_subprocess_env(home: Path, parent_env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return a sanitized environment for a routed profile child process.

    The ingress gateway may have platform tokens and model/provider credentials
    in its process environment. A routed profile should load credentials from
    its own ``HERMES_HOME`` instead of inheriting the gateway's secrets, so this
    function allowlists only basic process/runtime variables and then sets the
    target profile home explicitly.
    """
    source = parent_env if parent_env is not None else os.environ
    env: dict[str, str] = {}
    for key, value in source.items():
        if key in _SAFE_ENV_EXACT_KEYS or key.startswith(_SAFE_ENV_PREFIXES):
            env[key] = value
    env["HERMES_HOME"] = str(home)
    return env


def extract_session_id(output: str) -> str | None:
    """Best-effort extraction of a session id from quiet CLI output."""
    match = _SESSION_ID_RE.search(output or "")
    return match.group(1) if match else None


async def dispatch_to_profile(
    event: Any,
    route: ProfileRoute,
    *,
    root: Path | None = None,
    resume_session_id: str | None = None,
) -> tuple[str, str | None]:
    """Run one message through a target profile in a subprocess.

    Returns ``(response_text, discovered_session_id)``.  The caller owns any
    persistent route→session mapping; this module stays stateless and easy to
    test.
    """
    home = profile_home(route.profile, root=root)
    if not home.exists():
        raise FileNotFoundError(f"Hermes profile '{route.profile}' not found at {home}")

    payload = routed_profile_payload(event, route)
    text = payload.text
    if not text:
        text = " "

    cmd = build_profile_subprocess_command(
        text=text,
        source_tag="telegram-router",
        resume=resume_session_id,
        image_path=payload.image_path,
    )
    env = build_profile_subprocess_env(home)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=route.timeout_seconds)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise TimeoutError(f"Profile '{route.profile}' did not respond within {route.timeout_seconds:g}s")

    stdout = stdout_b.decode("utf-8", errors="replace").strip()
    stderr = stderr_b.decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        detail = stderr or stdout or f"exit code {proc.returncode}"
        raise RuntimeError(f"Profile '{route.profile}' failed: {detail}")

    # Quiet single-query mode prints the final response to stdout and the
    # session_id resume handle to stderr, keeping Telegram replies clean while
    # still letting the router preserve continuity on later turns.
    return stdout, extract_session_id("\n".join([stdout, stderr]))
