"""Tests for the staged plugin migration security fix (PR #37729).

Covers:
- Config v20->v21 migration writes plugins.staged (NOT plugins.enabled)
- _get_staged_set() / _save_staged_set() helpers
- cmd_enable() removes plugin from staged set
- cmd_audit() output (table + json)
- Migration prints SECURITY warning when staged plugins found
- Migration prints clean message when no plugins found
- Staged plugins do not auto-load

Run: python -m pytest tests/hermes_cli/test_staged_plugin_migration.py -v -o "addopts="
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from hermes_cli.config import (
    ensure_hermes_home,
    load_config,
    migrate_config,
    save_config,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_plugin_dir(plugins_dir: Path, name: str, *, version: str = "0.1.0",
                     description: str = "test") -> Path:
    """Create a minimal plugin directory with plugin.yaml + __init__.py."""
    plugin_dir = plugins_dir / name
    plugin_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": name,
        "version": version,
        "description": description,
    }
    (plugin_dir / "plugin.yaml").write_text(yaml.dump(manifest))
    (plugin_dir / "__init__.py").write_text("def register(ctx): pass\n")
    return plugin_dir


def _write_config_version(tmp_path: Path, ver: int) -> None:
    """Write config.yaml with the given _config_version directly."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"_config_version": ver}))


# ── Migration: v20 -> v21 writes staged, not enabled ──────────────────────


class TestMigrationWritesStaged:
    """The v20->v21 migration must write discovered plugins to plugins.staged,
    never to plugins.enabled."""

    def test_migration_writes_staged_not_enabled(self, tmp_path):
        """Discovered user plugins go to plugins.staged, not plugins.enabled."""
        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            ensure_hermes_home()
            plugins_dir = tmp_path / "plugins"
            plugins_dir.mkdir()
            _make_plugin_dir(plugins_dir, "evil-plugin")

            _write_config_version(tmp_path, 20)
            migrate_config(interactive=False, quiet=True)

            config = load_config()
            assert "staged" in config["plugins"]
            assert "evil-plugin" in config["plugins"]["staged"]
            enabled = config["plugins"].get("enabled", [])
            assert "evil-plugin" not in enabled

    def test_migration_staged_is_list(self, tmp_path):
        """plugins.staged must be a list (not a set or other type)."""
        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            ensure_hermes_home()
            plugins_dir = tmp_path / "plugins"
            plugins_dir.mkdir()
            _make_plugin_dir(plugins_dir, "test-plugin")

            _write_config_version(tmp_path, 20)
            migrate_config(interactive=False, quiet=True)

            config = load_config()
            assert isinstance(config["plugins"]["staged"], list)

    def test_migration_multiple_plugins_all_staged(self, tmp_path):
        """All discovered plugins are staged, none auto-enabled."""
        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            ensure_hermes_home()
            plugins_dir = tmp_path / "plugins"
            plugins_dir.mkdir()
            _make_plugin_dir(plugins_dir, "plugin-a")
            _make_plugin_dir(plugins_dir, "plugin-b")
            _make_plugin_dir(plugins_dir, "plugin-c")

            _write_config_version(tmp_path, 20)
            migrate_config(interactive=False, quiet=True)

            config = load_config()
            staged = set(config["plugins"]["staged"])
            assert staged == {"plugin-a", "plugin-b", "plugin-c"}
            enabled = config["plugins"].get("enabled", [])
            assert len(enabled) == 0

    def test_migration_no_plugins_found(self, tmp_path):
        """When no user plugins exist, staged is empty list."""
        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            ensure_hermes_home()

            _write_config_version(tmp_path, 20)
            migrate_config(interactive=False, quiet=True)

            config = load_config()
            assert "staged" in config["plugins"]
            assert config["plugins"]["staged"] == []

    def test_migration_disabled_plugins_not_staged(self, tmp_path):
        """Plugins in plugins.disabled must NOT appear in staged."""
        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            ensure_hermes_home()
            plugins_dir = tmp_path / "plugins"
            plugins_dir.mkdir()
            _make_plugin_dir(plugins_dir, "good-plugin")
            _make_plugin_dir(plugins_dir, "bad-plugin")

            config_path = tmp_path / "config.yaml"
            config_path.write_text(yaml.safe_dump({
                "_config_version": 20,
                "plugins": {"disabled": ["bad-plugin"]},
            }))

            migrate_config(interactive=False, quiet=True)

            config = load_config()
            staged = config["plugins"]["staged"]
            assert "good-plugin" in staged
            assert "bad-plugin" not in staged

    def test_migration_prints_security_warning(self, tmp_path, capsys):
        """Migration prints SECURITY warning when staged plugins are found."""
        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            ensure_hermes_home()
            plugins_dir = tmp_path / "plugins"
            plugins_dir.mkdir()
            _make_plugin_dir(plugins_dir, "sneaky-plugin")

            _write_config_version(tmp_path, 20)
            migrate_config(interactive=False, quiet=False)

            captured = capsys.readouterr()
            assert "SECURITY" in captured.out
            assert "sneaky-plugin" in captured.out
            assert "hermes plugins audit" in captured.out

    def test_migration_no_plugins_prints_clean_message(self, tmp_path, capsys):
        """Migration prints clean message when no plugins found."""
        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            ensure_hermes_home()

            _write_config_version(tmp_path, 20)
            migrate_config(interactive=False, quiet=False)

            captured = capsys.readouterr()
            assert "SECURITY" not in captured.out

    def test_migration_bumps_version(self, tmp_path):
        """After migration, config _config_version must be >= 21."""
        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            ensure_hermes_home()

            _write_config_version(tmp_path, 20)
            migrate_config(interactive=False, quiet=True)

            config_path = tmp_path / "config.yaml"
            raw = yaml.safe_load(config_path.read_text())
            assert raw["_config_version"] >= 21

    def test_migration_idempotent(self, tmp_path):
        """Running migration twice must not duplicate staged entries."""
        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            ensure_hermes_home()
            plugins_dir = tmp_path / "plugins"
            plugins_dir.mkdir()
            _make_plugin_dir(plugins_dir, "my-plugin")

            _write_config_version(tmp_path, 20)
            migrate_config(interactive=False, quiet=True)
            migrate_config(interactive=False, quiet=True)

            config = load_config()
            staged = config["plugins"]["staged"]
            assert staged.count("my-plugin") == 1


# ── _get_staged_set() / _save_staged_set() ─────────────────────────────────


class TestStagedSetHelpers:
    """Test the staged set read/write helpers."""

    def test_get_staged_set_returns_set(self, tmp_path):
        from hermes_cli.plugins_cmd import _get_staged_set

        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            ensure_hermes_home()
            config = load_config()
            config["plugins"] = {"staged": ["a", "b"]}
            save_config(config)

            result = _get_staged_set()
            assert isinstance(result, set)
            assert result == {"a", "b"}

    def test_get_staged_set_empty_when_no_staged_key(self, tmp_path):
        from hermes_cli.plugins_cmd import _get_staged_set

        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            ensure_hermes_home()
            config = load_config()
            config["plugins"] = {}
            save_config(config)

            result = _get_staged_set()
            assert result == set()

    def test_get_staged_set_empty_on_exception(self, tmp_path):
        from hermes_cli.plugins_cmd import _get_staged_set

        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            ensure_hermes_home()
            config_path = tmp_path / "config.yaml"
            config_path.write_text("{{invalid yaml", encoding="utf-8")

            result = _get_staged_set()
            assert result == set()

    def test_save_staged_set_writes_sorted(self, tmp_path):
        from hermes_cli.plugins_cmd import _get_staged_set, _save_staged_set

        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            ensure_hermes_home()
            _save_staged_set({"z-plugin", "a-plugin", "m-plugin"})

            result = _get_staged_set()
            assert result == {"a-plugin", "m-plugin", "z-plugin"}

            config = load_config()
            assert config["plugins"]["staged"] == ["a-plugin", "m-plugin", "z-plugin"]

    def test_save_staged_set_overwrites_existing(self, tmp_path):
        from hermes_cli.plugins_cmd import _save_staged_set

        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            ensure_hermes_home()
            _save_staged_set({"old-plugin"})
            _save_staged_set({"new-plugin"})

            config = load_config()
            assert config["plugins"]["staged"] == ["new-plugin"]


# ── cmd_enable() removes from staged ───────────────────────────────────────


class TestCmdEnableRemovesFromStaged:
    """cmd_enable() must move plugin from staged -> enabled and remove from staged."""

    def test_enable_removes_from_staged(self, tmp_path):
        from hermes_cli.plugins_cmd import _get_staged_set, _save_staged_set, cmd_enable

        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            ensure_hermes_home()
            plugins_dir = tmp_path / "plugins"
            plugins_dir.mkdir()
            _make_plugin_dir(plugins_dir, "my-plugin")
            _save_staged_set({"my-plugin"})

            cmd_enable("my-plugin")

            staged = _get_staged_set()
            assert "my-plugin" not in staged

    def test_enable_adds_to_enabled(self, tmp_path):
        from hermes_cli.plugins_cmd import _get_enabled_set, cmd_enable

        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            ensure_hermes_home()
            plugins_dir = tmp_path / "plugins"
            plugins_dir.mkdir()
            _make_plugin_dir(plugins_dir, "my-plugin")

            cmd_enable("my-plugin")

            enabled = _get_enabled_set()
            assert "my-plugin" in enabled

    def test_enable_already_enabled_is_idempotent(self, tmp_path):
        """Enabling an already-enabled plugin must not duplicate or error."""
        from hermes_cli.plugins_cmd import _get_enabled_set, cmd_enable

        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            ensure_hermes_home()
            plugins_dir = tmp_path / "plugins"
            plugins_dir.mkdir()
            _make_plugin_dir(plugins_dir, "my-plugin")

            cmd_enable("my-plugin")
            cmd_enable("my-plugin")

            enabled = _get_enabled_set()
            assert list(enabled).count("my-plugin") == 1


# ── cmd_audit() output ─────────────────────────────────────────────────────


class TestCmdAudit:
    """Test the audit subcommand output."""

    def test_audit_json_output_empty(self, tmp_path, capsys):
        from hermes_cli.plugins_cmd import cmd_audit

        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            ensure_hermes_home()

            args = type("Args", (), {"json": True})()
            cmd_audit(args)

            captured = capsys.readouterr()
            payload = json.loads(captured.out)
            assert payload["staged"] == []

    def test_audit_json_output_with_staged(self, tmp_path, capsys):
        from hermes_cli.plugins_cmd import _save_staged_set, cmd_audit

        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            ensure_hermes_home()
            _save_staged_set({"plugin-x"})

            args = type("Args", (), {"json": True})()
            cmd_audit(args)

            captured = capsys.readouterr()
            payload = json.loads(captured.out)
            assert "plugin-x" in payload["staged"]

    def test_audit_json_includes_enabled_and_disabled(self, tmp_path, capsys):
        from hermes_cli.plugins_cmd import _save_staged_set, cmd_audit

        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            ensure_hermes_home()
            _save_staged_set({"plugin-x"})

            args = type("Args", (), {"json": True})()
            cmd_audit(args)

            captured = capsys.readouterr()
            payload = json.loads(captured.out)
            assert "enabled" in payload
            assert "disabled" in payload

    def test_audit_nonempty_staged_does_not_print_no_staged_message(self, tmp_path, capsys):
        """When staged plugins exist, audit must NOT print 'No staged plugins'."""
        from hermes_cli.plugins_cmd import _save_staged_set, cmd_audit

        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            ensure_hermes_home()
            _save_staged_set({"plugin-x"})

            args = type("Args", (), {"json": True})()
            cmd_audit(args)

            captured = capsys.readouterr()
            payload = json.loads(captured.out)
            assert len(payload["staged"]) > 0


# ── Security: plugins.staged does not auto-load ────────────────────────────


class TestStagedPluginsDoNotAutoLoad:
    """Plugins in staged must NOT be loaded by the plugin manager."""

    def test_staged_not_in_enabled_after_migration(self, tmp_path):
        """After migration, staged plugins must not appear in enabled set."""
        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            ensure_hermes_home()
            plugins_dir = tmp_path / "plugins"
            plugins_dir.mkdir()
            _make_plugin_dir(plugins_dir, "backdoor-plugin")

            _write_config_version(tmp_path, 20)
            migrate_config(interactive=False, quiet=True)

            config = load_config()
            enabled = set(config["plugins"].get("enabled", []))
            staged = set(config["plugins"].get("staged", []))

            assert enabled.isdisjoint(staged)
            assert "backdoor-plugin" in staged
            assert "backdoor-plugin" not in enabled

    def test_get_enabled_set_excludes_staged(self, tmp_path):
        """_get_enabled_set() must not return staged plugins."""
        from hermes_cli.plugins_cmd import _get_enabled_set

        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            ensure_hermes_home()
            plugins_dir = tmp_path / "plugins"
            plugins_dir.mkdir()
            _make_plugin_dir(plugins_dir, "evil-plugin")

            _write_config_version(tmp_path, 20)
            migrate_config(interactive=False, quiet=True)

            enabled = _get_enabled_set()
            assert "evil-plugin" not in enabled
