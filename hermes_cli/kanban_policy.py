"""Kanban worker policy helpers.

This module is intentionally small and dependency-light so both the agent
prompt builder and the dispatcher can share one normalized view of Kanban
code-review behavior.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any, Mapping


TRUE_STRINGS = {"1", "true", "yes", "on"}
FALSE_STRINGS = {"0", "false", "no", "off"}

VALID_REVIEW_MODES = {"ai_reviewer", "self_verify", "human_review"}
VALID_PERMISSION_MODES = {"default", "ask", "deny"}


@dataclass(frozen=True)
class KanbanCodeReviewPolicy:
    """Normalized policy controlling coding-task completion/review behavior."""

    mode: str = "ai_reviewer"
    reviewer_profile: str = "reviewer"
    require_for_coding_tasks: bool = True
    human_blocks_for_code_review: bool = False
    permission_mode: str = "default"


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in TRUE_STRINGS:
            return True
        if lowered in FALSE_STRINGS:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def normalize_kanban_code_review_policy(
    raw: KanbanCodeReviewPolicy | Mapping[str, Any] | None = None,
) -> KanbanCodeReviewPolicy:
    """Return a valid policy from user config, falling back per-field.

    Unknown modes deliberately fall back to the default agent-review path
    rather than disabling review or routing technical review to humans.
    """

    if isinstance(raw, KanbanCodeReviewPolicy):
        return raw
    cfg = raw if isinstance(raw, Mapping) else {}

    mode = str(cfg.get("mode", KanbanCodeReviewPolicy.mode)).strip().lower()
    if mode not in VALID_REVIEW_MODES:
        mode = KanbanCodeReviewPolicy.mode

    reviewer_profile = str(
        cfg.get("reviewer_profile", KanbanCodeReviewPolicy.reviewer_profile)
    ).strip()
    if not reviewer_profile:
        reviewer_profile = KanbanCodeReviewPolicy.reviewer_profile

    permission_mode = str(
        cfg.get("permission_mode", KanbanCodeReviewPolicy.permission_mode)
    ).strip().lower()
    if permission_mode not in VALID_PERMISSION_MODES:
        permission_mode = KanbanCodeReviewPolicy.permission_mode

    return KanbanCodeReviewPolicy(
        mode=mode,
        reviewer_profile=reviewer_profile,
        require_for_coding_tasks=_coerce_bool(
            cfg.get(
                "require_for_coding_tasks",
                KanbanCodeReviewPolicy.require_for_coding_tasks,
            ),
            KanbanCodeReviewPolicy.require_for_coding_tasks,
        ),
        human_blocks_for_code_review=_coerce_bool(
            cfg.get(
                "human_blocks_for_code_review",
                KanbanCodeReviewPolicy.human_blocks_for_code_review,
            ),
            KanbanCodeReviewPolicy.human_blocks_for_code_review,
        ),
        permission_mode=permission_mode,
    )


def policy_from_config(config: Mapping[str, Any] | None) -> KanbanCodeReviewPolicy:
    """Extract and normalize ``kanban.code_review`` from a config mapping."""

    if not isinstance(config, Mapping):
        return normalize_kanban_code_review_policy()
    kanban = config.get("kanban", {})
    if not isinstance(kanban, Mapping):
        return normalize_kanban_code_review_policy()
    code_review = kanban.get("code_review", {})
    if not isinstance(code_review, Mapping):
        return normalize_kanban_code_review_policy()
    return normalize_kanban_code_review_policy(code_review)


def policy_from_env(
    env: Mapping[str, str] | None = None,
    *,
    base_policy: KanbanCodeReviewPolicy | Mapping[str, Any] | None = None,
) -> KanbanCodeReviewPolicy:
    """Return policy with dispatcher-provided env vars overriding config.

    The gateway dispatcher can run under a shared/root profile while spawned
    workers run under assignee profiles. Passing the normalized policy through
    env keeps board-level worker behavior consistent without requiring every
    profile to duplicate ``kanban.code_review`` config.
    """

    raw: dict[str, Any] = asdict(normalize_kanban_code_review_policy(base_policy))
    env = os.environ if env is None else env
    env_map = {
        "HERMES_KANBAN_CODE_REVIEW_MODE": "mode",
        "HERMES_KANBAN_REVIEWER_PROFILE": "reviewer_profile",
        "HERMES_KANBAN_REQUIRE_CODE_REVIEW": "require_for_coding_tasks",
        "HERMES_KANBAN_HUMAN_CODE_REVIEW_BLOCKS": "human_blocks_for_code_review",
        "HERMES_KANBAN_PERMISSION_MODE": "permission_mode",
    }
    for env_key, policy_key in env_map.items():
        if env_key in env:
            raw[policy_key] = env[env_key]
    return normalize_kanban_code_review_policy(raw)


def load_kanban_code_review_policy() -> KanbanCodeReviewPolicy:
    """Load the active profile's Kanban code-review policy.

    Config loading is optional by design: prompt construction and dispatcher
    spawn must stay robust even if config parsing fails.
    """

    try:
        from hermes_cli.config import load_config

        return policy_from_config(load_config())
    except Exception:
        return normalize_kanban_code_review_policy()


def kanban_policy_env(
    policy: KanbanCodeReviewPolicy | Mapping[str, Any] | None = None,
) -> dict[str, str]:
    """Serialize policy into worker env vars for subprocess consumers/logging."""

    if not isinstance(policy, KanbanCodeReviewPolicy):
        policy = normalize_kanban_code_review_policy(policy)
    return {
        "HERMES_KANBAN_CODE_REVIEW_MODE": policy.mode,
        "HERMES_KANBAN_REVIEWER_PROFILE": policy.reviewer_profile,
        "HERMES_KANBAN_REQUIRE_CODE_REVIEW": str(
            policy.require_for_coding_tasks
        ).lower(),
        "HERMES_KANBAN_HUMAN_CODE_REVIEW_BLOCKS": str(
            policy.human_blocks_for_code_review
        ).lower(),
        "HERMES_KANBAN_PERMISSION_MODE": policy.permission_mode,
    }
