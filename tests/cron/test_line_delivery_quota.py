"""LINE cron delivery quota guard tests."""

from __future__ import annotations


class _FakeLoop:
    def is_running(self):
        return True


class _FakeFuture:
    def __init__(self, result):
        self._result = result
        self.cancelled = False

    def result(self, timeout=None):
        return self._result

    def cancel(self):
        self.cancelled = True


class _QuotaFailingLineAdapter:
    async def send(self, chat_id, content, reply_to=None, metadata=None):
        from gateway.platforms.base import SendResult

        return SendResult(
            success=False,
            error="LINE push quota exhausted; not retrying automatically",
            retryable=False,
        )


def test_line_cron_nonretryable_push_quota_failure_does_not_fallback_to_second_push(monkeypatch):
    """A live LINE quota failure must not fall back to standalone push.

    The standalone fallback is useful for transient adapter failures on other platforms,
    but for LINE monthly push quota exhaustion it would create a duplicate failed push
    attempt now and a retry pile later.
    """
    from cron import scheduler as sched_mod
    from gateway.config import GatewayConfig, Platform, PlatformConfig
    from gateway.platforms.base import SendResult
    import gateway.config as gateway_config
    import tools.send_message_tool as send_message_tool

    line_platform = Platform("line")
    gateway_cfg = GatewayConfig(
        platforms={
            line_platform: PlatformConfig(
                enabled=True,
                extra={"channel_access_token": "unit-test-token", "channel_secret": "unit-test-secret"},
            )
        }
    )
    monkeypatch.setattr(sched_mod, "load_config", lambda: {"cron": {"wrap_response": False}})
    monkeypatch.setattr(gateway_config, "load_gateway_config", lambda: gateway_cfg)

    standalone_calls = []

    async def fake_send_to_platform(*args, **kwargs):
        standalone_calls.append((args, kwargs))
        return {"success": True, "message_id": "standalone-push"}

    monkeypatch.setattr(send_message_tool, "_send_to_platform", fake_send_to_platform)

    def fake_run_coroutine_threadsafe(coro, loop):
        coro.close()
        return _FakeFuture(
            SendResult(
                success=False,
                error="LINE push quota exhausted; not retrying automatically",
                retryable=False,
            )
        )

    monkeypatch.setattr(sched_mod.asyncio, "run_coroutine_threadsafe", fake_run_coroutine_threadsafe)

    err = sched_mod._deliver_result(
        {
            "id": "job-line-quota",
            "name": "parent reminder",
            "deliver": "line:Uparent",
        },
        "reminder body",
        adapters={line_platform: _QuotaFailingLineAdapter()},
        loop=_FakeLoop(),
    )

    assert err is not None
    assert "quota" in err.lower()
    assert standalone_calls == []
