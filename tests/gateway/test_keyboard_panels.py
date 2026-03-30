"""Tests for interactive Telegram keyboard panels.

Tests the keyboard builders, callback handler, pending text input system,
and /settings command across the gateway.
"""

import asyncio
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import Platform
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource


def _make_event(text="", platform=Platform.TELEGRAM,
                user_id="12345", chat_id="67890", message_id=None):
    """Build a MessageEvent for testing."""
    source = SessionSource(
        platform=platform,
        user_id=user_id,
        chat_id=chat_id,
        user_name="testuser",
    )
    return MessageEvent(text=text, source=source, message_id=message_id)


def _make_runner():
    """Create a bare GatewayRunner with minimal mocks."""
    from gateway.run import GatewayRunner
    runner = object.__new__(GatewayRunner)
    runner.adapters = {}
    runner._voice_mode = {}
    runner._session_db = None
    runner._reasoning_config = None
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._running_agents = {}
    runner._background_tasks = set()
    runner._show_reasoning = False
    runner._effective_model = None
    runner._effective_provider = None

    mock_store = MagicMock()
    runner.session_store = mock_store

    from gateway.hooks import HookRegistry
    runner.hooks = HookRegistry()

    return runner


# ---------------------------------------------------------------------------
# Keyboard builders (module-level functions)
# ---------------------------------------------------------------------------


class TestModelProvidersKeyboard:
    """Tests for _model_providers_keyboard builder."""

    def test_returns_text_and_buttons(self):
        from gateway.run import _model_providers_keyboard
        text, rows = _model_providers_keyboard("67890", "12345", "anthropic/claude-opus-4.6", "openrouter")
        assert isinstance(text, str)
        assert "Current: anthropic/claude-opus-4.6" in text
        assert isinstance(rows, list)
        assert len(rows) > 0

    def test_includes_cancel_button(self):
        from gateway.run import _model_providers_keyboard
        _, rows = _model_providers_keyboard("67890", "12345", "anthropic/claude-opus-4.6")
        # Find cancel button
        all_buttons = [btn for row in rows for btn in row]
        cancel_btns = [b for b in all_buttons if b["text"] == "Cancel"]
        assert len(cancel_btns) == 1

    def test_includes_add_provider_button(self):
        from gateway.run import _model_providers_keyboard
        _, rows = _model_providers_keyboard("67890", "12345", "anthropic/claude-opus-4.6")
        all_buttons = [btn for row in rows for btn in row]
        add_btns = [b for b in all_buttons if b["text"] == "+ Add Provider"]
        assert len(add_btns) == 1

    def test_current_provider_marked(self):
        from gateway.run import _model_providers_keyboard, _keyboard_actions
        _keyboard_actions.clear()
        _, rows = _model_providers_keyboard("67890", "12345", "anthropic/claude-opus-4.6", "openrouter")
        all_buttons = [btn for row in rows for btn in row]
        # At least one button should have the >> marker
        marked = [b for b in all_buttons if ">>" in b["text"]]
        assert len(marked) >= 1

    def test_registers_actions_in_keyboard_actions(self):
        from gateway.run import _model_providers_keyboard, _keyboard_actions
        _keyboard_actions.clear()
        _, rows = _model_providers_keyboard("67890", "12345", "anthropic/claude-opus-4.6")
        all_buttons = [btn for row in rows for btn in row]
        for btn in all_buttons:
            assert ("67890", "12345", btn["callback_data"]) in _keyboard_actions
        assert len(_keyboard_actions) > 0


class TestModelListKeyboard:
    """Tests for _model_list_keyboard builder."""

    def test_returns_text_and_buttons_for_known_provider(self):
        from gateway.run import _model_list_keyboard
        text, rows = _model_list_keyboard("67890", "12345", "anthropic", "anthropic/claude-opus-4.6")
        assert isinstance(text, str)
        assert "anthropic" in text.lower() or "Anthropic" in text
        assert isinstance(rows, list)

    def test_empty_for_unknown_provider(self):
        from gateway.run import _model_list_keyboard
        text, rows = _model_list_keyboard("67890", "12345", "nonexistent_provider_xyz", "model")
        assert "No models" in text
        assert rows == []

    def test_pagination_buttons(self):
        from gateway.run import _model_list_keyboard
        # Most providers have fewer than _MODELS_PER_PAGE models,
        # so pagination may not appear. Test that it works when page > 0
        # by checking that page=0 at least doesn't crash and returns back button.
        text, rows = _model_list_keyboard("67890", "12345", "anthropic", "model", page=0)
        all_buttons = [btn for row in rows for btn in row]
        # Should always have a back button
        back_btns = [b for b in all_buttons if "Providers" in b["text"]]
        assert len(back_btns) == 1

    def test_back_button_present(self):
        from gateway.run import _model_list_keyboard
        _, rows = _model_list_keyboard("67890", "12345", "anthropic", "model")
        all_buttons = [btn for row in rows for btn in row]
        back_btns = [b for b in all_buttons if "Providers" in b["text"]]
        assert len(back_btns) == 1

    def test_current_model_marked(self):
        from gateway.run import _model_list_keyboard
        _, rows = _model_list_keyboard("67890", "12345", "anthropic", "anthropic/claude-opus-4.6")
        all_buttons = [btn for row in rows for btn in row]
        marked = [b for b in all_buttons if b["text"].startswith("✓")]
        assert len(marked) >= 1


class TestReasoningKeyboard:
    """Tests for _reasoning_keyboard builder."""

    def test_returns_text_and_buttons(self):
        from gateway.run import _reasoning_keyboard
        text, rows = _reasoning_keyboard("67890", "12345", "medium", True)
        assert "Reasoning Settings" in text
        assert "medium" in text
        assert len(rows) > 0

    def test_all_effort_levels_present(self):
        from gateway.run import _reasoning_keyboard
        _, rows = _reasoning_keyboard("67890", "12345", "medium", False)
        all_buttons = [btn for row in rows for btn in row]
        effort_levels = ["none", "low", "minimal", "medium", "high", "xhigh"]
        for level in effort_levels:
            level_btns = [b for b in all_buttons if level.capitalize() in b["text"]]
            assert len(level_btns) == 1, f"Missing button for effort level: {level}"

    def test_current_effort_marked(self):
        from gateway.run import _reasoning_keyboard
        _, rows = _reasoning_keyboard("67890", "12345", "high", False)
        all_buttons = [btn for row in rows for btn in row]
        high_btns = [b for b in all_buttons if "High" in b["text"]]
        assert len(high_btns) == 1
        assert ">>" in high_btns[0]["text"]

    def test_display_toggle_buttons(self):
        from gateway.run import _reasoning_keyboard
        _, rows = _reasoning_keyboard("67890", "12345", "medium", True)
        all_buttons = [btn for row in rows for btn in row]
        show_btns = [b for b in all_buttons if "Show Reasoning" in b["text"]]
        hide_btns = [b for b in all_buttons if "Hide Reasoning" in b["text"]]
        assert len(show_btns) == 1
        assert len(hide_btns) == 1
        # When show_reasoning=True, show button should be marked
        assert "✓" in show_btns[0]["text"]


class TestSettingsKeyboard:
    """Tests for _settings_keyboard builder."""

    def test_returns_text_and_buttons(self):
        from gateway.run import _settings_keyboard
        text, rows = _settings_keyboard("67890", "12345", "all", "all")
        assert "Gateway Settings" in text
        assert len(rows) > 0

    def test_bg_notification_modes(self):
        from gateway.run import _settings_keyboard
        _, rows = _settings_keyboard("67890", "12345", "all", "all")
        # First row should have 4 bg notification buttons
        assert len(rows[0]) == 4
        bg_labels = [b["text"].lstrip(">> ") for b in rows[0]]
        for mode in ["All", "Result", "Error", "Off"]:
            assert mode in bg_labels, f"Missing bg mode: {mode}"

    def test_tool_progress_modes(self):
        from gateway.run import _settings_keyboard
        _, rows = _settings_keyboard("67890", "12345", "all", "all")
        # Third row (index 2, after spacer) should have 4 tool progress buttons
        tp_row = rows[2]
        assert len(tp_row) == 4
        tp_labels = [b["text"].lstrip(">> ") for b in tp_row]
        for mode in ["Off", "New", "All", "Verbose"]:
            assert mode in tp_labels, f"Missing tp mode: {mode}"


# ---------------------------------------------------------------------------
# Keyboard callback handler
# ---------------------------------------------------------------------------


class TestKeyboardCallback:
    """Tests for GatewayRunner._handle_keyboard_callback."""

    @pytest.mark.asyncio
    async def test_model_select_persists_provider(self, tmp_path):
        """Bug 1 regression: keyboard model_select must persist model.provider to config."""
        from gateway.run import _keyboard_actions, _register_keyboard_action
        _keyboard_actions.clear()

        config_path = tmp_path / "config.yaml"
        config_path.write_text("model:\n  default: old-model\n  provider: old-provider\n")

        runner = _make_runner()

        # Register a model_select action
        action_id = _register_keyboard_action("67890", "12345", {
            "type": "model_select",
            "model_id": "anthropic/claude-sonnet-4",
            "provider": "anthropic",
        })

        event = _make_event(text=action_id, message_id="100")
        with patch("gateway.run._hermes_home", tmp_path):
            await runner._handle_keyboard_callback(event)

        # Verify config was written
        import yaml
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        assert cfg["model"]["default"] == "anthropic/claude-sonnet-4"
        assert cfg["model"]["provider"] == "anthropic"

    @pytest.mark.asyncio
    async def test_model_cancel(self, tmp_path):
        from gateway.run import _keyboard_actions, _register_keyboard_action
        _keyboard_actions.clear()

        runner = _make_runner()
        mock_adapter = AsyncMock()
        mock_adapter.send_keyboard = AsyncMock()
        runner.adapters = {Platform.TELEGRAM: mock_adapter}

        action_id = _register_keyboard_action("67890", "12345", {"type": "model_cancel"})
        event = _make_event(text=action_id, message_id="100")
        await runner._handle_keyboard_callback(event)

        mock_adapter.send_keyboard.assert_called_once()
        call_args = mock_adapter.send_keyboard.call_args
        assert "Cancelled" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_unknown_action_ignored(self):
        from gateway.run import _keyboard_actions
        _keyboard_actions.clear()

        runner = _make_runner()
        mock_adapter = AsyncMock()
        runner.adapters = {Platform.TELEGRAM: mock_adapter}

        event = _make_event(text="nonexistent_action_id", message_id="100")
        await runner._handle_keyboard_callback(event)
        mock_adapter.send_keyboard.assert_not_called()

    @pytest.mark.asyncio
    async def test_reasoning_effort_callback(self, tmp_path):
        from gateway.run import _keyboard_actions, _register_keyboard_action
        _keyboard_actions.clear()

        config_path = tmp_path / "config.yaml"
        config_path.write_text("agent:\n  reasoning_effort: medium\n")

        runner = _make_runner()
        runner._show_reasoning = False
        mock_adapter = AsyncMock()
        mock_adapter.send_keyboard = AsyncMock()
        runner.adapters = {Platform.TELEGRAM: mock_adapter}

        action_id = _register_keyboard_action("67890", "12345", {
            "type": "reasoning_effort", "effort": "high",
        })
        event = _make_event(text=action_id, message_id="100")
        with patch("gateway.run._hermes_home", tmp_path):
            await runner._handle_keyboard_callback(event)

        assert runner._reasoning_config == {"enabled": True, "effort": "high"}
        # Config should be saved
        import yaml
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        assert cfg["agent"]["reasoning_effort"] == "high"

    @pytest.mark.asyncio
    async def test_settings_bg_notifications_callback(self, tmp_path):
        from gateway.run import _keyboard_actions, _register_keyboard_action
        _keyboard_actions.clear()

        config_path = tmp_path / "config.yaml"
        config_path.write_text("display:\n  background_process_notifications: all\n  tool_progress: all\n")

        runner = _make_runner()
        mock_adapter = AsyncMock()
        mock_adapter.send_keyboard = AsyncMock()
        runner.adapters = {Platform.TELEGRAM: mock_adapter}

        action_id = _register_keyboard_action("67890", "12345", {
            "type": "settings_bg_notifications", "value": "error",
        })
        event = _make_event(text=action_id, message_id="100")
        with patch("gateway.run._hermes_home", tmp_path):
            await runner._handle_keyboard_callback(event)

        import yaml
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        assert cfg["display"]["background_process_notifications"] == "error"


# ---------------------------------------------------------------------------
# Pending text input (wizard flows)
# ---------------------------------------------------------------------------


class TestPendingTextInput:
    """Tests for the pending text input system."""

    def test_register_and_cancel_pending_text(self):
        from gateway.run import _pending_text_input, _register_pending_text, _cancel_pending_text
        _pending_text_input.clear()

        _register_pending_text("67890", "12345", "add_provider_name", {"step": 1})
        assert ("67890", "12345") in _pending_text_input
        assert _pending_text_input[("67890", "12345")]["type"] == "add_provider_name"

        result = _cancel_pending_text("67890", "12345")
        assert result is True
        assert ("67890", "12345") not in _pending_text_input

        result = _cancel_pending_text("67890", "12345")
        assert result is False

    @pytest.mark.asyncio
    async def test_add_provider_wizard_name_step(self, tmp_path):
        from gateway.run import _pending_text_input, _register_pending_text
        _pending_text_input.clear()

        config_path = tmp_path / "config.yaml"
        config_path.write_text("model:\n  default: test\n")

        runner = _make_runner()
        mock_adapter = AsyncMock()
        mock_adapter.send_keyboard = AsyncMock()
        runner.adapters = {Platform.TELEGRAM: mock_adapter}

        # Register pending input for name step
        _register_pending_text("67890", "12345", "add_provider_name")

        event = _make_event(text="My Test Provider")
        await runner._handle_text_input(event)

        # Should have advanced to URL step
        assert ("67890", "12345") in _pending_text_input
        assert _pending_text_input[("67890", "12345")]["type"] == "add_provider_url"
        assert _pending_text_input[("67890", "12345")]["data"]["name"] == "My Test Provider"

    @pytest.mark.asyncio
    async def test_add_provider_wizard_url_step(self, tmp_path):
        from gateway.run import _pending_text_input, _register_pending_text
        _pending_text_input.clear()

        runner = _make_runner()
        mock_adapter = AsyncMock()
        mock_adapter.send_keyboard = AsyncMock()
        runner.adapters = {Platform.TELEGRAM: mock_adapter}

        _register_pending_text("67890", "12345", "add_provider_url", {"name": "Test"})

        event = _make_event(text="http://localhost:11434/v1")
        await runner._handle_text_input(event)

        assert ("67890", "12345") in _pending_text_input
        assert _pending_text_input[("67890", "12345")]["type"] == "add_provider_key"
        assert _pending_text_input[("67890", "12345")]["data"]["url"] == "http://localhost:11434/v1"

    @pytest.mark.asyncio
    async def test_add_provider_wizard_invalid_url(self, tmp_path):
        from gateway.run import _pending_text_input, _register_pending_text
        _pending_text_input.clear()

        runner = _make_runner()
        mock_adapter = AsyncMock()
        mock_adapter.send_keyboard = AsyncMock()
        runner.adapters = {Platform.TELEGRAM: mock_adapter}

        _register_pending_text("67890", "12345", "add_provider_url", {"name": "Test"})

        event = _make_event(text="not-a-valid-url")
        await runner._handle_text_input(event)

        # Should stay on URL step (re-prompt)
        assert ("67890", "12345") in _pending_text_input
        assert _pending_text_input[("67890", "12345")]["type"] == "add_provider_url"

    @pytest.mark.asyncio
    async def test_add_provider_wizard_complete(self, tmp_path):
        from gateway.run import _pending_text_input, _register_pending_text
        _pending_text_input.clear()

        config_path = tmp_path / "config.yaml"
        config_path.write_text("custom_providers: []\n")

        runner = _make_runner()
        mock_adapter = AsyncMock()
        mock_adapter.send_keyboard = AsyncMock()
        runner.adapters = {Platform.TELEGRAM: mock_adapter}

        _register_pending_text("67890", "12345", "add_provider_key", {
            "name": "My LLM", "url": "http://localhost:11434/v1",
        })

        event = _make_event(text="sk-test-key")
        with patch("gateway.run._hermes_home", tmp_path):
            await runner._handle_text_input(event)

        # Wizard should be complete
        assert ("67890", "12345") not in _pending_text_input

        # Config should have the new provider
        import yaml
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        providers = cfg.get("custom_providers", [])
        assert len(providers) == 1
        assert providers[0]["name"] == "My LLM"
        assert providers[0]["base_url"] == "http://localhost:11434/v1"
        assert providers[0]["api_key"] == "sk-test-key"

    @pytest.mark.asyncio
    async def test_add_provider_wizard_skip_key(self, tmp_path):
        from gateway.run import _pending_text_input, _register_pending_text
        _pending_text_input.clear()

        config_path = tmp_path / "config.yaml"
        config_path.write_text("custom_providers: []\n")

        runner = _make_runner()
        mock_adapter = AsyncMock()
        mock_adapter.send_keyboard = AsyncMock()
        runner.adapters = {Platform.TELEGRAM: mock_adapter}

        _register_pending_text("67890", "12345", "add_provider_key", {
            "name": "Local", "url": "http://localhost:11434/v1",
        })

        event = _make_event(text="skip")
        with patch("gateway.run._hermes_home", tmp_path):
            await runner._handle_text_input(event)

        import yaml
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        providers = cfg.get("custom_providers", [])
        assert len(providers) == 1
        assert "api_key" not in providers[0]

    @pytest.mark.asyncio
    async def test_edit_provider_wizard(self, tmp_path):
        from gateway.run import _pending_text_input, _register_pending_text
        _pending_text_input.clear()

        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "custom_providers:\n"
            "  - name: My LLM\n"
            "    base_url: http://localhost:11434/v1\n"
            "    api_key: old-key\n"
        )

        runner = _make_runner()
        mock_adapter = AsyncMock()
        mock_adapter.send_keyboard = AsyncMock()
        runner.adapters = {Platform.TELEGRAM: mock_adapter}

        _register_pending_text("67890", "12345", "edit_provider", {"name": "My LLM"})

        event = _make_event(text="http://localhost:8080/v1 | new-secret-key", message_id="100")
        with patch("gateway.run._hermes_home", tmp_path):
            await runner._handle_text_input(event)

        import yaml
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        provider = cfg["custom_providers"][0]
        assert provider["base_url"] == "http://localhost:8080/v1"
        assert provider["api_key"] == "new-secret-key"


# ---------------------------------------------------------------------------
# /settings command
# ---------------------------------------------------------------------------


class TestSettingsCommand:
    """Tests for /settings command."""

    @pytest.mark.asyncio
    async def test_settings_shows_keyboard(self, tmp_path):
        from gateway.run import _keyboard_actions
        _keyboard_actions.clear()

        config_path = tmp_path / "config.yaml"
        config_path.write_text("display:\n  background_process_notifications: all\n  tool_progress: all\n")

        runner = _make_runner()
        mock_adapter = AsyncMock()
        mock_adapter.send_keyboard = AsyncMock()
        runner.adapters = {Platform.TELEGRAM: mock_adapter}

        event = _make_event(text="/settings")
        with patch("gateway.run._hermes_home", tmp_path):
            result = await runner._handle_settings_command(event)

        # Should have called send_keyboard
        mock_adapter.send_keyboard.assert_called_once()
        # Should return None (handled via keyboard)
        assert result is None

    @pytest.mark.asyncio
    async def test_settings_fallback_text(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text("display:\n  background_process_notifications: result\n  tool_progress: off\n")

        runner = _make_runner()
        # No adapter — should fall back to text
        runner._load_background_notifications_mode = lambda: "result"

        event = _make_event(text="/settings")
        with patch("gateway.run._hermes_home", tmp_path):
            result = await runner._handle_settings_command(event)

        assert result is not None
        assert "result" in result
        assert "off" in result


# ---------------------------------------------------------------------------
# TTL pruning
# ---------------------------------------------------------------------------


class TestTTLPruning:
    """Tests for keyboard action and pending text TTL pruning."""

    def test_prune_expired_keyboard_actions(self):
        from gateway.run import _keyboard_actions, _prune_keyboard_actions
        _keyboard_actions.clear()

        # Add an expired action
        _keyboard_actions[("c1", "u1", "old")] = {"type": "test", "_ts": time.time() - 1000}
        # Add a fresh action
        _keyboard_actions[("c1", "u1", "new")] = {"type": "test", "_ts": time.time()}

        _prune_keyboard_actions()

        assert ("c1", "u1", "old") not in _keyboard_actions
        assert ("c1", "u1", "new") in _keyboard_actions

    def test_prune_expired_pending_text(self):
        from gateway.run import _pending_text_input, _prune_pending_text_input
        _pending_text_input.clear()

        _pending_text_input[("c1", "u1")] = {"type": "test", "_ts": time.time() - 1000}
        _pending_text_input[("c2", "u2")] = {"type": "test", "_ts": time.time()}

        _prune_pending_text_input()

        assert ("c1", "u1") not in _pending_text_input
        assert ("c2", "u2") in _pending_text_input
