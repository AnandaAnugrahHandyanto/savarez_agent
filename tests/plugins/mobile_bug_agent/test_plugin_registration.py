from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import yaml

import plugins.mobile_bug_agent as monica_plugin
from gateway.config import Platform
from plugins.mobile_bug_agent import register
from plugins.mobile_bug_agent.config import MonicaConfig, SlackConfig

SAFE_RUNTIME_UNAVAILABLE_TEXT = (
    "Monica could not start because her runtime is not configured correctly. "
    "Run `hermes mobile-bug-agent doctor` on the host for details."
)


class FakeContext:
    def __init__(self) -> None:
        self.cli_commands: list[dict] = []
        self.hooks: list[str] = []

    def register_cli_command(self, **kwargs):
        self.cli_commands.append(kwargs)

    def register_hook(self, name, fn):
        self.hooks.append(name)


def test_plugin_registers_cli_and_gateway_hook():
    ctx = FakeContext()

    register(ctx)

    assert [cmd["name"] for cmd in ctx.cli_commands] == ["mobile-bug-agent"]
    assert ctx.cli_commands[0]["help"] == "Inspect and operate Monica mobile bug loops"
    assert ctx.hooks == ["pre_gateway_dispatch"]


def test_plugin_manifest_points_to_operator_docs():
    manifest_path = Path(__file__).resolve().parents[3] / "plugins" / "mobile_bug_agent" / "plugin.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    assert "docs/monica-agent.md" in manifest["description"]


def test_bundled_plugin_loads_when_enabled(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes_home"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        yaml.safe_dump({"plugins": {"enabled": ["mobile-bug-agent"]}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    from hermes_cli.plugins import PluginManager

    manager = PluginManager()
    manager.discover_and_load()

    loaded = manager._plugins["mobile-bug-agent"]
    assert loaded.enabled
    assert loaded.manifest.source == "bundled"
    assert "pre_gateway_dispatch" in loaded.hooks_registered
    assert "mobile-bug-agent" in manager._cli_commands


def test_bundled_plugin_is_opt_in(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes_home"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        yaml.safe_dump({"plugins": {"enabled": []}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    from hermes_cli.plugins import PluginManager

    manager = PluginManager()
    manager.discover_and_load()

    loaded = manager._plugins["mobile-bug-agent"]
    assert not loaded.enabled
    assert "not enabled" in str(loaded.error)


def test_pre_gateway_dispatch_reports_runtime_bootstrap_failure(monkeypatch):
    monica_plugin._runtime.cache_clear()
    monkeypatch.setattr(monica_plugin, "load_monica_config", lambda: MonicaConfig(enabled=True))
    monkeypatch.setattr(
        monica_plugin,
        "runtime_root",
        lambda config: (_ for _ in ()).throw(ValueError("bad Monica runtime root")),
    )
    event = SimpleNamespace(
        source=SimpleNamespace(platform=Platform.SLACK),
        raw_message={"type": "app_mention", "text": "<@U_MONICA> checkout crash"},
    )

    try:
        result = monica_plugin._on_pre_gateway_dispatch(event)
    finally:
        monica_plugin._runtime.cache_clear()

    assert result == {
        "action": "skip_reply",
        "reason": "monica_runtime_unavailable",
        "text": SAFE_RUNTIME_UNAVAILABLE_TEXT,
    }


def test_pre_gateway_dispatch_runtime_failure_does_not_leak_raw_exception_details(monkeypatch):
    monica_plugin._runtime.cache_clear()
    monkeypatch.setattr(monica_plugin, "load_monica_config", lambda: MonicaConfig(enabled=True))
    monkeypatch.setattr(
        monica_plugin,
        "runtime_root",
        lambda config: (_ for _ in ()).throw(ValueError("/Users/ritik/.hermes/secrets")),
    )
    event = SimpleNamespace(
        source=SimpleNamespace(platform=Platform.SLACK),
        raw_message={"type": "app_mention", "text": "<@U_MONICA> checkout crash"},
    )

    try:
        result = monica_plugin._on_pre_gateway_dispatch(event)
    finally:
        monica_plugin._runtime.cache_clear()

    assert result is not None
    assert result["action"] == "skip_reply"
    assert result["reason"] == "monica_runtime_unavailable"
    assert result["text"] == SAFE_RUNTIME_UNAVAILABLE_TEXT
    assert "/Users/ritik/.hermes/secrets" not in result["text"]


def test_pre_gateway_dispatch_runtime_failure_catches_configured_message_mention(monkeypatch):
    monica_plugin._runtime.cache_clear()
    monkeypatch.setattr(
        monica_plugin,
        "load_monica_config",
        lambda: MonicaConfig(enabled=True, slack=SlackConfig(bot_user_ids=("U_MONICA",))),
    )
    monkeypatch.setattr(
        monica_plugin,
        "runtime_root",
        lambda config: (_ for _ in ()).throw(ValueError("bad Monica runtime root")),
    )
    event = SimpleNamespace(
        source=SimpleNamespace(platform=Platform.SLACK),
        raw_message={"type": "message", "text": "<@U_MONICA> checkout crash"},
    )

    try:
        result = monica_plugin._on_pre_gateway_dispatch(event)
    finally:
        monica_plugin._runtime.cache_clear()

    assert result == {
        "action": "skip_reply",
        "reason": "monica_runtime_unavailable",
        "text": SAFE_RUNTIME_UNAVAILABLE_TEXT,
    }


def test_pre_gateway_dispatch_runtime_failure_ignores_other_app_mentions_when_configured(
    monkeypatch,
):
    monica_plugin._runtime.cache_clear()
    monkeypatch.setattr(
        monica_plugin,
        "load_monica_config",
        lambda: MonicaConfig(enabled=True, slack=SlackConfig(bot_user_ids=("U_MONICA",))),
    )
    monkeypatch.setattr(
        monica_plugin,
        "runtime_root",
        lambda config: (_ for _ in ()).throw(ValueError("bad Monica runtime root")),
    )
    event = SimpleNamespace(
        source=SimpleNamespace(platform=Platform.SLACK),
        raw_message={"type": "app_mention", "text": "<@U_CHANDLER> checkout crash"},
    )

    try:
        result = monica_plugin._on_pre_gateway_dispatch(event)
    finally:
        monica_plugin._runtime.cache_clear()

    assert result is None


def test_pre_gateway_dispatch_runtime_failure_catches_punctuated_message_mention(monkeypatch):
    monica_plugin._runtime.cache_clear()
    monkeypatch.setattr(
        monica_plugin,
        "load_monica_config",
        lambda: MonicaConfig(enabled=True, slack=SlackConfig(bot_user_ids=("U_MONICA",))),
    )
    monkeypatch.setattr(
        monica_plugin,
        "runtime_root",
        lambda config: (_ for _ in ()).throw(ValueError("bad Monica runtime root")),
    )
    event = SimpleNamespace(
        source=SimpleNamespace(platform=Platform.SLACK),
        raw_message={"type": "message", "text": "<@U_MONICA>, checkout crash"},
    )

    try:
        result = monica_plugin._on_pre_gateway_dispatch(event)
    finally:
        monica_plugin._runtime.cache_clear()

    assert result == {
        "action": "skip_reply",
        "reason": "monica_runtime_unavailable",
        "text": SAFE_RUNTIME_UNAVAILABLE_TEXT,
    }


def test_pre_gateway_dispatch_runtime_failure_catches_direct_message(monkeypatch):
    monica_plugin._runtime.cache_clear()
    monkeypatch.setattr(monica_plugin, "load_monica_config", lambda: MonicaConfig(enabled=True))
    monkeypatch.setattr(
        monica_plugin,
        "runtime_root",
        lambda config: (_ for _ in ()).throw(ValueError("bad Monica runtime root")),
    )
    event = SimpleNamespace(
        source=SimpleNamespace(platform=Platform.SLACK, chat_id="D_MONICA", chat_type="dm"),
        raw_message={
            "type": "message",
            "channel_type": "im",
            "text": "checkout crash",
        },
    )

    try:
        result = monica_plugin._on_pre_gateway_dispatch(event)
    finally:
        monica_plugin._runtime.cache_clear()

    assert result == {
        "action": "skip_reply",
        "reason": "monica_runtime_unavailable",
        "text": SAFE_RUNTIME_UNAVAILABLE_TEXT,
    }


def test_pre_gateway_dispatch_runtime_failure_ignores_group_dm_without_mention(monkeypatch):
    monica_plugin._runtime.cache_clear()
    monkeypatch.setattr(monica_plugin, "load_monica_config", lambda: MonicaConfig(enabled=True))
    monkeypatch.setattr(
        monica_plugin,
        "runtime_root",
        lambda config: (_ for _ in ()).throw(ValueError("bad Monica runtime root")),
    )
    event = SimpleNamespace(
        source=SimpleNamespace(platform=Platform.SLACK, chat_id="G_MONICA", chat_type="dm"),
        raw_message={
            "type": "message",
            "channel_type": "mpim",
            "text": "checkout crash",
        },
    )

    try:
        result = monica_plugin._on_pre_gateway_dispatch(event)
    finally:
        monica_plugin._runtime.cache_clear()

    assert result is None
