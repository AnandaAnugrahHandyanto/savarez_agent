"""Tests for the edit action on the send_message tool."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from tools.send_message_tool import SEND_MESSAGE_SCHEMA, send_message_tool
from unittest.mock import patch, MagicMock


class TestSchema:
    """Verify the schema accepts the edit action and message_id parameter."""

    def test_schema_accepts_edit_action(self):
        """Schema should include 'edit' in the action enum."""
        action_prop = SEND_MESSAGE_SCHEMA["parameters"]["properties"]["action"]
        assert "edit" in action_prop["enum"], "edit should be a valid action"
        assert action_prop["enum"] == ["send", "list", "edit"]

    def test_schema_has_message_id(self):
        """Schema should include message_id property."""
        props = SEND_MESSAGE_SCHEMA["parameters"]["properties"]
        assert "message_id" in props, "message_id should be a parameter"
        assert props["message_id"]["type"] == "string"

    def test_schema_description_mentions_edit(self):
        """Action description should mention the edit action."""
        action_prop = SEND_MESSAGE_SCHEMA["parameters"]["properties"]["action"]
        assert "edit" in action_prop["description"].lower()


class TestHandleEdit:
    """Test the _handle_edit dispatch function."""

    def test_edit_dispatches_to_adapter(self):
        """_handle_edit should call adapter.edit_message when platform is supported."""
        args = {
            "action": "edit",
            "target": "telegram:-1001234567890",
            "message": "Updated message",
            "message_id": "12345",
        }

        with (
            patch("tools.send_message_tool._parse_target_ref") as mock_parse,
            patch("gateway.config.load_gateway_config") as mock_load_cfg,
            patch("gateway.config.Platform") as mock_platform_cls,
            patch("tools.interrupt.is_interrupted") as mock_interrupt,
            patch("model_tools._run_async") as mock_run,
        ):
            mock_parse.return_value = ("-1001234567890", None, True)
            mock_interrupt.return_value = False

            mock_platform = MagicMock()
            mock_platform.value = "telegram"
            mock_platform_cls.return_value = mock_platform

            mock_cfg = MagicMock()
            mock_pconfig = MagicMock()
            mock_pconfig.enabled = True
            mock_cfg.platforms = {mock_platform: mock_pconfig}
            mock_load_cfg.return_value = mock_cfg

            mock_run.return_value = {
                "success": True,
                "platform": "telegram",
                "chat_id": "-1001234567890",
                "message_id": "12345",
            }

            result = send_message_tool(args)
            result_data = json.loads(result)

            assert result_data["success"] is True
            assert result_data["platform"] == "telegram"
            assert result_data["message_id"] == "12345"
            mock_run.assert_called_once()

    def test_edit_returns_error_for_unsupported_platform(self):
        """_handle_edit should return an error when edit_message is not supported."""
        args = {
            "action": "edit",
            "target": "telegram:-1001234567890",
            "message": "Updated message",
            "message_id": "12345",
        }

        with (
            patch("tools.send_message_tool._parse_target_ref") as mock_parse,
            patch("gateway.config.load_gateway_config") as mock_load_cfg,
            patch("gateway.config.Platform") as mock_platform_cls,
            patch("tools.interrupt.is_interrupted") as mock_interrupt,
            patch("model_tools._run_async") as mock_run,
        ):
            mock_parse.return_value = ("-1001234567890", None, True)
            mock_interrupt.return_value = False

            mock_platform = MagicMock()
            mock_platform.value = "telegram"
            mock_platform_cls.return_value = mock_platform

            mock_cfg = MagicMock()
            mock_pconfig = MagicMock()
            mock_pconfig.enabled = True
            mock_cfg.platforms = {mock_platform: mock_pconfig}
            mock_load_cfg.return_value = mock_cfg

            mock_run.return_value = {"error": "Edit not supported on this platform"}

            result = send_message_tool(args)
            result_data = json.loads(result)

            assert "error" in result_data

    def test_edit_returns_error_when_message_id_missing(self):
        """_handle_edit should return an error when message_id is missing."""
        args = {
            "action": "edit",
            "target": "telegram:-1001234567890",
            "message": "Updated message",
        }

        result = send_message_tool(args)
        result_data = json.loads(result)

        assert "error" in result_data

    def test_edit_requires_target_and_message(self):
        """_handle_edit should return an error when target or message is missing."""
        # Missing target
        result = send_message_tool({
            "action": "edit",
            "target": "",
            "message": "Updated message",
            "message_id": "12345",
        })
        assert "error" in json.loads(result)

        # Missing message
        result = send_message_tool({
            "action": "edit",
            "target": "telegram:-1001234567890",
            "message": "",
            "message_id": "12345",
        })
        assert "error" in json.loads(result)

    def test_send_action_still_works(self):
        """Original send action should still work unchanged."""
        # The send action should route to _handle_send (not _handle_edit)
        with patch("tools.send_message_tool._handle_send") as mock_send:
            mock_send.return_value = json.dumps({
                "success": True,
                "platform": "telegram",
                "chat_id": "-1001234567890",
                "message_id": "99999",
            })
            result = send_message_tool({
                "action": "send",
                "target": "telegram:-1001234567890",
                "message": "Hello world",
            })
            result_data = json.loads(result)
            assert result_data["success"] is True
            mock_send.assert_called_once()

    def test_list_action_still_works(self):
        """Original list action should still work unchanged."""
        with patch("tools.send_message_tool._handle_list") as mock_list:
            mock_list.return_value = json.dumps({"targets": ["telegram:home"]})
            result = send_message_tool({"action": "list"})
            result_data = json.loads(result)
            assert "targets" in result_data
            mock_list.assert_called_once()
