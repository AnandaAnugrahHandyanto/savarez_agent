import pytest

from gateway.config import Platform, PlatformConfig


def _make_adapter(monkeypatch, **extra):
    monkeypatch.setenv('BLUEBUBBLES_SERVER_URL', 'http://localhost:1234')
    monkeypatch.setenv('BLUEBUBBLES_PASSWORD', 'secret')
    from gateway.platforms.bluebubbles import BlueBubblesAdapter
    cfg = PlatformConfig(enabled=True, extra={
        'server_url': 'http://localhost:1234',
        'password': 'secret',
        **extra,
    })
    return BlueBubblesAdapter(cfg)


class TestBlueBubblesPlatformEnum:
    def test_bluebubbles_enum_exists(self):
        assert Platform.BLUEBUBBLES.value == 'bluebubbles'


class TestBlueBubblesConfigLoading:
    def test_apply_env_overrides_bluebubbles(self, monkeypatch):
        monkeypatch.setenv('BLUEBUBBLES_SERVER_URL', 'http://localhost:1234')
        monkeypatch.setenv('BLUEBUBBLES_PASSWORD', 'secret')
        monkeypatch.setenv('BLUEBUBBLES_WEBHOOK_PORT', '9999')
        from gateway.config import GatewayConfig, _apply_env_overrides
        config = GatewayConfig()
        _apply_env_overrides(config)
        assert Platform.BLUEBUBBLES in config.platforms
        bc = config.platforms[Platform.BLUEBUBBLES]
        assert bc.enabled is True
        assert bc.extra['server_url'] == 'http://localhost:1234'
        assert bc.extra['password'] == 'secret'
        assert bc.extra['webhook_port'] == 9999

    def test_connected_platforms_includes_bluebubbles(self, monkeypatch):
        monkeypatch.setenv('BLUEBUBBLES_SERVER_URL', 'http://localhost:1234')
        monkeypatch.setenv('BLUEBUBBLES_PASSWORD', 'secret')
        from gateway.config import GatewayConfig, _apply_env_overrides
        config = GatewayConfig()
        _apply_env_overrides(config)
        assert Platform.BLUEBUBBLES in config.get_connected_platforms()


class TestBlueBubblesHelpers:
    def test_check_requirements(self, monkeypatch):
        monkeypatch.setenv('BLUEBUBBLES_SERVER_URL', 'http://localhost:1234')
        monkeypatch.setenv('BLUEBUBBLES_PASSWORD', 'secret')
        from gateway.platforms.bluebubbles import check_bluebubbles_requirements
        assert check_bluebubbles_requirements() is True

    def test_format_message_strips_markdown(self, monkeypatch):
        adapter = _make_adapter(monkeypatch)
        assert adapter.format_message('**Hello** `world`') == 'Hello world'

    def test_init_normalizes_webhook_path(self, monkeypatch):
        adapter = _make_adapter(monkeypatch, webhook_path='bluebubbles-webhook')
        assert adapter.webhook_path == '/bluebubbles-webhook'
