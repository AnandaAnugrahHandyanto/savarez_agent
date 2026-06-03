"""Run-scoped external-write budget ledger prototype.

This module is intentionally standalone for the first prototype: it gives tool
surfaces a common taxonomy and a deterministic in-memory ledger, but it does not
wire enforcement into live tools yet. The next integration step is to call
``record_surface_write()`` immediately before side-effecting operations such as
``send_message`` delivery or ``cronjob(create/update/remove/run)``.

No upstream RuVector/rvAgent code is imported here; this is a Hermes-native
Python model inspired only by the first-class external-write-budget pattern.

Provenance: pattern source RuVector/rvAgent BudgetEnforcer at upstream commit
``c2089c4e4880c0d2b1f5632043daea6535f4a534`` (public GitHub source;
license/import risk assessed in parent design note
``/home/filip/spearhead-execution/20260529-source-spikes/ruvnet-ruvector/hermes-adoption-design-note.md``).
Adapted: category/counter/check-before-write idea only. Not adopted: Rust code,
upstream prompts, hooks, MCP configs, generated bundles, workflows, or unsafe
automation snippets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Mapping


class ExternalWriteBudgetError(RuntimeError):
    """Raised when an external write would exceed the configured budget."""


# Initial ledger taxonomy for exact Hermes side-effect surfaces.
#
# Categories are policy-level buckets. ``SURFACE_TAXONOMY`` maps concrete Hermes
# tools/actions to those buckets so integration can be incremental and testable.
EXTERNAL_WRITE_CATEGORIES: tuple[str, ...] = (
    "public_send",
    "cron_mutation",
    "notion_write",
    "profile_skill_mutation",
    "profile_memory_mutation",
    "profile_config_mutation",
    "filesystem_durable_write",
    "kanban_mutation",
    "paid_api",
    "deploy_push_merge",
)

SURFACE_TAXONOMY: dict[str, str] = {
    # Public/user-visible sends.
    "send_message:send": "public_send",
    "gateway:auto_deliver": "public_send",
    "text_to_speech:deliver_media": "public_send",
    "image_generate:deliver_media": "public_send",
    "video_generate:deliver_media": "public_send",
    # Scheduler mutations and forced runs.
    "cronjob:create": "cron_mutation",
    "cronjob:update": "cron_mutation",
    "cronjob:pause": "cron_mutation",
    "cronjob:resume": "cron_mutation",
    "cronjob:remove": "cron_mutation",
    "cronjob:run": "cron_mutation",
    # Notion/Feishu/Google-style durable workspace writes. Notion is a policy
    # category even when provided by skills/plugins rather than a builtin tool.
    "notion:page_write": "notion_write",
    "notion:database_write": "notion_write",
    "notion:comment_write": "notion_write",
    # Profile-scoped prompt/state mutation.
    "skill_manage:create": "profile_skill_mutation",
    "skill_manage:patch": "profile_skill_mutation",
    "skill_manage:edit": "profile_skill_mutation",
    "skill_manage:delete": "profile_skill_mutation",
    "skill_manage:write_file": "profile_skill_mutation",
    "skill_manage:remove_file": "profile_skill_mutation",
    "memory:add": "profile_memory_mutation",
    "memory:replace": "profile_memory_mutation",
    "memory:remove": "profile_memory_mutation",
    "config:set": "profile_config_mutation",
    "tools:enable_disable": "profile_config_mutation",
    # Durable filesystem/profile writes.
    "write_file": "filesystem_durable_write",
    "patch": "filesystem_durable_write",
    "terminal:durable_filesystem_write": "filesystem_durable_write",
    # Board state changes. Non-destructive comments/completions can use their
    # own lower caps; destructive archival/removal belongs behind approval.
    "kanban:create": "kanban_mutation",
    "kanban:comment": "kanban_mutation",
    "kanban:block": "kanban_mutation",
    "kanban:complete": "kanban_mutation",
    "kanban:link": "kanban_mutation",
    "kanban:destructive": "kanban_mutation",
    # Cost/prod policy categories; usually approval-gated above this ledger.
    "paid_api:call": "paid_api",
    "deploy:execute": "deploy_push_merge",
    "git:push": "deploy_push_merge",
    "github:merge": "deploy_push_merge",
}


@dataclass(frozen=True)
class ExternalWriteDecision:
    """Decision returned by a budget check or record operation."""

    allowed: bool
    category: str
    surface: str
    used: int
    limit: int | None
    reason: str | None = None
    target_digest: str | None = None


@dataclass
class ExternalWriteBudgetLedger:
    """In-memory run-scoped ledger for external side-effect writes.

    ``limits`` maps category -> maximum allowed writes for the run. A missing
    category means unlimited for prototype/backwards-compatible call sites;
    pass ``0`` for autonomous runs or high-risk categories that should fail
    closed. Counters are incremented only on allowed records.
    """

    limits: Mapping[str, int | None] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    events: list[ExternalWriteDecision] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Snapshot caller-provided mappings so later external mutation cannot
        # change enforcement mid-run.
        self.limits = dict(self.limits)
        unknown = set(self.limits) - set(EXTERNAL_WRITE_CATEGORIES)
        if unknown:
            unknown_list = ", ".join(sorted(unknown))
            raise ValueError(f"Unknown external-write budget categories: {unknown_list}")
        for category, limit in self.limits.items():
            if limit is not None and limit < 0:
                raise ValueError(f"Budget limit for {category!r} must be >= 0 or None")

    def check(self, category: str, *, surface: str, target: str | None = None) -> ExternalWriteDecision:
        """Return whether the next write in ``category`` would be allowed."""

        self._validate_category(category)
        used = self.counts.get(category, 0)
        limit = self.limits.get(category)
        target_digest = _target_digest(target)
        if limit is not None and used >= limit:
            return ExternalWriteDecision(
                allowed=False,
                category=category,
                surface=surface,
                used=used,
                limit=limit,
                reason=(
                    f"external-write budget exceeded for {category}: "
                    f"used {used}/{limit} before {surface}"
                ),
                target_digest=target_digest,
            )
        return ExternalWriteDecision(
            allowed=True,
            category=category,
            surface=surface,
            used=used,
            limit=limit,
            target_digest=target_digest,
        )

    def record(self, category: str, *, surface: str, target: str | None = None) -> ExternalWriteDecision:
        """Record one write or raise ``ExternalWriteBudgetError`` if capped."""

        decision = self.check(category, surface=surface, target=target)
        if not decision.allowed:
            self.events.append(decision)
            raise ExternalWriteBudgetError(decision.reason or "external-write budget exceeded")

        new_used = decision.used + 1
        self.counts[category] = new_used
        recorded = ExternalWriteDecision(
            allowed=True,
            category=category,
            surface=surface,
            used=new_used,
            limit=decision.limit,
            target_digest=decision.target_digest,
        )
        self.events.append(recorded)
        return recorded

    def check_surface_write(self, surface: str, *, target: str | None = None) -> ExternalWriteDecision:
        """Check a concrete Hermes surface by taxonomy key."""

        category = category_for_surface(surface)
        return self.check(category, surface=surface, target=target)

    def record_surface_write(self, surface: str, *, target: str | None = None) -> ExternalWriteDecision:
        """Record a concrete Hermes surface by taxonomy key."""

        category = category_for_surface(surface)
        return self.record(category, surface=surface, target=target)

    @property
    def snapshot(self) -> dict[str, dict[str, int | None]]:
        """Return redaction-safe counters for progress/session telemetry."""

        return {
            category: {"used": self.counts.get(category, 0), "limit": self.limits.get(category)}
            for category in EXTERNAL_WRITE_CATEGORIES
            if self.counts.get(category, 0) or category in self.limits
        }

    @staticmethod
    def _validate_category(category: str) -> None:
        if category not in EXTERNAL_WRITE_CATEGORIES:
            raise ValueError(f"Unknown external-write budget category: {category}")


def category_for_surface(surface: str) -> str:
    """Resolve a concrete Hermes side-effect surface to a budget category."""

    try:
        return SURFACE_TAXONOMY[surface]
    except KeyError as exc:
        raise ValueError(f"Unknown external-write surface: {surface}") from exc


def _target_digest(target: str | None) -> str | None:
    """Return a stable redacted target digest; never persist raw target text."""

    if not target:
        return None
    return "sha256:" + sha256(target.encode("utf-8", errors="surrogatepass")).hexdigest()[:16]
