"""Feishu permission gate model — two-layer access control for Hermes.

Layer 1: Global allowlist (FEISHU_ALLOWED_USERS env var).
    Controls which users can interact with the bot at all.

Layer 2: Per-group policy.
    Controls which users can interact within specific group chats.
    Policies: "open" | "allowlist" | "blacklist" | "admin_only" | "disabled"

This module is advisory input only. It does not modify routing or policy
execution. It provides check() results that the Feishu transport can use
to accept or reject messages.

The actual enforcement point in feishu.py is the existing
_check_sender_allowed() method. This module provides structured data
for that method and for future dashboard display.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Literal

from .entry_event import EntryEvent

# Layer 1: Global allowlist
# If FEISHU_ALLOWED_USERS is empty or "*", all users are allowed.
# Otherwise, only listed open_ids can interact.

# Layer 2: Per-group policy
# "open" = all users in the group
# "allowlist" = only listed users
# "blacklist" = all except listed users
# "admin_only" = only admin users
# "disabled" = no one in this group

GroupPolicy = Literal["open", "allowlist", "blacklist", "admin_only", "disabled"]


@dataclass(frozen=True, slots=True)
class PermissionCheckResult:
    """Result of a permission gate check."""
    allowed: bool
    reason: str
    layer: Literal["global", "group", "disabled", "unknown"] = "unknown"
    policy: GroupPolicy | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "layer": self.layer,
            "policy": self.policy,
        }


@dataclass
class FeishuPermissionGate:
    """Two-layer permission gate for Feishu messages.

    Does NOT modify routing or policy execution.
    Provides structured check() results for the Feishu transport.
    """

    # Layer 1: Global allowlist (open_ids that can interact with the bot)
    global_allowed_users: set[str] = field(default_factory=set)

    # Layer 2: Per-group policies
    # Key: chat_id, Value: (policy, user_set)
    group_policies: dict[str, tuple[GroupPolicy, set[str]]] = field(default_factory=dict)

    # Admin users (always allowed in admin_only policy)
    admin_users: set[str] = field(default_factory=set)

    @staticmethod
    def from_env() -> "FeishuPermissionGate":
        """Build a FeishuPermissionGate from environment variables.

        Reads:
        - FEISHU_ALLOWED_USERS: comma-separated open_ids or "*"
        - FEISHU_GROUP_POLICY: default group policy
        - FEISHU_ADMINS: comma-separated admin open_ids
        """
        allowed_raw = os.getenv("FEISHU_ALLOWED_USERS", "").strip()
        if allowed_raw and allowed_raw != "*":
            global_allowed = {u.strip() for u in allowed_raw.split(",") if u.strip()}
        else:
            global_allowed = set()  # empty = all allowed

        admins_raw = os.getenv("FEISHU_ADMINS", "").strip()
        admin_users = {u.strip() for u in admins_raw.split(",") if u.strip()} if admins_raw else set()

        return FeishuPermissionGate(
            global_allowed_users=global_allowed,
            admin_users=admin_users,
        )

    def check(
        self,
        open_id: str,
        chat_id: str,
        chat_type: str = "group",
    ) -> PermissionCheckResult:
        """Check whether a Feishu message sender is allowed.

        Evaluation order:
        1. Layer 1 (global): If global allowlist is non-empty and user is
           not in it, reject.
        2. Layer 2 (per-group): Evaluate the group-specific policy.
           If no group policy exists, allow by default.

        Returns:
            PermissionCheckResult with allowed, reason, layer, policy.
        """
        # Layer 1: Global allowlist
        if self.global_allowed_users and open_id not in self.global_allowed_users:
            return PermissionCheckResult(
                allowed=False,
                reason=f"User {open_id} not in global allowlist",
                layer="global",
                policy=None,
            )

        # Layer 2: Per-group policy
        if chat_id in self.group_policies:
            policy, user_set = self.group_policies[chat_id]

            if policy == "disabled":
                return PermissionCheckResult(
                    allowed=False,
                    reason=f"Group {chat_id} is disabled",
                    layer="group",
                    policy=policy,
                )

            if policy == "open":
                return PermissionCheckResult(
                    allowed=True,
                    reason="Group policy is open",
                    layer="group",
                    policy=policy,
                )

            if policy == "allowlist":
                if open_id in user_set:
                    return PermissionCheckResult(
                        allowed=True,
                        reason=f"User {open_id} in group allowlist",
                        layer="group",
                        policy=policy,
                    )
                # Admins bypass group allowlist
                if open_id in self.admin_users:
                    return PermissionCheckResult(
                        allowed=True,
                        reason=f"Admin user {open_id} bypasses group allowlist",
                        layer="group",
                        policy=policy,
                    )
                return PermissionCheckResult(
                    allowed=False,
                    reason=f"User {open_id} not in group allowlist",
                    layer="group",
                    policy=policy,
                )

            if policy == "blacklist":
                if open_id in user_set:
                    return PermissionCheckResult(
                        allowed=False,
                        reason=f"User {open_id} in group blacklist",
                        layer="group",
                        policy=policy,
                    )
                return PermissionCheckResult(
                    allowed=True,
                    reason="User not in blacklist",
                    layer="group",
                    policy=policy,
                )

            if policy == "admin_only":
                if open_id in self.admin_users:
                    return PermissionCheckResult(
                        allowed=True,
                        reason=f"Admin user {open_id}",
                        layer="group",
                        policy=policy,
                    )
                return PermissionCheckResult(
                    allowed=False,
                    reason=f"Group requires admin, user {open_id} is not admin",
                    layer="group",
                    policy=policy,
                )

        # No group policy: allow by default
        return PermissionCheckResult(
            allowed=True,
            reason="No group policy, default allow",
            layer="unknown",
            policy=None,
        )

    def set_group_policy(
        self,
        chat_id: str,
        policy: GroupPolicy,
        users: set[str] | None = None,
    ) -> None:
        """Set the per-group policy for a group chat.

        This is a configuration method. It does NOT modify routing or
        policy execution.
        """
        self.group_policies[chat_id] = (policy, users or set())

    def remove_group_policy(self, chat_id: str) -> None:
        """Remove the per-group policy for a group chat."""
        self.group_policies.pop(chat_id, None)

    def health(self) -> dict[str, Any]:
        """Return a health snapshot for dashboard display."""
        return {
            "global_allowed_users_count": len(self.global_allowed_users),
            "global_allowlist_active": bool(self.global_allowed_users),
            "group_policies_count": len(self.group_policies),
            "admin_users_count": len(self.admin_users),
        }
