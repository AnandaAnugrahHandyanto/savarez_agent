"""Gateway runtime-metadata footer and compact runtime prefix.

Renders a compact footer showing runtime state (model, context %, cwd) and
appends it to the FINAL message of an agent turn when enabled.  Off by default
to keep replies minimal.

The optional runtime prefix prepends a compact model tag to the FINAL message,
e.g. ``[gpt5.5] Done``.  It is also off by default and supports global and
per-platform label maps for short human-friendly model names.

Config (``~/.hermes/config.yaml``)::

    display:
      runtime_footer:
        enabled: true                       # off by default
        fields: [model, context_pct, cwd]   # order shown; drop any to hide
      runtime_prefix:
        enabled: true                       # off by default
        labels:
          gpt-5.5: "[gpt5.5]"

Per-platform overrides live under ``display.platforms.<platform>.runtime_footer``
and ``display.platforms.<platform>.runtime_prefix``. Users can toggle the global
footer setting with ``/footer on|off`` from both the CLI and any gateway platform.

The footer is appended to the final response text in ``gateway/run.py`` right
before returning the response to the adapter send path — so it only lands on
the final message a user sees, not on tool-progress updates or streaming
partials.  When streaming is on and the final text has already been delivered
piecemeal, the footer is sent as a separate trailing message via
``send_trailing_footer()``.
"""

from __future__ import annotations

import os
import re
from typing import Any, Iterable, Optional

_DEFAULT_FIELDS: tuple[str, ...] = ("model", "context_pct", "cwd")
_DEFAULT_PREFIX_MAP: dict[str, str] = {}
_SEP = " · "


def _home_relative_cwd(cwd: str) -> str:
    """Return *cwd* with ``$HOME`` collapsed to ``~``.  Empty string if unset."""
    if not cwd:
        return ""
    try:
        home = os.path.expanduser("~")
        p = os.path.abspath(cwd)
        if home and (p == home or p.startswith(home + os.sep)):
            return "~" + p[len(home):]
        return p
    except Exception:
        return cwd


def _model_short(model: Optional[str]) -> str:
    """Drop ``vendor/`` prefix for readability (``openai/gpt-5.4`` → ``gpt-5.4``)."""
    if not model:
        return ""
    return model.rsplit("/", 1)[-1]


def resolve_footer_config(
    user_config: dict[str, Any] | None,
    platform_key: str | None = None,
) -> dict[str, Any]:
    """Resolve effective runtime-footer config for *platform_key*.

    Merge order (later wins):
        1. Built-in defaults (enabled=False)
        2. ``display.runtime_footer``
        3. ``display.platforms.<platform_key>.runtime_footer``
    """
    resolved = {"enabled": False, "fields": list(_DEFAULT_FIELDS)}
    cfg = (user_config or {}).get("display") or {}

    global_cfg = cfg.get("runtime_footer")
    if isinstance(global_cfg, dict):
        if "enabled" in global_cfg:
            resolved["enabled"] = bool(global_cfg.get("enabled"))
        if isinstance(global_cfg.get("fields"), list) and global_cfg["fields"]:
            resolved["fields"] = [str(f) for f in global_cfg["fields"]]

    if platform_key:
        platforms = cfg.get("platforms") or {}
        plat_cfg = platforms.get(platform_key)
        if isinstance(plat_cfg, dict):
            plat_footer = plat_cfg.get("runtime_footer")
            if isinstance(plat_footer, dict):
                if "enabled" in plat_footer:
                    resolved["enabled"] = bool(plat_footer.get("enabled"))
                if isinstance(plat_footer.get("fields"), list) and plat_footer["fields"]:
                    resolved["fields"] = [str(f) for f in plat_footer["fields"]]

    return resolved


def resolve_prefix_config(
    user_config: dict[str, Any] | None,
    platform_key: str | None = None,
) -> dict[str, Any]:
    """Resolve effective compact runtime-prefix config for *platform_key*.

    Merge order mirrors :func:`resolve_footer_config`:
        1. Built-in defaults (enabled=False)
        2. ``display.runtime_prefix``
        3. ``display.platforms.<platform_key>.runtime_prefix``
    """
    resolved: dict[str, Any] = {"enabled": False, "labels": dict(_DEFAULT_PREFIX_MAP)}
    cfg = (user_config or {}).get("display") or {}

    def _apply(prefix_cfg: Any) -> None:
        if not isinstance(prefix_cfg, dict):
            return
        if "enabled" in prefix_cfg:
            resolved["enabled"] = bool(prefix_cfg.get("enabled"))
        labels = prefix_cfg.get("labels") or prefix_cfg.get("map") or prefix_cfg.get("markers")
        if isinstance(labels, dict):
            merged = dict(resolved.get("labels") or {})
            for key, value in labels.items():
                k = str(key).strip().lower()
                v = str(value).strip()
                if k and v:
                    merged[k] = v
            resolved["labels"] = merged

    _apply(cfg.get("runtime_prefix"))

    if platform_key:
        platforms = cfg.get("platforms") or {}
        plat_cfg = platforms.get(platform_key)
        if isinstance(plat_cfg, dict):
            _apply(plat_cfg.get("runtime_prefix"))

    return resolved


def format_runtime_prefix(
    *,
    model: Optional[str],
    labels: dict[str, str] | None = None,
) -> str:
    """Return a compact marker for *model*, or ``""`` when no model is known."""
    short = _model_short(model)
    if not short:
        return ""
    mapping = labels or _DEFAULT_PREFIX_MAP
    model_l = str(model or "").lower()
    short_l = short.lower()
    for needle in sorted(mapping, key=len, reverse=True):
        key = str(needle).strip().lower()
        if key and (key in model_l or short_l.startswith(key)):
            return _normalize_prefix_marker(mapping[needle])
    return f"[{short}]"


def _normalize_prefix_marker(value: Any) -> str:
    """Return a compact, single-line bracket marker for configured labels.

    Runtime prefix values are user-configurable, but downstream gateway logic
    treats them as small first-line markers. Normalizing to ``[label]`` keeps
    custom labels compact and strips multiline/control/mention punctuation so
    arbitrary platform mentions cannot be prepended to every gateway reply.
    """
    marker = str(value).strip().splitlines()[0].strip() if value is not None else ""
    if not marker:
        return ""
    marker = marker[:64].strip()
    if marker.startswith("[") and marker.endswith("]"):
        marker = marker[1:-1].strip()
    else:
        marker = marker.strip("[]").strip()
    marker = re.sub(r"[^\w .:/+-]", "", marker).strip()
    return f"[{marker}]" if marker else ""


def build_prefix_line(
    *,
    user_config: dict[str, Any] | None,
    platform_key: str | None,
    model: Optional[str],
) -> str:
    """Top-level entry point used by gateway/run.py for model prefix markers."""
    cfg = resolve_prefix_config(user_config, platform_key)
    if not cfg.get("enabled"):
        return ""
    labels = cfg.get("labels") if isinstance(cfg.get("labels"), dict) else None
    return format_runtime_prefix(model=model, labels=labels)


def apply_runtime_prefix(response: str, prefix: str) -> str:
    """Prepend *prefix* once to a final gateway response."""
    if not response or not prefix:
        return response
    stripped = response.lstrip()
    if stripped.startswith(prefix):
        return response
    leading = response[: len(response) - len(stripped)]
    return f"{leading}{prefix} {stripped}"


def format_runtime_footer(
    *,
    model: Optional[str],
    context_tokens: int,
    context_length: Optional[int],
    cwd: Optional[str] = None,
    fields: Iterable[str] = _DEFAULT_FIELDS,
) -> str:
    """Render the footer line, or return "" if no fields have data.

    Fields are skipped silently when their underlying data is missing — a
    partially-populated footer is better than a line with ``?%`` or empty slots.
    """
    parts: list[str] = []
    for field in fields:
        if field == "model":
            m = _model_short(model)
            if m:
                parts.append(m)
        elif field == "context_pct":
            if context_length and context_length > 0 and context_tokens >= 0:
                pct = max(0, min(100, round((context_tokens / context_length) * 100)))
                parts.append(f"{pct}%")
        elif field == "cwd":
            rel = _home_relative_cwd(cwd or os.environ.get("TERMINAL_CWD", ""))
            if rel:
                parts.append(rel)
        # Unknown field names are silently ignored.

    if not parts:
        return ""
    return _SEP.join(parts)


def build_footer_line(
    *,
    user_config: dict[str, Any] | None,
    platform_key: str | None,
    model: Optional[str],
    context_tokens: int,
    context_length: Optional[int],
    cwd: Optional[str] = None,
) -> str:
    """Top-level entry point used by gateway/run.py.

    Returns the footer text (empty string when disabled or no data).  Callers
    append this to the final response themselves, preserving a single blank
    line of separation.
    """
    cfg = resolve_footer_config(user_config, platform_key)
    if not cfg.get("enabled"):
        return ""
    return format_runtime_footer(
        model=model,
        context_tokens=context_tokens,
        context_length=context_length,
        cwd=cwd,
        fields=cfg.get("fields") or _DEFAULT_FIELDS,
    )
