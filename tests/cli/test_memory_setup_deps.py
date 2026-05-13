"""Test _install_dependencies return value and caller abort behavior.

Covers: https://github.com/NousResearch/hermes-agent/issues/25086
"""

from __future__ import annotations

import importlib
import sys
from unittest import mock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reload_module():
    """Force-reload memory_setup so patches take effect."""
    mod_name = "hermes_cli.memory_setup"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    return importlib.import_module(mod_name)


def _make_import_raise(names_to_fail):
    """Return an __import__ wrapper that raises ImportError for given module names."""
    original_import = __import__

    def _custom_import(name, *args, **kwargs):
        if name in names_to_fail:
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    return _custom_import


# ---------------------------------------------------------------------------
# _install_dependencies unit tests
# ---------------------------------------------------------------------------

class TestInstallDependencies:
    """Unit tests for _install_dependencies(provider_name) -> bool."""

    def test_returns_true_when_no_plugin_dir(self):
        """Provider without a plugin directory → no deps to check → True."""
        mod = _reload_module()
        with mock.patch("plugins.memory.find_provider_dir", return_value=None):
            assert mod._install_dependencies("nonexistent") is True

    def test_returns_true_when_no_plugin_yaml(self, tmp_path):
        """Provider with plugin dir but no plugin.yaml → no deps declared → True."""
        mod = _reload_module()
        with mock.patch("plugins.memory.find_provider_dir", return_value=tmp_path):
            assert mod._install_dependencies("testprov") is True

    def test_returns_true_when_no_pip_deps(self, tmp_path):
        """Provider with plugin.yaml but empty pip_dependencies → True."""
        mod = _reload_module()
        yaml_file = tmp_path / "plugin.yaml"
        yaml_file.write_text("name: testprov\npip_dependencies: []\n")
        with mock.patch("plugins.memory.find_provider_dir", return_value=tmp_path):
            assert mod._install_dependencies("testprov") is True

    def test_returns_true_when_deps_already_importable(self, tmp_path):
        """All deps already installed → True (no install attempted)."""
        mod = _reload_module()
        yaml_file = tmp_path / "plugin.yaml"
        yaml_file.write_text("name: testprov\npip_dependencies:\n  - json\n")
        with mock.patch("plugins.memory.find_provider_dir", return_value=tmp_path):
            assert mod._install_dependencies("testprov") is True

    def test_returns_true_on_successful_install(self, tmp_path):
        """Missing deps installed successfully → True."""
        mod = _reload_module()
        yaml_file = tmp_path / "plugin.yaml"
        yaml_file.write_text("name: testprov\npip_dependencies:\n  - fake-pkg-xyz\n")
        with mock.patch("plugins.memory.find_provider_dir", return_value=tmp_path):
            with mock.patch("builtins.__import__",
                            side_effect=_make_import_raise({"fake_pkg_xyz"})):
                with mock.patch("shutil.which", return_value="/usr/bin/uv"):
                    with mock.patch("subprocess.run"):
                        result = mod._install_dependencies("testprov")
        assert result is True

    def test_returns_false_when_uv_not_found(self, tmp_path):
        """Missing deps and uv not available → False."""
        mod = _reload_module()
        yaml_file = tmp_path / "plugin.yaml"
        yaml_file.write_text("name: testprov\npip_dependencies:\n  - fake-pkg-xyz\n")
        with mock.patch("plugins.memory.find_provider_dir", return_value=tmp_path):
            with mock.patch("builtins.__import__",
                            side_effect=_make_import_raise({"fake_pkg_xyz"})):
                with mock.patch("shutil.which", return_value=None):
                    result = mod._install_dependencies("testprov")
        assert result is False

    def test_returns_false_on_install_failure(self, tmp_path):
        """Missing deps and install fails → False."""
        import subprocess
        mod = _reload_module()
        yaml_file = tmp_path / "plugin.yaml"
        yaml_file.write_text("name: testprov\npip_dependencies:\n  - fake-pkg-xyz\n")
        with mock.patch("plugins.memory.find_provider_dir", return_value=tmp_path):
            with mock.patch("builtins.__import__",
                            side_effect=_make_import_raise({"fake_pkg_xyz"})):
                with mock.patch("shutil.which", return_value="/usr/bin/uv"):
                    with mock.patch("subprocess.run",
                                    side_effect=subprocess.CalledProcessError(1, "uv")):
                        result = mod._install_dependencies("testprov")
        assert result is False


# ---------------------------------------------------------------------------
# cmd_setup_provider abort-on-failure tests
# ---------------------------------------------------------------------------

class TestSetupProviderAbort:
    """Verify cmd_setup_provider aborts when deps are not importable."""

    def test_abort_on_dep_failure(self, capsys):
        """cmd_setup_provider should print abort message and return early."""
        mod = _reload_module()

        with mock.patch.object(mod, "_install_dependencies", return_value=False):
            with mock.patch.object(mod, "_get_available_providers",
                                  return_value=[("mem0", "api key", mock.MagicMock())]):
                mod.cmd_setup_provider("mem0")

        captured = capsys.readouterr()
        assert "Setup aborted" in captured.out
        assert "not importable" in captured.out

    def test_proceeds_on_dep_success(self, tmp_path, capsys):
        """cmd_setup_provider should proceed past dep check when True."""
        mod = _reload_module()

        fake_provider = mock.MagicMock()
        fake_provider.post_setup = mock.MagicMock()

        with mock.patch.object(mod, "_install_dependencies", return_value=True):
            with mock.patch.object(mod, "_get_available_providers",
                                  return_value=[("mem0", "api key", fake_provider)]):
                with mock.patch("hermes_cli.memory_setup.get_hermes_home",
                                return_value=tmp_path):
                    with mock.patch("hermes_cli.config.load_config",
                                    return_value={"memory": {}}):
                        mod.cmd_setup_provider("mem0")

        captured = capsys.readouterr()
        assert "Setup aborted" not in captured.out
