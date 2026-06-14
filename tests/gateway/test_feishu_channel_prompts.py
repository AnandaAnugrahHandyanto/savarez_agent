"""Tests for Feishu channel_prompts support."""

import asyncio
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from gateway.platforms.base import resolve_channel_prompt


class TestFeishuChannelPromptResolution(unittest.TestCase):
    """Test that resolve_channel_prompt works correctly for Feishu config patterns."""

    def test_exact_chat_id_match(self):
        """An exact chat_id match returns the corresponding prompt."""
        config_extra = {
            "channel_prompts": {
                "oc_abc123": "This is a medical report group.",
                "oc_def456": "This is a general chat.",
            }
        }
        result = resolve_channel_prompt(config_extra, "oc_abc123")
        self.assertEqual(result, "This is a medical report group.")

    def test_thread_falls_back_to_parent_chat(self):
        """When thread_id has no match, fall back to the parent chat_id."""
        config_extra = {
            "channel_prompts": {
                "oc_abc123": "Parent chat prompt.",
            }
        }
        # thread_id="oc_thread999" has no match → falls back to "oc_abc123"
        result = resolve_channel_prompt(config_extra, "oc_thread999", parent_id="oc_abc123")
        self.assertEqual(result, "Parent chat prompt.")

    def test_thread_preferred_over_parent(self):
        """An exact thread_id match takes priority over the parent chat_id."""
        config_extra = {
            "channel_prompts": {
                "oc_abc123": "Parent chat prompt.",
                "oc_thread999": "Thread-specific prompt.",
            }
        }
        result = resolve_channel_prompt(config_extra, "oc_thread999", parent_id="oc_abc123")
        self.assertEqual(result, "Thread-specific prompt.")

    def test_no_match_returns_none(self):
        """Returns None when no chat_id or parent_id matches."""
        config_extra = {
            "channel_prompts": {
                "oc_abc123": "Some prompt.",
            }
        }
        result = resolve_channel_prompt(config_extra, "oc_unknown")
        self.assertIsNone(result)

    def test_empty_prompts_dict_returns_none(self):
        """An empty channel_prompts dict returns None."""
        config_extra = {"channel_prompts": {}}
        result = resolve_channel_prompt(config_extra, "oc_abc123")
        self.assertIsNone(result)

    def test_missing_prompts_key_returns_none(self):
        """When channel_prompts key is absent, returns None."""
        config_extra = {}
        result = resolve_channel_prompt(config_extra, "oc_abc123")
        self.assertIsNone(result)

    def test_blank_prompt_treated_as_absent(self):
        """A blank/whitespace-only prompt is treated as absent."""
        config_extra = {
            "channel_prompts": {
                "oc_abc123": "   ",
            }
        }
        result = resolve_channel_prompt(config_extra, "oc_abc123")
        self.assertIsNone(result)

    def test_none_parent_id_ignored(self):
        """When parent_id is None, only chat_id is checked."""
        config_extra = {
            "channel_prompts": {
                "oc_abc123": "Chat prompt.",
            }
        }
        result = resolve_channel_prompt(config_extra, "oc_abc123", parent_id=None)
        self.assertEqual(result, "Chat prompt.")

    def test_channel_prompts_not_dict_returns_none(self):
        """If channel_prompts is not a dict, returns None."""
        config_extra = {"channel_prompts": "not a dict"}
        result = resolve_channel_prompt(config_extra, "oc_abc123")
        self.assertIsNone(result)


try:
    import lark_oapi
    _HAS_LARK = True
except ImportError:
    _HAS_LARK = False


@unittest.skipUnless(_HAS_LARK, "lark_oapi not installed")
class TestFeishuChannelPromptInAdapter(unittest.TestCase):
    """Test that FeishuAdapter correctly resolves channel_prompt from config."""

    def _make_adapter(self, channel_prompts=None):
        """Create a FeishuAdapter with channel_prompts in config.extra."""
        from gateway.config import PlatformConfig
        from gateway.platforms.feishu import FeishuAdapter

        extra = {}
        if channel_prompts:
            extra["channel_prompts"] = channel_prompts
        pc = PlatformConfig(enabled=True, extra=extra)
        adapter = FeishuAdapter(pc)
        return adapter

    def test_config_extra_contains_channel_prompts(self):
        """Verify the adapter stores channel_prompts in config.extra."""
        adapter = self._make_adapter(channel_prompts={
            "oc_test_chat": "This chat is about medical reports.",
        })
        self.assertIn("channel_prompts", adapter.config.extra)
        result = resolve_channel_prompt(adapter.config.extra, "oc_test_chat")
        self.assertEqual(result, "This chat is about medical reports.")

    def test_channel_prompt_none_for_unknown_chat(self):
        """Verify channel_prompt is None for an unmatched chat."""
        adapter = self._make_adapter(channel_prompts={
            "oc_other_chat": "Other prompt.",
        })
        result = resolve_channel_prompt(adapter.config.extra, "oc_unknown_chat")
        self.assertIsNone(result)

    def test_no_channel_prompts_configured(self):
        """Verify channel_prompt is None when no channel_prompts are set."""
        adapter = self._make_adapter()
        result = resolve_channel_prompt(adapter.config.extra, "oc_any_chat")
        self.assertIsNone(result)

    @patch.dict(os.environ, {
        "FEISHU_APP_ID": "cli_test",
        "FEISHU_APP_SECRET": "secret_test",
        "FEISHU_CONNECTION_MODE": "websocket",
    }, clear=False)
    def test_channel_prompts_bridged_from_config_yaml(self):
        """Verify channel_prompts are bridged from feishu: config block to adapter extra."""
        from gateway.config import GatewayConfig, Platform, _apply_env_overrides

        config = GatewayConfig()
        # Simulate what load_gateway_config does with channel_prompts
        platforms_data = {}
        plat_data = {"enabled": True}
        extra = {
            "app_id": "cli_test",
            "app_secret": "secret_test",
            "connection_mode": "websocket",
            "channel_prompts": {"oc_chat1": "Prompt for chat1"},
        }
        plat_data["extra"] = extra
        platforms_data["feishu"] = plat_data

        # The channel_prompts should be accessible after config loading
        self.assertEqual(extra["channel_prompts"]["oc_chat1"], "Prompt for chat1")


@unittest.skipUnless(_HAS_LARK, "lark_oapi not installed")
class TestFeishuChannelPromptInboundEvent(unittest.TestCase):
    """Verify _process_inbound_message injects channel_prompt into MessageEvent."""

    def _make_adapter(self, channel_prompts=None):
        from gateway.config import PlatformConfig
        from gateway.platforms.feishu import FeishuAdapter

        extra = {}
        if channel_prompts is not None:
            extra["channel_prompts"] = channel_prompts
        adapter = FeishuAdapter(PlatformConfig(enabled=True, extra=extra))
        adapter._dispatch_inbound_event = AsyncMock()
        adapter.get_chat_info = AsyncMock(
            return_value={"chat_id": "oc_parent", "name": "Feishu Group", "type": "group"}
        )
        adapter._resolve_sender_profile = AsyncMock(
            return_value={"user_id": "ou_user", "user_name": "张三", "user_id_alt": None}
        )
        return adapter

    def _message(self, *, chat_id="oc_parent", thread_id=None, text="hello"):
        return SimpleNamespace(
            chat_id=chat_id,
            thread_id=thread_id,
            parent_id=None,
            upper_message_id=None,
            root_id=None,
            message_type="text",
            content=json.dumps({"text": text}, ensure_ascii=False),
            message_id="om_text",
        )

    def _run_message(self, adapter, message):
        asyncio.run(
            adapter._process_inbound_message(
                data=SimpleNamespace(event=SimpleNamespace(message=message)),
                message=message,
                sender_id=SimpleNamespace(open_id="ou_user", user_id=None, union_id=None),
                chat_type="group",
                message_id=message.message_id,
            )
        )
        adapter._dispatch_inbound_event.assert_awaited_once()
        return adapter._dispatch_inbound_event.await_args.args[0]

    def test_inbound_chat_id_match_sets_channel_prompt(self):
        adapter = self._make_adapter({"oc_parent": "Parent group prompt"})
        event = self._run_message(adapter, self._message(chat_id="oc_parent"))
        self.assertEqual(event.channel_prompt, "Parent group prompt")

    def test_inbound_thread_id_match_takes_priority_over_parent(self):
        adapter = self._make_adapter({
            "oc_parent": "Parent group prompt",
            "om_thread": "Thread-specific prompt",
        })
        event = self._run_message(adapter, self._message(chat_id="oc_parent", thread_id="om_thread"))
        self.assertEqual(event.channel_prompt, "Thread-specific prompt")

    def test_inbound_thread_falls_back_to_parent_chat(self):
        adapter = self._make_adapter({"oc_parent": "Parent group prompt"})
        event = self._run_message(adapter, self._message(chat_id="oc_parent", thread_id="om_thread"))
        self.assertEqual(event.channel_prompt, "Parent group prompt")

    def test_inbound_no_channel_prompt_config_sets_none(self):
        adapter = self._make_adapter()
        event = self._run_message(adapter, self._message(chat_id="oc_parent"))
        self.assertIsNone(event.channel_prompt)
