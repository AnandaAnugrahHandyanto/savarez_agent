"""Helpers for configurable response brevity styles."""

from __future__ import annotations

VALID_RESPONSE_STYLES = ("normal", "brief", "ultra")

_STYLE_LABELS = {
    "normal": "Normal",
    "brief": "Brief",
    "ultra": "Ultra-brief",
}

_STYLE_RULES = {
    "normal": [
        "Full detail when helpful; no forced compression.",
        "Use normal prose, examples, and structure based on task needs.",
    ],
    "brief": [
        "Lead with the direct answer.",
        "Keep only the most relevant details.",
        "Avoid long preambles, repeated context, and unnecessary step-by-step explanation.",
    ],
    "ultra": [
        "Prefer the shortest useful answer that still completes the task.",
        "Skip preambles and use bullets over prose when possible.",
        "Use fragments or a very short sentence when enough; expand only when the task requires it.",
    ],
}


def normalize_response_style(value: str | None) -> str:
    """Return a normalized response style, defaulting invalid values to normal."""
    normalized = str(value or "").strip().lower()
    if normalized in VALID_RESPONSE_STYLES:
        return normalized
    return "normal"


def describe_response_style(style: str | None, *, auto_clarity: bool = True) -> dict:
    """Return a structured description of the selected response style."""
    normalized = normalize_response_style(style)
    rules = list(_STYLE_RULES[normalized])
    if auto_clarity:
        auto_clarity_note = (
            "Auto-clarity enabled: add the minimum extra context needed when brevity would be confusing, unsafe, or incomplete."
        )
    else:
        auto_clarity_note = "Auto-clarity disabled: keep the selected brevity even if that reduces explanation."

    prompt_defaults = normalized != "normal"
    return {
        "style": normalized,
        "label": _STYLE_LABELS[normalized],
        "rules": rules,
        "auto_clarity": bool(auto_clarity),
        "auto_clarity_note": auto_clarity_note,
        "prompt_defaults": prompt_defaults,
    }


def build_response_style_guidance(style: str | None, *, auto_clarity: bool = True) -> str:
    """Return system-prompt guidance for the selected response style."""
    summary = describe_response_style(style, auto_clarity=auto_clarity)
    if summary["style"] == "normal":
        return ""

    title = {
        "brief": "brief response style",
        "ultra": "ultra-brief",
    }.get(summary["style"], summary["style"].replace("-", " "))
    lines = [f"Response style: {title}."]
    lines.extend(summary["rules"])
    if auto_clarity:
        lines.append(
            "Auto-clarity override: if brevity would make the answer confusing, unsafe, or incomplete, add the minimum extra context needed."
        )
    return "\n".join(lines)


def format_style_status(
    style: str | None,
    *,
    auto_clarity: bool = True,
    prefix: str = "",
    available_styles: tuple[str, ...] | list[str] = VALID_RESPONSE_STYLES,
) -> list[str]:
    """Render human-readable `/style` status lines."""
    summary = describe_response_style(style, auto_clarity=auto_clarity)
    available = tuple(available_styles) or VALID_RESPONSE_STYLES
    lines = [
        f"{prefix}Current response style: {summary['style']} ({summary['label']})",
        f"{prefix}Auto-clarity: {'on' if summary['auto_clarity'] else 'off'}",
        f"{prefix}Available: {', '.join(available)}",
        f"{prefix}Usage: /style <{'|'.join(available)}>",
    ]
    for rule in summary["rules"]:
        lines.append(f"{prefix}  - {rule}")
    lines.append(f"{prefix}  - {summary['auto_clarity_note']}")
    return lines
