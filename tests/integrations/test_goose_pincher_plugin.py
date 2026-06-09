"""Tests for the repo-local Goose Open Plugins hook extension."""

from __future__ import annotations

import json
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = ROOT / ".agents" / "plugins" / "hermes-pincher-hooks"


def test_goose_plugin_manifest_is_valid_open_plugin_metadata():
    manifest = json.loads((PLUGIN_ROOT / "plugin.json").read_text())

    assert manifest["name"] == "hermes-pincher-hooks"
    assert manifest["version"]
    assert "Pincher" in manifest["description"]


def test_goose_plugin_registers_pincher_pre_tool_hook_for_developer_tools():
    hooks = json.loads((PLUGIN_ROOT / "hooks" / "hooks.json").read_text())

    pre_tool_hooks = hooks["hooks"]["PreToolUse"]
    assert len(pre_tool_hooks) == 1

    entry = pre_tool_hooks[0]
    assert entry["matcher"] == "developer__shell|developer__text_editor"
    assert entry["hooks"] == [
        {
            "type": "command",
            "command": "${PLUGIN_ROOT}/scripts/pincher-hook-check.sh",
        }
    ]


def test_goose_pincher_hook_script_is_executable_and_uses_pincher_hook_check():
    script = PLUGIN_ROOT / "scripts" / "pincher-hook-check.sh"

    mode = script.stat().st_mode
    assert mode & stat.S_IXUSR

    text = script.read_text()
    assert "pincher hook-check" in text
    assert "PLUGIN_ROOT" in text


def test_goose_plugin_documents_project_scope_installation():
    readme = (PLUGIN_ROOT / "README.md").read_text()

    assert ".agents/plugins/hermes-pincher-hooks" in readme
    assert "goose session" in readme
    assert "PreToolUse" in readme
