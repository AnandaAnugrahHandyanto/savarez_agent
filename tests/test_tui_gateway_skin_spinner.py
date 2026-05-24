"""Tests for TUI gateway skin spinner integration.

These tests verify that the TUI gateway properly passes skin spinner configuration
(thinking_verbs, thinking_faces) to the frontend.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestResolveSkinSpinner:
    """Tests for resolve_skin() including spinner config in payload."""

    @pytest.fixture
    def mock_skin(self):
        """Create a mock skin with spinner configuration."""
        skin = MagicMock()
        skin.name = "test_skin"
        skin.colors = {"banner_title": "#FFD700"}
        skin.branding = {"agent_name": "Test Agent"}
        skin.banner_logo = "test logo"
        skin.banner_hero = "test hero"
        skin.tool_prefix = "|"
        skin.spinner = {
            "thinking_verbs": ["custom_verb1", "custom_verb2", "custom_verb3"],
            "thinking_faces": ["(¬‿¬)", "(⌐■_■)"],
            "waiting_faces": ["(¬_¬)"],
            "wings": [["<<", ">>"]],
        }
        skin.tool_emojis = {"terminal": "⚡"}
        return skin

    def test_resolve_skin_includes_spinner_config(self, mock_skin):
        """Verify resolve_skin() includes spinner in the returned payload."""
        from tui_gateway.server import resolve_skin

        with patch("tui_gateway.server._load_cfg") as mock_load_cfg, \
             patch("hermes_cli.skin_engine.init_skin_from_config") as mock_init, \
             patch("hermes_cli.skin_engine.get_active_skin", return_value=mock_skin):

            mock_load_cfg.return_value = {"display": {"skin": "test_skin"}}

            result = resolve_skin()

            assert "spinner" in result
            assert result["spinner"] == mock_skin.spinner
            assert result["spinner"]["thinking_verbs"] == ["custom_verb1", "custom_verb2", "custom_verb3"]
            assert result["spinner"]["thinking_faces"] == ["(¬‿¬)", "(⌐■_■)"]

    def test_resolve_skin_includes_tool_emojis(self, mock_skin):
        """Verify resolve_skin() includes tool_emojis in the returned payload."""
        from tui_gateway.server import resolve_skin

        with patch("tui_gateway.server._load_cfg") as mock_load_cfg, \
             patch("hermes_cli.skin_engine.init_skin_from_config") as mock_init, \
             patch("hermes_cli.skin_engine.get_active_skin", return_value=mock_skin):

            mock_load_cfg.return_value = {"display": {"skin": "test_skin"}}

            result = resolve_skin()

            assert "tool_emojis" in result
            assert result["tool_emojis"] == {"terminal": "⚡"}

    def test_resolve_skin_handles_empty_spinner(self):
        """Verify resolve_skin() handles skins without spinner config."""
        from tui_gateway.server import resolve_skin

        mock_skin = MagicMock()
        mock_skin.name = "minimal_skin"
        mock_skin.colors = {}
        mock_skin.branding = {}
        mock_skin.banner_logo = ""
        mock_skin.banner_hero = ""
        mock_skin.tool_prefix = ""
        mock_skin.spinner = {}
        mock_skin.tool_emojis = {}

        with patch("tui_gateway.server._load_cfg") as mock_load_cfg, \
             patch("hermes_cli.skin_engine.init_skin_from_config") as mock_init, \
             patch("hermes_cli.skin_engine.get_active_skin", return_value=mock_skin):

            mock_load_cfg.return_value = {"display": {"skin": "minimal_skin"}}

            result = resolve_skin()

            assert "spinner" in result
            assert result["spinner"] == {}
            assert "tool_emojis" in result
            assert result["tool_emojis"] == {}

    def test_resolve_skin_handles_skin_engine_failure(self):
        """Verify resolve_skin() returns empty dict when skin engine fails."""
        from tui_gateway.server import resolve_skin

        with patch("tui_gateway.server._load_cfg") as mock_load_cfg, \
             patch("hermes_cli.skin_engine.init_skin_from_config") as mock_init, \
             patch("hermes_cli.skin_engine.get_active_skin", side_effect=Exception("skin error")):

            mock_load_cfg.return_value = {"display": {"skin": "broken"}}

            result = resolve_skin()

            assert result == {}

    def test_resolve_skin_preserves_other_skin_fields(self, mock_skin):
        """Verify resolve_skin() still includes all other skin fields."""
        from tui_gateway.server import resolve_skin

        with patch("tui_gateway.server._load_cfg") as mock_load_cfg, \
             patch("hermes_cli.skin_engine.init_skin_from_config") as mock_init, \
             patch("hermes_cli.skin_engine.get_active_skin", return_value=mock_skin):

            mock_load_cfg.return_value = {"display": {"skin": "test_skin"}}

            result = resolve_skin()

            # Verify all expected fields are present
            assert result["name"] == "test_skin"
            assert result["colors"] == {"banner_title": "#FFD700"}
            assert result["branding"] == {"agent_name": "Test Agent"}
            assert result["banner_logo"] == "test logo"
            assert result["banner_hero"] == "test hero"
            assert result["tool_prefix"] == "|"
            assert "help_header" in result
