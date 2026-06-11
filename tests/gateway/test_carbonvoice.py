"""Tests for the native Carbon Voice platform.

Carbon Voice is a voice-first messaging platform ported from the external
hermes-plugin-carbonvoice into gateway/platforms/carbonvoice/. These tests
cover the native-integration contract (enum, factory wiring, requirements,
config auto-enable) plus the pure platform logic (payload parsing,
deny-by-default allow-list, one-tap approval reactions).
"""

import os
from unittest import mock

import pytest

from gateway.config import Platform, PlatformConfig


# ── Native integration: enum + requirements + factory ────────────────────

class TestNativeWiring:
    def test_platform_enum_member(self):
        assert Platform.CARBONVOICE.value == "carbonvoice"
        # The adapter constructs Platform("carbonvoice"); it must resolve to
        # the real member, not a dynamic plugin pseudo-member.
        assert Platform("carbonvoice") is Platform.CARBONVOICE

    def test_check_requirements(self):
        from gateway.platforms.carbonvoice import check_carbonvoice_requirements
        # httpx is a core dep, so requirements pass (socketio is optional).
        assert check_carbonvoice_requirements() is True

    def test_subpackage_exports(self):
        from gateway.platforms.carbonvoice import (
            CarbonVoiceAdapter,
            CarbonVoiceAPI,
            standalone_send,
        )
        from gateway.platforms.base import BasePlatformAdapter
        assert issubclass(CarbonVoiceAdapter, BasePlatformAdapter)
        assert callable(standalone_send)
        assert CarbonVoiceAPI is not None

    def test_adapter_init(self):
        from gateway.platforms.carbonvoice import CarbonVoiceAdapter
        cfg = PlatformConfig(enabled=True, token="cv_pat_dummy", extra={"pat": "cv_pat_dummy"})
        adapter = CarbonVoiceAdapter(cfg)
        # No edit API on Carbon Voice — must declare it so the stream consumer
        # doesn't re-send on unconfirmed delivery.
        assert adapter.SUPPORTS_MESSAGE_EDITING is False


class TestConfigAutoEnable:
    def test_pat_enables_platform(self):
        from gateway.config import _apply_env_overrides, GatewayConfig
        with mock.patch.dict(os.environ, {"CARBONVOICE_PAT": "cv_pat_dummy"}, clear=False):
            cfg = GatewayConfig()
            _apply_env_overrides(cfg)
            cv = cfg.platforms.get(Platform.CARBONVOICE)
            assert cv is not None
            assert cv.enabled is True
            assert cv.token == "cv_pat_dummy"
            assert cv.extra.get("pat") == "cv_pat_dummy"

    def test_no_pat_no_platform(self):
        from gateway.config import _apply_env_overrides, GatewayConfig
        env = {k: v for k, v in os.environ.items() if k != "CARBONVOICE_PAT"}
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = GatewayConfig()
            _apply_env_overrides(cfg)
            assert Platform.CARBONVOICE not in cfg.platforms


# ── Payload parsing (pure) ───────────────────────────────────────────────

class TestParse:
    def test_extract_transcript(self):
        from gateway.platforms.carbonvoice.parse import extract_transcript
        assert extract_transcript(
            {"text_models": [{"type": "transcript", "value": "hi"}]}
        ) == "hi"
        assert extract_transcript({"transcript": "v5 flat"}) == "v5 flat"
        assert extract_transcript({}) == ""

    def test_extract_message_id_v5_v2(self):
        from gateway.platforms.carbonvoice.parse import extract_message_id
        assert extract_message_id({"id": "abc"}) == "abc"          # v5
        assert extract_message_id({"message_id": "xyz"}) == "xyz"  # v2

    def test_message_age_seconds(self):
        from datetime import datetime, timezone
        from gateway.platforms.carbonvoice.parse import message_age_seconds
        now = datetime(2026, 6, 8, 16, 0, 0, tzinfo=timezone.utc)
        assert message_age_seconds({"created_at": "2026-06-08T15:59:00Z"}, now) == 60.0
        assert message_age_seconds({"created_at": "2026-06-08T15:59:00"}, now) == 60.0  # naive→UTC
        assert message_age_seconds({"id": "x"}, now) is None       # no ts
        assert message_age_seconds({"created_at": "garbage"}, now) is None

    def test_reactors_for(self):
        from gateway.platforms.carbonvoice.parse import reactors_for
        msg = {"reaction_summary": {"top_user_reactions": [
            {"user_id": "owner", "reaction_id": "affirmative"},
            {"user_id": "stranger", "reaction_id": "negative"},
        ]}}
        assert reactors_for(msg, {"affirmative"}) == {"owner"}
        assert reactors_for(msg, {"negative"}) == {"stranger"}
        assert reactors_for(msg, {"affirmative", "negative"}) == {"owner", "stranger"}
        assert reactors_for({}, {"affirmative"}) == set()


# ── Deny-by-default allow-list ───────────────────────────────────────────

class TestAllowlist:
    def test_deny_by_default(self):
        from gateway.platforms.carbonvoice.audit import AllowlistGate
        env = {k: v for k, v in os.environ.items()
               if k not in ("CARBONVOICE_ALLOW_ALL_USERS", "CARBONVOICE_ALLOWED_USERS")}
        with mock.patch.dict(os.environ, env, clear=True):
            g = AllowlistGate.from_env()
            assert g.is_allowed("anyone") is False
            assert g.has_any_authorizer is False
            # Owner (whoami.created_by) is always allowed.
            g.set_owner("OWNER")
            assert g.is_owner("OWNER") and g.is_allowed("OWNER")
            assert g.is_allowed("anyone") is False

    def test_allow_all_opt_in(self):
        from gateway.platforms.carbonvoice.audit import AllowlistGate
        with mock.patch.dict(os.environ, {"CARBONVOICE_ALLOW_ALL_USERS": "true"}, clear=False):
            assert AllowlistGate.from_env().is_allowed("anyone") is True

    def test_static_allowed_users(self):
        from gateway.platforms.carbonvoice.audit import AllowlistGate
        with mock.patch.dict(os.environ, {"CARBONVOICE_ALLOWED_USERS": "abc"}, clear=False):
            env = dict(os.environ)
            env.pop("CARBONVOICE_ALLOW_ALL_USERS", None)
            with mock.patch.dict(os.environ, env, clear=True):
                g = AllowlistGate.from_env()
                g.set_owner("OWNER")
                assert g.is_allowed("abc")
                assert g.is_allowed("OWNER")
                assert not g.is_allowed("xyz")


# ── Admin command parser ─────────────────────────────────────────────────

class TestCommandParser:
    def test_explicit_command_names(self):
        from gateway.platforms.carbonvoice.permits import parse_admin_command
        assert parse_admin_command("/cv-allow-user Fmx4") == ("allow", "Fmx4")
        assert parse_admin_command("  /CV-DENY-USER  ABC ") == ("deny", "ABC")
        assert parse_admin_command("/cv-list-allow-users") == ("list", None)
        assert parse_admin_command("/cv-allow-user") == ("allow", None)  # missing arg
        # Not commands
        assert parse_admin_command("hi /cv-allow-user X") is None
        assert parse_admin_command("/cv-allow X") is None  # old short form gone
        assert parse_admin_command(None) is None
        assert parse_admin_command("") is None


# ── One-tap approval reactions ───────────────────────────────────────────

class TestReactions:
    def test_pending_and_ack_reactions_distinct(self):
        from gateway.platforms.carbonvoice.constants import (
            DEFAULT_APPROVE_REACTION_ID,
            DEFAULT_REACTION_ID,
            DEFAULT_REJECT_REACTION_ID,
        )
        assert DEFAULT_APPROVE_REACTION_ID == "affirmative"
        assert DEFAULT_REJECT_REACTION_ID == "negative"
        assert DEFAULT_APPROVE_REACTION_ID != DEFAULT_REJECT_REACTION_ID
        assert DEFAULT_APPROVE_REACTION_ID != DEFAULT_REACTION_ID

    @pytest.mark.asyncio
    async def test_reaction_service_react(self):
        from gateway.platforms.carbonvoice.reactions import ReactionService

        class _FakeAPI:
            def __init__(self):
                self.calls = []

            async def react(self, rid, mid):
                self.calls.append((rid, mid))

        api = _FakeAPI()
        svc = ReactionService(api)
        assert svc.reaction_id == "acknowledged"
        assert svc.pending_reaction_id == "confused"
        assert callable(svc.pending)
        assert await svc.ack_sync("m1") is True
        assert ("acknowledged", "m1") in api.calls
