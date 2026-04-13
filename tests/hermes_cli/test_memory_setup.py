"""Tests for hermes memory setup provider discovery and dependency resolution."""

import os
import sys
from pathlib import Path
from unittest.mock import patch


def _make_user_memory_plugin(name: str, hermes_home: Path, plugin_yaml: str) -> Path:
    plugin_dir = hermes_home / "plugins" / name
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "__init__.py").write_text(
        "from agent.memory_provider import MemoryProvider\n"
        "\n"
        "class TestProvider(MemoryProvider):\n"
        "    @property\n"
        "    def name(self):\n"
        f"        return {name!r}\n"
        "    def is_available(self):\n"
        "        return True\n"
        "    def initialize(self, session_id, **kwargs):\n"
        "        pass\n"
        "    def get_tool_schemas(self):\n"
        "        return []\n"
        "\n"
        "def register(ctx):\n"
        "    ctx.register_memory_provider(TestProvider())\n"
    )
    (plugin_dir / "plugin.yaml").write_text(plugin_yaml)
    return plugin_dir


def test_install_dependencies_reads_user_plugin_manifest(tmp_path, monkeypatch):
    """Dependency installation should use the user-installed provider manifest."""
    hermes_home = Path(os.environ["HERMES_HOME"])
    plugin_name = "brainctl_deps"
    _make_user_memory_plugin(
        plugin_name,
        hermes_home,
        "name: brainctl_deps\n"
        "pip_dependencies:\n"
        "  - totally-missing-package\n",
    )

    import hermes_cli.memory_setup as memory_setup

    original_import = __import__

    def _fake_import(name, *args, **kwargs):
        if name == "totally_missing_package":
            raise ImportError("missing on purpose")
        return original_import(name, *args, **kwargs)

    with (
        patch("builtins.__import__", side_effect=_fake_import),
        patch("shutil.which", return_value="/usr/bin/uv"),
        patch("subprocess.run") as mock_run,
    ):
        memory_setup._install_dependencies(plugin_name)

    assert mock_run.called
    install_cmd = mock_run.call_args.args[0]
    assert install_cmd[:4] == ["/usr/bin/uv", "pip", "install", "--python"]
    assert "totally-missing-package" in install_cmd
    sys.modules.pop(f"plugins.memory.{plugin_name}", None)
