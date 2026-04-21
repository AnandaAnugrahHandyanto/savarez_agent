"""Regression tests for WhatsApp setup dependency repair."""

import os
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch


def _touch_baileys(root: Path) -> None:
    pkg = root / "node_modules" / "@whiskeysockets" / "baileys" / "package.json"
    pkg.parent.mkdir(parents=True, exist_ok=True)
    pkg.write_text("{}")


def test_need_install_when_baileys_missing(tmp_path: Path) -> None:
    import hermes_cli.main as main_mod

    (tmp_path / "node_modules").mkdir()
    (tmp_path / "package-lock.json").write_text("{}")

    assert main_mod._whatsapp_bridge_need_npm_install(tmp_path) is True


def test_need_install_when_lock_newer_than_marker(tmp_path: Path) -> None:
    import hermes_cli.main as main_mod

    _touch_baileys(tmp_path)
    (tmp_path / "package-lock.json").write_text("{}")
    (tmp_path / "node_modules" / ".package-lock.json").write_text("{}")
    os.utime(tmp_path / "package-lock.json", (200, 200))
    os.utime(tmp_path / "node_modules" / ".package-lock.json", (100, 100))

    assert main_mod._whatsapp_bridge_need_npm_install(tmp_path) is True


def test_no_install_when_baileys_present_and_marker_current(tmp_path: Path) -> None:
    import hermes_cli.main as main_mod

    _touch_baileys(tmp_path)
    (tmp_path / "package-lock.json").write_text("{}")
    (tmp_path / "node_modules" / ".package-lock.json").write_text("{}")
    os.utime(tmp_path / "package-lock.json", (100, 100))
    os.utime(tmp_path / "node_modules" / ".package-lock.json", (200, 200))

    assert main_mod._whatsapp_bridge_need_npm_install(tmp_path) is False


def test_cmd_whatsapp_repairs_partial_bridge_install(tmp_path: Path, capsys) -> None:
    import hermes_cli.main as main_mod

    project_root = tmp_path / "repo"
    bridge_dir = project_root / "scripts" / "whatsapp-bridge"
    bridge_dir.mkdir(parents=True)
    (bridge_dir / "bridge.js").write_text("// bridge")
    (bridge_dir / "package.json").write_text("{}")
    (bridge_dir / "package-lock.json").write_text("{}")
    (bridge_dir / "node_modules").mkdir()

    fake_main = project_root / "hermes_cli" / "main.py"
    fake_main.parent.mkdir(parents=True)
    fake_main.write_text("# test shim")

    env = {}

    def fake_get_env_value(key):
        return env.get(key, "")

    def fake_save_env_value(key, value):
        env[key] = value

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return MagicMock(returncode=0, stderr="")

    with (
        patch.object(main_mod, "__file__", str(fake_main)),
        patch.object(main_mod, "_require_tty"),
        patch.object(main_mod, "get_hermes_home", return_value=tmp_path / ".hermes"),
        patch.object(main_mod.shutil, "which", return_value="/usr/bin/npm"),
        patch.object(main_mod.subprocess, "run", side_effect=fake_run),
        patch("hermes_cli.config.get_env_value", side_effect=fake_get_env_value),
        patch("hermes_cli.config.save_env_value", side_effect=fake_save_env_value),
        patch("builtins.input", side_effect=["2", "189984136"]),
    ):
        main_mod.cmd_whatsapp(Namespace())

    out = capsys.readouterr().out
    assert "✓ Dependencies installed" in out
    assert "✓ Bridge dependencies already installed" not in out
    assert calls[0][:2] == ["/usr/bin/npm", "install"]

