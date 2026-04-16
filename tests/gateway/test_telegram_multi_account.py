import pytest
from unittest.mock import AsyncMock, patch

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.run import GatewayRunner


class _FakeTelegramAdapter:
    def __init__(self, config):
        self.config = config
        self.platform = Platform.TELEGRAM
        self.name = "telegram"
        self.account_id = getattr(config, "account_id", None)
        self.has_fatal_error = False
        self.fatal_error_retryable = False
        self.fatal_error_code = None
        self.fatal_error_message = None

    def set_message_handler(self, handler):
        self._message_handler = handler

    def set_fatal_error_handler(self, handler):
        self._fatal_handler = handler

    def set_session_store(self, store):
        self._session_store = store

    def set_busy_session_handler(self, handler):
        self._busy_handler = handler

    async def connect(self):
        return True


class _FakeHooks:
    loaded_hooks = []

    def discover_and_load(self):
        return None

    async def emit(self, *_args, **_kwargs):
        return None


class _FakeDeliveryRouter:
    def __init__(self):
        self.adapters = {}


def _make_runner(config):
    runner = object.__new__(GatewayRunner)
    runner.config = config
    runner.adapters = {}
    runner.delivery_router = _FakeDeliveryRouter()
    runner.session_store = object()
    runner.hooks = _FakeHooks()
    runner._failed_platforms = {}
    runner._running = False
    runner._restart_requested = False
    runner._exit_reason = None
    runner._sync_voice_mode_state_to_adapter = lambda adapter: None
    runner._update_platform_runtime_status = lambda *args, **kwargs: None
    runner._update_runtime_status = lambda *args, **kwargs: None
    runner._handle_message = lambda *args, **kwargs: None
    runner._handle_adapter_fatal_error = lambda *args, **kwargs: None
    runner._handle_active_session_busy_message = lambda *args, **kwargs: None
    runner._increment_restart_failure_counts = lambda *args, **kwargs: None
    runner._send_update_notification = AsyncMock(return_value=False)
    runner._schedule_update_notification_watch = lambda *args, **kwargs: None
    runner._send_restart_notification = AsyncMock(return_value=None)
    runner._suspend_stuck_loop_sessions = lambda *args, **kwargs: 0
    return runner


def test_create_adapter_sets_account_id_and_name_for_telegram():
    runner = _make_runner(GatewayConfig())
    config = PlatformConfig(enabled=True, token="tok", account_id="devteam")

    with patch("gateway.run.check_telegram_requirements", return_value=True, create=True), \
         patch("gateway.platforms.telegram.check_telegram_requirements", return_value=True), \
         patch("gateway.platforms.telegram.TelegramAdapter", _FakeTelegramAdapter):
        adapter = runner._create_adapter(Platform.TELEGRAM, config)

    assert adapter is not None
    assert adapter.account_id == "devteam"
    assert adapter.name == "telegram[devteam]"


@pytest.mark.asyncio
async def test_start_connects_primary_and_extra_telegram_accounts():
    cfg = GatewayConfig(platforms={
        Platform.TELEGRAM: PlatformConfig(
            enabled=True,
            token="primary-token",
            extra={
                "telegram_accounts": {
                    "devteam": {"enabled": True, "token": "dev-token"},
                    "alerts": {"enabled": True, "token": "alerts-token"},
                }
            },
        )
    })
    runner = _make_runner(cfg)

    with patch.object(GatewayRunner, "_create_adapter", side_effect=lambda platform, config: _FakeTelegramAdapter(config)), \
         patch("gateway.channel_directory.build_channel_directory", return_value={"platforms": {}}), \
         patch.object(GatewayRunner, "_session_expiry_watcher", return_value=None), \
         patch.object(GatewayRunner, "_platform_reconnect_watcher", return_value=None):
        result = await GatewayRunner.start(runner)

    assert result is True
    assert set(runner.adapters.keys()) == {"telegram", "telegram[alerts]", "telegram[devteam]"}
    assert runner.adapters["telegram"].config.token == "primary-token"
    assert runner.adapters["telegram[devteam]"].config.account_id == "devteam"
    assert runner.adapters["telegram[alerts]"].config.account_id == "alerts"
