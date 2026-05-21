from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from gateway.config import Platform
from gateway.platform_registry import PlatformEntry, platform_registry
from gateway.run import GatewayRunner
from tests.gateway._plugin_adapter_loader import load_plugin_adapter


_whatsapp_plugin = load_plugin_adapter("whatsapp")


@pytest.fixture
def clean_registry():
    original = dict(platform_registry._entries)
    platform_registry._entries.clear()
    yield
    platform_registry._entries.clear()
    platform_registry._entries.update(original)


def _make_runner() -> GatewayRunner:
    runner = GatewayRunner.__new__(GatewayRunner)
    runner.config = SimpleNamespace(
        group_sessions_per_user=False,
        thread_sessions_per_user=False,
    )
    return runner


def _make_platform_config():
    return SimpleNamespace(extra={}, enabled=True, token=None, api_key=None)


def test_whatsapp_plugin_registers_canonical_override_name(clean_registry):
    class _Ctx:
        def register_platform(self, **kwargs):
            platform_registry.register(PlatformEntry(source="plugin", **kwargs))

    _whatsapp_plugin.register(_Ctx())

    entry = platform_registry.get("whatsapp")
    assert entry is not None
    assert entry.name == "whatsapp"
    assert entry.label == "WhatsApp"


def test_create_adapter_prefers_registered_whatsapp_plugin_override(clean_registry):
    sentinel = object()
    platform_registry.register(
        PlatformEntry(
            name="whatsapp",
            label="WhatsApp Override",
            adapter_factory=lambda cfg: sentinel,
            check_fn=lambda: True,
            source="plugin",
        )
    )

    runner = _make_runner()
    config = _make_platform_config()

    with patch("gateway.platforms.whatsapp.WhatsAppAdapter", side_effect=AssertionError("built-in fallback should not run")):
        adapter = runner._create_adapter(Platform.WHATSAPP, config)

    assert adapter is sentinel


def test_create_adapter_falls_back_to_builtin_whatsapp_when_no_registry_entry(clean_registry):
    runner = _make_runner()
    config = _make_platform_config()
    sentinel = object()

    with patch("gateway.platforms.whatsapp.check_whatsapp_requirements", return_value=True), patch(
        "gateway.platforms.whatsapp.WhatsAppAdapter",
        return_value=sentinel,
    ) as mock_builtin:
        adapter = runner._create_adapter(Platform.WHATSAPP, config)

    assert adapter is sentinel
    mock_builtin.assert_called_once_with(config)


def test_create_adapter_returns_none_when_registered_override_cannot_instantiate(clean_registry):
    platform_registry.register(
        PlatformEntry(
            name="whatsapp",
            label="Broken WhatsApp Override",
            adapter_factory=lambda cfg: (_ for _ in ()).throw(RuntimeError("boom")),
            check_fn=lambda: True,
            source="plugin",
        )
    )

    runner = _make_runner()
    config = _make_platform_config()

    with patch("gateway.platforms.whatsapp.WhatsAppAdapter", side_effect=AssertionError("built-in fallback should stay disabled after override failure")):
        adapter = runner._create_adapter(Platform.WHATSAPP, config)

    assert adapter is None


def test_bridge_health_scaffold_uses_local_default_port():
    assert _whatsapp_plugin.bridge_base_url() == "http://127.0.0.1:3000"
    assert _whatsapp_plugin.bridge_health_url() == "http://127.0.0.1:3000/health"
    assert _whatsapp_plugin.local_bridge_healthcheck_command() == "curl http://127.0.0.1:3000/health"


def test_bridge_health_scaffold_uses_configured_port():
    config = SimpleNamespace(extra={"bridge_port": 4123})

    assert _whatsapp_plugin.bridge_health_url(config) == "http://127.0.0.1:4123/health"
    assert _whatsapp_plugin.local_bridge_healthcheck_command(config) == "curl http://127.0.0.1:4123/health"


def test_plugin_adapter_wraps_builtin_whatsapp_adapter():
    config = SimpleNamespace(
        extra={},
        enabled=True,
        token=None,
        api_key=None,
        home_channel=None,
        reply_to_mode="first",
    )

    adapter = _whatsapp_plugin.WhatsAppPluginAdapter(config)

    from gateway.platforms.whatsapp import WhatsAppAdapter

    assert isinstance(adapter, WhatsAppAdapter)
    assert adapter.plugin_bridge_health_url == "http://127.0.0.1:3000/health"
