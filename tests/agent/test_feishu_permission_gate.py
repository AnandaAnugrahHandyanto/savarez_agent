"""Tests for Feishu permission gate."""

import os
import pytest

from agent.managed_agents.feishu_permission_gate import (
    FeishuPermissionGate,
    GroupPolicy,
    PermissionCheckResult,
)


# ---------------------------------------------------------------------------
# Global allowlist (Layer 1)
# ---------------------------------------------------------------------------

class TestGlobalAllowlist:
    """Test Layer 1: global allowlist checks."""

    def test_empty_global_allowlist_allows_all(self):
        """Empty global allowlist means all users are allowed."""
        gate = FeishuPermissionGate()
        result = gate.check("ou_any", "oc_chat1")
        assert result.allowed is True
        assert result.layer == "unknown"

    def test_global_allowlist_with_star_allows_all(self):
        """Global allowlist set to '*' allows all users."""
        # This is tested via from_env(), not directly
        gate = FeishuPermissionGate(global_allowed_users=set())
        result = gate.check("ou_any", "oc_chat1")
        assert result.allowed is True

    def test_global_allowlist_blocks_unlisted(self):
        """Users not in global allowlist are blocked."""
        gate = FeishuPermissionGate(global_allowed_users={"ou_alice", "ou_bob"})
        result = gate.check("ou_eve", "oc_chat1")
        assert result.allowed is False
        assert result.layer == "global"

    def test_global_allowlist_allows_listed(self):
        """Users in global allowlist are allowed."""
        gate = FeishuPermissionGate(global_allowed_users={"ou_alice", "ou_bob"})
        result = gate.check("ou_alice", "oc_chat1")
        assert result.allowed is True
        assert result.layer == "unknown"  # No group policy, falls through


# ---------------------------------------------------------------------------
# Per-group policy (Layer 2)
# ---------------------------------------------------------------------------

class TestGroupPolicy:
    """Test Layer 2: per-group policy checks."""

    def test_open_policy_allows_all(self):
        """Open policy allows all users in the group."""
        gate = FeishuPermissionGate()
        gate.set_group_policy("oc_chat1", "open")
        result = gate.check("ou_any", "oc_chat1")
        assert result.allowed is True
        assert result.policy == "open"
        assert result.layer == "group"

    def test_disabled_policy_blocks_all(self):
        """Disabled policy blocks all users."""
        gate = FeishuPermissionGate(admin_users={"ou_admin"})
        gate.set_group_policy("oc_chat1", "disabled")
        result = gate.check("ou_any", "oc_chat1")
        assert result.allowed is False
        assert result.policy == "disabled"
        assert result.layer == "group"

    def test_disabled_policy_blocks_admins(self):
        """Disabled policy even blocks admin users."""
        gate = FeishuPermissionGate(admin_users={"ou_admin"})
        gate.set_group_policy("oc_chat1", "disabled")
        result = gate.check("ou_admin", "oc_chat1")
        assert result.allowed is False

    def test_allowlist_policy_allows_listed(self):
        """Allowlist policy allows users in the list."""
        gate = FeishuPermissionGate()
        gate.set_group_policy("oc_chat1", "allowlist", users={"ou_alice"})
        result = gate.check("ou_alice", "oc_chat1")
        assert result.allowed is True
        assert result.policy == "allowlist"

    def test_allowlist_policy_blocks_unlisted(self):
        """Allowlist policy blocks users not in the list."""
        gate = FeishuPermissionGate()
        gate.set_group_policy("oc_chat1", "allowlist", users={"ou_alice"})
        result = gate.check("ou_eve", "oc_chat1")
        assert result.allowed is False
        assert result.policy == "allowlist"

    def test_allowlist_policy_admin_bypass(self):
        """Admin users bypass group allowlist."""
        gate = FeishuPermissionGate(admin_users={"ou_admin"})
        gate.set_group_policy("oc_chat1", "allowlist", users={"ou_alice"})
        result = gate.check("ou_admin", "oc_chat1")
        assert result.allowed is True
        assert "admin" in result.reason.lower() or "Admin" in result.reason

    def test_blacklist_policy_blocks_listed(self):
        """Blacklist policy blocks users in the list."""
        gate = FeishuPermissionGate()
        gate.set_group_policy("oc_chat1", "blacklist", users={"ou_spammer"})
        result = gate.check("ou_spammer", "oc_chat1")
        assert result.allowed is False
        assert result.policy == "blacklist"

    def test_blacklist_policy_allows_others(self):
        """Blacklist policy allows users not in the list."""
        gate = FeishuPermissionGate()
        gate.set_group_policy("oc_chat1", "blacklist", users={"ou_spammer"})
        result = gate.check("ou_nice_user", "oc_chat1")
        assert result.allowed is True

    def test_admin_only_policy_allows_admins(self):
        """Admin-only policy allows admin users."""
        gate = FeishuPermissionGate(admin_users={"ou_admin"})
        gate.set_group_policy("oc_chat1", "admin_only")
        result = gate.check("ou_admin", "oc_chat1")
        assert result.allowed is True
        assert result.policy == "admin_only"

    def test_admin_only_policy_blocks_non_admins(self):
        """Admin-only policy blocks non-admin users."""
        gate = FeishuPermissionGate(admin_users={"ou_admin"})
        gate.set_group_policy("oc_chat1", "admin_only")
        result = gate.check("ou_user", "oc_chat1")
        assert result.allowed is False
        assert result.policy == "admin_only"


# ---------------------------------------------------------------------------
# Layer interaction
# ---------------------------------------------------------------------------

class TestLayerInteraction:
    """Test Layer 1 + Layer 2 interaction."""

    def test_global_block_overrides_group_open(self):
        """Global allowlist block takes precedence over group open policy."""
        gate = FeishuPermissionGate(global_allowed_users={"ou_alice"})
        gate.set_group_policy("oc_chat1", "open")
        result = gate.check("ou_eve", "oc_chat1")
        assert result.allowed is False
        assert result.layer == "global"

    def test_global_allow_then_group_allowlist_blocks(self):
        """Global allow → group allowlist can still block."""
        gate = FeishuPermissionGate(global_allowed_users={"ou_alice", "ou_eve"})
        gate.set_group_policy("oc_chat1", "allowlist", users={"ou_alice"})
        result = gate.check("ou_eve", "oc_chat1")
        assert result.allowed is False
        assert result.layer == "group"

    def test_no_group_policy_allows(self):
        """No group policy falls through to allow."""
        gate = FeishuPermissionGate()
        result = gate.check("ou_any", "oc_no_policy")
        assert result.allowed is True
        assert result.layer == "unknown"

    def test_no_group_policy_with_global_allowlist(self):
        """No group policy, but global allowlist allows the user."""
        gate = FeishuPermissionGate(global_allowed_users={"ou_alice"})
        result = gate.check("ou_alice", "oc_no_policy")
        assert result.allowed is True


# ---------------------------------------------------------------------------
# Management methods
# ---------------------------------------------------------------------------

class TestManagement:
    """Test set/remove group policy and health."""

    def test_set_and_remove_group_policy(self):
        """Set and then remove a group policy."""
        gate = FeishuPermissionGate()
        gate.set_group_policy("oc_chat1", "allowlist", users={"ou_alice"})
        assert "oc_chat1" in gate.group_policies

        gate.remove_group_policy("oc_chat1")
        assert "oc_chat1" not in gate.group_policies

    def test_remove_nonexistent_group_policy(self):
        """Removing a non-existent group policy does not error."""
        gate = FeishuPermissionGate()
        gate.remove_group_policy("oc_nonexistent")  # No error

    def test_health_snapshot(self):
        """Health snapshot includes gate state."""
        gate = FeishuPermissionGate(
            global_allowed_users={"ou_a", "ou_b"},
            admin_users={"ou_admin"},
        )
        gate.set_group_policy("oc_g1", "open")
        gate.set_group_policy("oc_g2", "allowlist", users={"ou_alice"})

        health = gate.health()
        assert health["global_allowed_users_count"] == 2
        assert health["global_allowlist_active"] is True
        assert health["group_policies_count"] == 2
        assert health["admin_users_count"] == 1

    def test_from_env(self):
        """from_env builds gate from environment variables."""
        original_users = os.environ.get("FEISHU_ALLOWED_USERS")
        original_admins = os.environ.get("FEISHU_ADMINS")
        try:
            os.environ["FEISHU_ALLOWED_USERS"] = "ou_alice,ou_bob"
            os.environ["FEISHU_ADMINS"] = "ou_admin"
            gate = FeishuPermissionGate.from_env()
            assert "ou_alice" in gate.global_allowed_users
            assert "ou_bob" in gate.global_allowed_users
            assert "ou_admin" in gate.admin_users
        finally:
            if original_users is not None:
                os.environ["FEISHU_ALLOWED_USERS"] = original_users
            else:
                os.environ.pop("FEISHU_ALLOWED_USERS", None)
            if original_admins is not None:
                os.environ["FEISHU_ADMINS"] = original_admins
            else:
                os.environ.pop("FEISHU_ADMINS", None)


# ---------------------------------------------------------------------------
# PermissionCheckResult
# ---------------------------------------------------------------------------

class TestPermissionCheckResult:
    """Test PermissionCheckResult data structure."""

    def test_result_to_dict(self):
        """Result can be serialized to dict."""
        result = PermissionCheckResult(
            allowed=True,
            reason="open policy",
            layer="group",
            policy="open",
        )
        d = result.to_dict()
        assert d["allowed"] is True
        assert d["reason"] == "open policy"
        assert d["layer"] == "group"
        assert d["policy"] == "open"
