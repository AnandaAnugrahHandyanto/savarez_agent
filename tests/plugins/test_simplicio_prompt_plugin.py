from __future__ import annotations

from pathlib import Path

import yaml


def _clear_flags(monkeypatch):
    monkeypatch.delenv("SIMPLICIO_PROMPT", raising=False)
    monkeypatch.delenv("HERMES_SIMPLICIO_PROMPT", raising=False)


def test_simplicio_prompt_disabled_by_default(monkeypatch):
    _clear_flags(monkeypatch)

    from plugins import simplicio_prompt as sp

    assert sp.build_context(config={}) is None


def test_simplicio_prompt_enabled_by_env(monkeypatch):
    _clear_flags(monkeypatch)
    monkeypatch.setenv("SIMPLICIO_PROMPT", "true")

    from plugins import simplicio_prompt as sp

    payload = sp.build_context(config={})

    assert payload is not None
    assert payload["context"].startswith("[SIMPLICIO_PROMPT]")
    assert "Default response" in payload["context"]
    assert "[Próximo Yool a executar]" in payload["context"]


def test_simplicio_prompt_enabled_by_config(monkeypatch):
    _clear_flags(monkeypatch)

    from plugins import simplicio_prompt as sp

    payload = sp.build_context(config={"simplicio_prompt": {"enabled": True}})

    assert payload is not None
    assert "tuple-space" in payload["context"]


def test_simplicio_prompt_enabled_by_plugin_allow_list(monkeypatch):
    _clear_flags(monkeypatch)

    from plugins import simplicio_prompt as sp

    payload = sp.build_context(config={"plugins": {"enabled": ["SIMPLICIO_PROMPT"]}})

    assert payload is not None
    assert "Respect provider limits" in payload["context"]


def test_simplicio_prompt_registers_pre_llm_hook():
    from plugins import simplicio_prompt as sp

    class FakeContext:
        def __init__(self):
            self.hooks = []

        def register_hook(self, name, callback):
            self.hooks.append((name, callback))

    ctx = FakeContext()
    sp.register(ctx)

    assert len(ctx.hooks) == 1
    assert ctx.hooks[0][0] == "pre_llm_call"
    assert ctx.hooks[0][1] is sp._pre_llm_call


def _write_hook_plugin(root: Path, *, manifest: dict) -> None:
    plugin_dir = root / manifest["name"]
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    (plugin_dir / "__init__.py").write_text(
        "def register(ctx):\n"
        "    ctx.register_hook('pre_llm_call', lambda **kw: {'context': 'auto'})\n",
        encoding="utf-8",
    )


def test_bundled_plugin_auto_enables_from_manifest_env_gate(tmp_path, monkeypatch):
    from hermes_cli.plugins import PluginManager

    bundled = tmp_path / "bundled"
    _write_hook_plugin(
        bundled,
        manifest={
            "name": "auto_prompt_env",
            "hooks": ["pre_llm_call"],
            "auto_enable_env": ["AUTO_PROMPT_TEST"],
        },
    )
    hermes_home = tmp_path / "home"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_BUNDLED_PLUGINS", str(bundled))
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("AUTO_PROMPT_TEST", "true")

    manager = PluginManager()
    manager.discover_and_load()

    loaded = manager._plugins["auto_prompt_env"]
    assert loaded.enabled is True
    assert "pre_llm_call" in loaded.hooks_registered


def test_bundled_plugin_auto_enables_from_manifest_config_gate(tmp_path, monkeypatch):
    from hermes_cli.plugins import PluginManager

    bundled = tmp_path / "bundled"
    _write_hook_plugin(
        bundled,
        manifest={
            "name": "auto_prompt_config",
            "hooks": ["pre_llm_call"],
            "auto_enable_config": ["auto_prompt.enabled"],
        },
    )
    hermes_home = tmp_path / "home"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        yaml.safe_dump({"auto_prompt": {"enabled": True}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_BUNDLED_PLUGINS", str(bundled))
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    manager = PluginManager()
    manager.discover_and_load()

    loaded = manager._plugins["auto_prompt_config"]
    assert loaded.enabled is True
    assert "pre_llm_call" in loaded.hooks_registered
