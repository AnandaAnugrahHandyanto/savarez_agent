from __future__ import annotations

from types import SimpleNamespace


def test_install_dependencies_normalizes_versioned_pip_specs_before_import_check(tmp_path, monkeypatch):
    from hermes_cli import memory_setup

    plugin_dir = tmp_path / "hindsight"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.yaml").write_text(
        'pip_dependencies:\n  - "hindsight-client>=0.6.1,<0.8"\n',
        encoding="utf-8",
    )

    imports: list[str] = []
    commands: list[list[str]] = []

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        imports.append(name)
        if name == "hindsight_client":
            return SimpleNamespace()
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("plugins.memory.find_provider_dir", lambda provider_name: plugin_dir)
    monkeypatch.setattr("builtins.__import__", fake_import)
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/uv" if name == "uv" else None)
    monkeypatch.setattr("subprocess.run", lambda cmd, **kwargs: commands.append(cmd) or SimpleNamespace(returncode=0))

    memory_setup._install_dependencies("hindsight")

    assert "hindsight_client" in imports
    assert commands == []
