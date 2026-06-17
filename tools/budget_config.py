"""Configurable budget constants for tool result persistence.

Per-tool resolution: pinned > config overrides > registry > default.
"""

from dataclasses import dataclass, field
from typing import Any, Dict

# Tools whose thresholds must never be overridden.
# read_file=inf prevents infinite persist->read->persist loops.
PINNED_THRESHOLDS: Dict[str, float] = {
    "read_file": float("inf"),
}

# Defaults matching the current hardcoded values in tool_result_storage.py.
# Kept here as the single source of truth; tool_result_storage.py imports these.
DEFAULT_RESULT_SIZE_CHARS: int = 100_000
DEFAULT_TURN_BUDGET_CHARS: int = 200_000
DEFAULT_PREVIEW_SIZE_CHARS: int = 1_500


@dataclass(frozen=True)
class BudgetConfig:
    """Immutable budget constants for the 3-layer tool result persistence system.

    Layer 2 (per-result): resolve_threshold(tool_name) -> threshold in chars.
    Layer 3 (per-turn):   turn_budget -> aggregate char budget across all tool
                          results in a single assistant turn.
    Preview:              preview_size -> inline snippet size after persistence.
    """

    default_result_size: int = DEFAULT_RESULT_SIZE_CHARS
    turn_budget: int = DEFAULT_TURN_BUDGET_CHARS
    preview_size: int = DEFAULT_PREVIEW_SIZE_CHARS
    tool_overrides: Dict[str, int] = field(default_factory=dict)

    def resolve_threshold(self, tool_name: str) -> int | float:
        """Resolve the persistence threshold for a tool.

        Priority: pinned -> tool_overrides -> registry per-tool -> default.
        """
        if tool_name in PINNED_THRESHOLDS:
            return PINNED_THRESHOLDS[tool_name]
        if tool_name in self.tool_overrides:
            return self.tool_overrides[tool_name]
        from tools.registry import registry
        return registry.get_max_result_size(tool_name, default=self.default_result_size)


def _positive_int(value: Any, default: int) -> int:
    """Return ``value`` as a positive int, else ``default``."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def budget_config_from_mapping(config: dict[str, Any] | None) -> BudgetConfig:
    """Build tool-result budget settings from ``config.yaml`` data.

    User-facing config lives at::

        tools:
          result_budget:
            default_result_size: 50000
            turn_budget: 120000
            preview_size: 1500
            tool_overrides:
              terminal: 25000

    Invalid values are ignored so a typo cannot disable persistence. Pinned
    thresholds such as ``read_file`` still win at ``resolve_threshold`` time.
    """
    root = config or {}
    section = ((root.get("tools") or {}).get("result_budget") or {})
    if not isinstance(section, dict):
        section = {}

    overrides_raw = section.get("tool_overrides") or {}
    overrides: Dict[str, int] = {}
    if isinstance(overrides_raw, dict):
        for name, value in overrides_raw.items():
            if not isinstance(name, str) or not name:
                continue
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                overrides[name] = parsed

    return BudgetConfig(
        default_result_size=_positive_int(
            section.get("default_result_size"), DEFAULT_RESULT_SIZE_CHARS,
        ),
        turn_budget=_positive_int(
            section.get("turn_budget"), DEFAULT_TURN_BUDGET_CHARS,
        ),
        preview_size=_positive_int(
            section.get("preview_size"), DEFAULT_PREVIEW_SIZE_CHARS,
        ),
        tool_overrides=overrides,
    )


# Default config -- matches current hardcoded behavior exactly.
DEFAULT_BUDGET = BudgetConfig()
