"""Opt-in budget guard for unattended Hermes runs.

The guard is intentionally small and dependency-free: when config.yaml has no
``budget`` section it is a no-op; when caps are configured, callers can check the
currently known spend estimate before starting another model call.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class BudgetCaps:
    daily_usd_cap: Optional[float] = None
    monthly_usd_cap: Optional[float] = None

    @property
    def enabled(self) -> bool:
        return (self.daily_usd_cap or 0) > 0 or (self.monthly_usd_cap or 0) > 0


class BudgetExceededError(RuntimeError):
    """Raised when a configured budget cap has already been reached."""


def _parse_positive_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def load_budget_caps(config: Optional[Mapping[str, Any]] = None) -> BudgetCaps:
    """Load daily/monthly budget caps from Hermes config.

    Supported config shape::

        budget:
          daily_usd_cap: 50.0
          monthly_usd_cap: 500.0
    """
    if config is None:
        try:
            from hermes_cli.config import load_config

            config = load_config()
        except Exception:
            config = {}
    budget = config.get("budget") if isinstance(config, Mapping) else None
    if not isinstance(budget, Mapping):
        return BudgetCaps()
    return BudgetCaps(
        daily_usd_cap=_parse_positive_float(budget.get("daily_usd_cap")),
        monthly_usd_cap=_parse_positive_float(budget.get("monthly_usd_cap")),
    )


def check_budget_caps(
    *,
    current_spend_usd: float,
    caps: Optional[BudgetCaps] = None,
    config: Optional[Mapping[str, Any]] = None,
) -> None:
    """Raise BudgetExceededError if known spend is already at a configured cap."""
    caps = caps or load_budget_caps(config)
    if not caps.enabled:
        return
    spend = max(0.0, float(current_spend_usd or 0.0))
    violations: list[str] = []
    if caps.daily_usd_cap and spend >= caps.daily_usd_cap:
        violations.append(f"daily cap ${caps.daily_usd_cap:.2f}")
    if caps.monthly_usd_cap and spend >= caps.monthly_usd_cap:
        violations.append(f"monthly cap ${caps.monthly_usd_cap:.2f}")
    if violations:
        joined = " and ".join(violations)
        raise BudgetExceededError(
            f"Budget cap reached: current estimated spend is ${spend:.2f}, "
            f"which meets or exceeds the configured {joined}. Refusing to start "
            "another model call. Raise or remove budget.*_usd_cap in config.yaml "
            "to continue."
        )


def enforce_configured_budget(current_spend_usd: float) -> None:
    """Convenience wrapper for model-call preflight sites."""
    check_budget_caps(current_spend_usd=current_spend_usd)
