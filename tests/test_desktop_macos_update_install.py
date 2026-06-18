import unittest
from pathlib import Path
from unittest import mock

import hermes_cli.main as main


def make_app(root: Path, marker: str) -> Path:
    app = root / "Hermes.app"
    exe = app / "Contents" / "MacOS" / "Hermes"
    exe.parent.mkdir(parents=True)
    exe.write_text(marker)
    return app


class DesktopMacosUpdateInstallTests(unittest.TestCase):
    def test_macos_update_installs_rebuilt_app_over_existing_bundle(self):
        with tempfile_dir() as tmp_path, mock.patch.object(main.sys, "platform", "darwin"), mock.patch.object(
            main.subprocess, "run", lambda *args, **kwargs: None
        ):
            rebuilt = make_app(tmp_path / "release" / "mac-arm64", "new renderer")
            target = make_app(tmp_path / "Applications", "old renderer")

            main._install_macos_desktop_app_bundle(rebuilt, target)

            self.assertEqual((target / "Contents" / "MacOS" / "Hermes").read_text(), "new renderer")
            self.assertFalse((target.parent / "Hermes.app.hermes-update-new").exists())
            self.assertFalse((target.parent / "Hermes.app.hermes-update-old").exists())

    def test_macos_update_installer_rolls_back_if_final_swap_fails(self):
        with tempfile_dir() as tmp_path, mock.patch.object(main.sys, "platform", "darwin"), mock.patch.object(
            main.subprocess, "run", lambda *args, **kwargs: None
        ):
            rebuilt = make_app(tmp_path / "release" / "mac-arm64", "new renderer")
            target = make_app(tmp_path / "Applications", "old renderer")
            original_rename = Path.rename

            def fail_tmp_into_target(self: Path, target_path: Path):
                if self.name == "Hermes.app.hermes-update-new":
                    raise OSError("simulated final swap failure")
                return original_rename(self, target_path)

            with mock.patch.object(Path, "rename", fail_tmp_into_target):
                with self.assertRaisesRegex(OSError, "simulated final swap failure"):
                    main._install_macos_desktop_app_bundle(rebuilt, target)

            self.assertEqual((target / "Contents" / "MacOS" / "Hermes").read_text(), "old renderer")
            self.assertFalse((target.parent / "Hermes.app.hermes-update-new").exists())

    def test_sync_macos_installed_desktop_app_uses_existing_installed_targets(self):
        with tempfile_dir() as tmp_path, mock.patch.object(main.sys, "platform", "darwin"), mock.patch.object(
            main.subprocess, "run", lambda *args, **kwargs: None
        ):
            desktop_dir = tmp_path / "apps" / "desktop"
            rebuilt = make_app(desktop_dir / "release" / "mac-arm64", "new contract")
            target = make_app(tmp_path / "Applications", "stale contract")

            with mock.patch.object(main, "_desktop_macos_built_app_bundle", lambda _desktop_dir: rebuilt), mock.patch.object(
                main, "_desktop_macos_installed_app_candidates", lambda: [target]
            ):
                main._sync_macos_installed_desktop_app(desktop_dir)

            self.assertEqual((target / "Contents" / "MacOS" / "Hermes").read_text(), "new contract")


class tempfile_dir:
    def __enter__(self) -> Path:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        return Path(self._tmp.name)

    def __exit__(self, exc_type, exc, tb):
        self._tmp.cleanup()
        return False


if __name__ == "__main__":
    unittest.main()
