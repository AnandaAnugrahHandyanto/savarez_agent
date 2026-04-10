"""Tests for the WeChat (Weixin) gateway integration."""

from gateway.config import Platform


class TestWeixinPlatformEnum:
    def test_weixin_enum_exists_without_regressing_bluebubbles(self):
        assert Platform.WEIXIN.value == "weixin"
        assert Platform.BLUEBUBBLES.value == "bluebubbles"


class TestWeixinConfigLoading:
    def test_apply_env_overrides_weixin(self, monkeypatch):
        monkeypatch.setenv("WEIXIN_TOKEN", "token-123")
        monkeypatch.setenv("WEIXIN_ACCOUNT_ID", "acct-456")
        monkeypatch.setenv("WEIXIN_BASE_URL", "https://example.invalid")
        monkeypatch.setenv("WEIXIN_CDN_BASE_URL", "https://cdn.example.invalid")

        from gateway.config import GatewayConfig, _apply_env_overrides

        config = GatewayConfig()
        _apply_env_overrides(config)

        assert Platform.WEIXIN in config.platforms
        wc = config.platforms[Platform.WEIXIN]
        assert wc.enabled is True
        assert wc.token == "token-123"
        assert wc.extra["account_id"] == "acct-456"
        assert wc.extra["base_url"] == "https://example.invalid"
        assert wc.extra["cdn_base_url"] == "https://cdn.example.invalid"

    def test_connected_platforms_requires_account_id(self, monkeypatch):
        monkeypatch.setenv("WEIXIN_TOKEN", "token-123")
        monkeypatch.delenv("WEIXIN_ACCOUNT_ID", raising=False)

        from gateway.config import GatewayConfig, _apply_env_overrides

        config = GatewayConfig()
        _apply_env_overrides(config)

        assert Platform.WEIXIN not in config.get_connected_platforms()

    def test_connected_platforms_includes_weixin(self, monkeypatch):
        monkeypatch.setenv("WEIXIN_TOKEN", "token-123")
        monkeypatch.setenv("WEIXIN_ACCOUNT_ID", "acct-456")

        from gateway.config import GatewayConfig, _apply_env_overrides

        config = GatewayConfig()
        _apply_env_overrides(config)

        assert Platform.WEIXIN in config.get_connected_platforms()

    def test_home_channel_set_from_env(self, monkeypatch):
        monkeypatch.setenv("WEIXIN_TOKEN", "token-123")
        monkeypatch.setenv("WEIXIN_ACCOUNT_ID", "acct-456")
        monkeypatch.setenv("WEIXIN_HOME_CHANNEL", "wx-user-789")

        from gateway.config import GatewayConfig, _apply_env_overrides

        config = GatewayConfig()
        _apply_env_overrides(config)

        hc = config.platforms[Platform.WEIXIN].home_channel
        assert hc is not None
        assert hc.chat_id == "wx-user-789"


class TestWeixinToolsetIntegration:
    def test_toolset_exists(self):
        from toolsets import TOOLSETS

        assert "hermes-weixin" in TOOLSETS

    def test_toolset_in_gateway_composite(self):
        from toolsets import TOOLSETS

        gateway = TOOLSETS["hermes-gateway"]
        assert "hermes-weixin" in gateway["includes"]


class TestWeixinPromptHint:
    def test_platform_hint_exists(self):
        from agent.prompt_builder import PLATFORM_HINTS

        assert "weixin" in PLATFORM_HINTS
        hint = PLATFORM_HINTS["weixin"]
        assert "WeChat" in hint
        assert "plain text" in hint
