from types import SimpleNamespace

from gateway.config import GatewayConfig, Platform, PlatformConfig, _apply_env_overrides


def test_plugin_enable_pass_respects_explicit_disabled_platform(monkeypatch):
    """A plugin dependency check must not override platforms.<name>.enabled=false."""

    from gateway import platform_registry
    from hermes_cli import plugins

    fake_entry = SimpleNamespace(
        name="discord",
        check_fn=lambda: True,
        env_enablement_fn=None,
    )

    monkeypatch.setattr(plugins, "discover_plugins", lambda: None)
    monkeypatch.setattr(platform_registry.platform_registry, "plugin_entries", lambda: [fake_entry])
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DISCORD_HOME_CHANNEL", raising=False)
    monkeypatch.delenv("DISCORD_REPLY_TO_MODE", raising=False)

    config = GatewayConfig(
        platforms={
            Platform.DISCORD: PlatformConfig(
                enabled=False,
                extra={"_enabled_explicit": True},
            )
        }
    )

    _apply_env_overrides(config)

    assert config.platforms[Platform.DISCORD].enabled is False
