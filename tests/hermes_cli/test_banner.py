"""Tests for banner toolset name normalization and skin color usage."""

from unittest.mock import patch

from rich.console import Console

import hermes_cli.banner as banner
import model_tools
import tools.mcp_tool


def test_display_toolset_name_strips_legacy_suffix():
    assert banner._display_toolset_name("homeassistant_tools") == "homeassistant"
    assert banner._display_toolset_name("honcho_tools") == "honcho"
    assert banner._display_toolset_name("web_tools") == "web"


def test_display_toolset_name_preserves_clean_names():
    assert banner._display_toolset_name("browser") == "browser"
    assert banner._display_toolset_name("file") == "file"
    assert banner._display_toolset_name("terminal") == "terminal"


def test_display_toolset_name_handles_empty():
    assert banner._display_toolset_name("") == "unknown"
    assert banner._display_toolset_name(None) == "unknown"


def test_build_welcome_banner_uses_normalized_toolset_names():
    """Unavailable toolsets should not have '_tools' appended in banner output."""
    with (
        patch.object(
            model_tools,
            "check_tool_availability",
            return_value=(
                ["web"],
                [
                    {"name": "homeassistant", "tools": ["ha_call_service"]},
                    {"name": "honcho", "tools": ["honcho_conclude"]},
                ],
            ),
        ),
        patch.object(banner, "get_available_skills", return_value={}),
        patch.object(banner, "get_update_result", return_value=None),
        patch.object(tools.mcp_tool, "get_mcp_status", return_value=[]),
    ):
        console = Console(
            record=True, force_terminal=False, color_system=None, width=160
        )
        banner.build_welcome_banner(
            console=console,
            model="anthropic/test-model",
            cwd="/tmp/project",
            tools=[
                {"function": {"name": "web_search"}},
                {"function": {"name": "read_file"}},
            ],
            get_toolset_for_tool=lambda name: {
                "web_search": "web_tools",
                "read_file": "file",
            }.get(name),
        )

    output = console.export_text()
    assert "homeassistant:" in output
    assert "honcho:" in output
    assert "web:" in output
    assert "homeassistant_tools:" not in output
    assert "honcho_tools:" not in output
    assert "web_tools:" not in output


def test_tint_default_banner_art_replaces_legacy_gold_palette():
    sample = "[bold #FFD700]A[/] [#FFBF00]B[/] [#CD7F32]C[/] [dim #B8860B]D[/] [#FFF8DC]E[/]"

    with patch.object(
        banner,
        "_skin_color",
        side_effect=lambda key, fallback: {
            "banner_title": "#111111",
            "banner_accent": "#222222",
            "banner_border": "#333333",
            "banner_dim": "#444444",
            "banner_text": "#555555",
        }.get(key, fallback),
    ):
        tinted = banner._tint_default_banner_art(sample)

    assert "#111111" in tinted
    assert "#222222" in tinted
    assert "#333333" in tinted
    assert "#444444" in tinted
    assert "#555555" in tinted
    assert "#FFD700" not in tinted
    assert "#FFBF00" not in tinted
    assert "#CD7F32" not in tinted
    assert "#B8860B" not in tinted
    assert "#FFF8DC" not in tinted
