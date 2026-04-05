"""Per-skill performance tracking from implicit signals and usage data.

Aggregates implicit_signals (skill_match type) to produce a ranked view of
skill health. Used by the self-evolution pipeline to prioritize which skills
to evolve first (lowest-performing, most-used).

Usage:
    from agent.skill_performance import SkillPerformanceTracker
    tracker = SkillPerformanceTracker(db)
    report = tracker.generate_report(days=30)
    weakest = tracker.get_weakest_skills(top_n=3)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SkillMetrics:
    """Aggregated performance metrics for a single skill."""
    skill_name: str
    total_suggestions: int = 0
    total_usages: int = 0
    total_skips: int = 0
    avg_signal_value: float = 0.0
    usage_rate: float = 0.0  # usages / suggestions

    @property
    def performance_score(self) -> float:
        """Composite score 0.0-1.0 (higher = better performing).

        Weighs actual usage more heavily than mere suggestion.
        """
        if self.total_suggestions == 0:
            return 0.5  # Unknown — neutral

        self.usage_rate = self.total_usages / self.total_suggestions
        # Combine usage rate and average signal quality
        score = self.usage_rate * 0.6 + self.avg_signal_value * 0.4
        return max(0.0, min(1.0, score))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "total_suggestions": self.total_suggestions,
            "total_usages": self.total_usages,
            "total_skips": self.total_skips,
            "avg_signal_value": round(self.avg_signal_value, 3),
            "usage_rate": round(self.usage_rate, 3),
            "performance_score": round(self.performance_score, 3),
        }


class SkillPerformanceTracker:
    """Aggregates implicit signals into per-skill performance metrics."""

    def __init__(self, db: Any):
        self._db = db

    def generate_report(self, days: int = 30) -> Dict[str, SkillMetrics]:
        """Generate per-skill performance report from implicit signals.

        Returns dict mapping skill_name to SkillMetrics.
        """
        signals = self._db.get_implicit_signals("skill_match", limit=10000)

        cutoff = time.time() - (days * 86400)
        recent_signals = [
            s for s in signals
            if (s.get("created_at") or 0) >= cutoff
        ]

        # Aggregate by skill name (context_id holds the skill name)
        metrics: Dict[str, SkillMetrics] = {}

        for sig in recent_signals:
            skill_name = sig.get("context_id", "unknown")
            if skill_name not in metrics:
                metrics[skill_name] = SkillMetrics(skill_name=skill_name)

            m = metrics[skill_name]
            m.total_suggestions += 1

            value = sig.get("signal_value", 0.0)
            source = sig.get("signal_source", "")

            if source == "implicit_usage":
                m.total_usages += 1
            elif source == "implicit_skip":
                m.total_skips += 1

            # Running average of signal values
            old_avg = m.avg_signal_value
            m.avg_signal_value = old_avg + (value - old_avg) / m.total_suggestions

        return metrics

    def get_weakest_skills(
        self,
        top_n: int = 3,
        min_suggestions: int = 5,
        days: int = 30,
    ) -> List[SkillMetrics]:
        """Return the weakest-performing skills (candidates for evolution).

        Only considers skills with enough suggestions to be statistically meaningful.
        """
        report = self.generate_report(days=days)

        candidates = [
            m for m in report.values()
            if m.total_suggestions >= min_suggestions
        ]

        candidates.sort(key=lambda m: m.performance_score)
        return candidates[:top_n]

    def get_most_used_skills(
        self,
        top_n: int = 10,
        days: int = 30,
    ) -> List[SkillMetrics]:
        """Return skills by total usage count (most active first)."""
        report = self.generate_report(days=days)

        skills = list(report.values())
        skills.sort(key=lambda m: m.total_usages, reverse=True)
        return skills[:top_n]

    def format_report(self, days: int = 30) -> str:
        """Generate a human-readable skill performance report."""
        report = self.generate_report(days=days)

        if not report:
            return "No skill performance data available yet."

        lines = [f"Skill Performance Report (last {days} days)", "=" * 50]
        sorted_skills = sorted(report.values(), key=lambda m: m.performance_score)

        for m in sorted_skills:
            lines.append(
                f"  {m.skill_name:30s}  score={m.performance_score:.2f}  "
                f"used={m.total_usages}/{m.total_suggestions}  "
                f"skipped={m.total_skips}"
            )

        weakest = self.get_weakest_skills(top_n=3, days=days)
        if weakest:
            lines.append("")
            lines.append("Candidates for evolution (weakest):")
            for m in weakest:
                lines.append(f"  - {m.skill_name} (score={m.performance_score:.2f})")

        return "\n".join(lines)
