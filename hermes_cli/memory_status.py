"""Shared memory status rendering for CLI and `hermes memory status`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hermes_cli.colors import should_use_color
from tools.memory_tool import MemoryStore

_BAR_WIDTH = 24


def build_memory_status_snapshot(
    *,
    provider_name: str = "",
    provider_config: dict[str, Any] | None = None,
    providers: list[tuple[str, str, Any]] | None = None,
) -> dict[str, Any]:
    """Collect built-in memory usage plus optional external provider metadata."""
    store = MemoryStore()
    store.load_from_disk()

    stores = []
    for key, label, file_name, entries, used_chars, char_limit in (
        (
            "memory",
            "Agent memory",
            "MEMORY.md",
            list(store.memory_entries),
            store._char_count("memory"),
            store.memory_char_limit,
        ),
        (
            "user",
            "User profile",
            "USER.md",
            list(store.user_entries),
            store._char_count("user"),
            store.user_char_limit,
        ),
    ):
        pct = _usage_percent(used_chars, char_limit)
        stores.append(
            {
                "key": key,
                "label": label,
                "file_name": file_name,
                "file_path": str(store._path_for(key)),
                "entries": len(entries),
                "used_chars": used_chars,
                "char_limit": char_limit,
                "percent": pct,
                "remaining_chars": max(char_limit - used_chars, 0),
            }
        )

    provider = {
        "name": provider_name or "",
        "installed": False,
        "available": False,
        "description": "",
        "config": provider_config or {},
        "missing": [],
    }

    if provider_name:
        for pname, desc, plugin in providers or []:
            if pname != provider_name:
                continue
            provider["installed"] = True
            provider["description"] = desc or ""
            try:
                provider["available"] = bool(plugin.is_available())
            except Exception:
                provider["available"] = False
            schema = plugin.get_config_schema() if hasattr(plugin, "get_config_schema") else []
            missing = []
            for field in schema or []:
                env_var = str(field.get("env_var") or "").strip()
                if not env_var:
                    continue
                if not field.get("secret") and provider["config"].get(field.get("key")):
                    continue
                import os
                if os.environ.get(env_var):
                    continue
                missing.append(
                    {
                        "env_var": env_var,
                        "url": str(field.get("url") or "").strip(),
                    }
                )
            provider["missing"] = missing
            break

    return {"stores": stores, "provider": provider}


def build_memory_status_lines(snapshot: dict[str, Any], use_color: bool | None = None) -> list[str]:
    """Render a colorful but portable memory dashboard as plain text lines."""
    color_enabled = should_use_color() if use_color is None else use_color
    stores = list(snapshot.get("stores") or [])
    provider = dict(snapshot.get("provider") or {})

    lines = [
        _paint("Memory cockpit  /memory", "title", color_enabled),
        _paint("═" * 72, "dim", color_enabled),
        _paint("Built-in persistent stores", "section", color_enabled),
    ]

    for store in stores:
        used = int(store.get("used_chars") or 0)
        limit = int(store.get("char_limit") or 0)
        pct = int(store.get("percent") or _usage_percent(used, limit) + 0.5)
        entries = int(store.get("entries") or 0)
        file_name = str(store.get("file_name") or "")
        label = str(store.get("label") or store.get("key") or "Memory")
        remaining = int(store.get("remaining_chars") or max(limit - used, 0))
        bar = _progress_bar(pct, color_enabled)

        lines.append(
            f"  {_paint(label, 'label', color_enabled)}  "
            f"{_paint(file_name, 'accent', color_enabled)}  "
            f"{_paint(f'{entries} entr{_plural(entries)}', 'dim', color_enabled)}"
        )
        lines.append(
            f"    {bar} {_paint(f'{pct}%', _tone_for_percent(pct), color_enabled)}  "
            f"{used:,}/{limit:,} chars  {_paint(f'{remaining:,} free', 'dim', color_enabled)}"
        )

    lines.extend(
        [
            "",
            _paint("External memory provider", "section", color_enabled),
            _render_provider_line(provider, color_enabled),
        ]
    )

    if provider.get("config"):
        lines.append(f"  config: {_format_provider_config(provider['config'])}")
    if provider.get("missing"):
        lines.append(f"  missing: {_format_missing(provider['missing'])}")

    lines.extend(
        [
            "",
            _paint("Tip: use /memory anytime to check how full MEMORY.md and USER.md are.", "dim", color_enabled),
        ]
    )
    return lines


def _render_provider_line(provider: dict[str, Any], color_enabled: bool) -> str:
    name = str(provider.get("name") or "").strip()
    if not name:
        return f"  {_paint('built-in only', 'dim', color_enabled)}"

    installed = bool(provider.get("installed"))
    available = bool(provider.get("available"))
    installed_text = _paint("installed", "good" if installed else "bad", color_enabled)
    available_text = _paint("available", "good" if available else "warn", color_enabled)
    description = str(provider.get("description") or "").strip()
    suffix = f" — {description}" if description else ""
    return f"  {_paint(name, 'accent', color_enabled)}  {installed_text}, {available_text}{suffix}"


def _format_provider_config(config: dict[str, Any]) -> str:
    parts = []
    for key, value in sorted(config.items()):
        text = str(value)
        if len(text) > 36:
            text = text[:33] + "..."
        parts.append(f"{key}={text}")
    return ", ".join(parts)


def _format_missing(missing: list[dict[str, str]]) -> str:
    bits = []
    for item in missing:
        env_var = item.get("env_var") or "?"
        url = item.get("url") or ""
        bits.append(f"{env_var} ({url})" if url else env_var)
    return ", ".join(bits)


def _progress_bar(percent: int, color_enabled: bool) -> str:
    percent = max(0, min(100, int(percent)))
    filled = round((_BAR_WIDTH * percent) / 100)
    bar = "[" + ("█" * filled) + ("░" * (_BAR_WIDTH - filled)) + "]"
    return _paint(bar, _tone_for_percent(percent), color_enabled)


def _tone_for_percent(percent: int) -> str:
    if percent >= 90:
        return "bad"
    if percent >= 70:
        return "warn"
    return "good"


def _usage_percent(used_chars: int, char_limit: int) -> float:
    if char_limit <= 0:
        return 0.0
    return round((used_chars / char_limit) * 100, 1)


def _plural(value: int) -> str:
    return "y" if value == 1 else "ies"


def _paint(text: str, tone: str, color_enabled: bool) -> str:
    if not color_enabled:
        return text
    code = {
        "title": "\x1b[1;38;5;45m",
        "section": "\x1b[1;38;5;117m",
        "label": "\x1b[1;37m",
        "accent": "\x1b[1;36m",
        "good": "\x1b[1;32m",
        "warn": "\x1b[1;33m",
        "bad": "\x1b[1;31m",
        "dim": "\x1b[2;37m",
    }.get(tone, "")
    if not code:
        return text
    return f"{code}{text}\x1b[0m"
