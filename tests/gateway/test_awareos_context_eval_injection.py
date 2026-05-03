import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent
from gateway.run import GatewayRunner
from gateway.session import SessionSource


def _make_runner(config: GatewayConfig) -> GatewayRunner:
    runner = object.__new__(GatewayRunner)
    runner.config = config
    runner.adapters = {}
    runner._model = "openai/gpt-4.1-mini"
    runner._base_url = None
    runner._awareos_last_context_eval_ts = {}
    return runner


@pytest.mark.asyncio
async def test_context_eval_injects_on_calendar_prompt(monkeypatch):
    monkeypatch.setenv("AWAREOS_CONTEXT_EVAL_ENABLED", "1")
    monkeypatch.setenv("AWAREOS_CONTEXT_EVAL_URL", "http://example.invalid/eval")

    from gateway import awareos_bridge as ab

    class _Res:
        ok = True
        snippet = "calendar: none"
        meta = {}

    monkeypatch.setattr(ab, "run_context_eval", lambda **_: _Res())

    runner = _make_runner(
        GatewayConfig(
            platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="fake")},
        )
    )
    source = SessionSource(platform=Platform.TELEGRAM, chat_id="1", chat_type="dm", user_id="u")
    event = MessageEvent(text="What's on my calendar tomorrow?", source=source)
    out = await runner._prepare_inbound_message_text(event=event, source=source, history=[])
    assert out.startswith("[AwareOS context evaluator]\ncalendar: none\n\n")


@pytest.mark.asyncio
async def test_context_eval_debounces_per_session(monkeypatch):
    monkeypatch.setenv("AWAREOS_CONTEXT_EVAL_ENABLED", "1")
    monkeypatch.setenv("AWAREOS_CONTEXT_EVAL_URL", "http://example.invalid/eval")
    monkeypatch.setenv("AWAREOS_CONTEXT_EVAL_DEBOUNCE_SECS", "9999")

    from gateway import awareos_bridge as ab

    calls = {"n": 0}

    class _Res:
        ok = True
        snippet = "ok"
        meta = {}

    def _fake(**_):
        calls["n"] += 1
        return _Res()

    monkeypatch.setattr(ab, "run_context_eval", _fake)

    runner = _make_runner(
        GatewayConfig(
            platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="fake")},
        )
    )
    source = SessionSource(platform=Platform.TELEGRAM, chat_id="1", chat_type="dm", user_id="u")
    event = MessageEvent(text="calendar today", source=source)
    out1 = await runner._prepare_inbound_message_text(event=event, source=source, history=[])
    out2 = await runner._prepare_inbound_message_text(event=event, source=source, history=[])
    assert calls["n"] == 1
    assert out1.startswith("[AwareOS context evaluator]\n")
    assert out2 == "calendar today"


@pytest.mark.asyncio
async def test_context_eval_skips_slash_commands(monkeypatch):
    monkeypatch.setenv("AWAREOS_CONTEXT_EVAL_ENABLED", "1")
    monkeypatch.setenv("AWAREOS_CONTEXT_EVAL_URL", "http://example.invalid/eval")

    from gateway import awareos_bridge as ab

    monkeypatch.setattr(ab, "run_context_eval", lambda **_: (_ for _ in ()).throw(AssertionError("should not call")))

    runner = _make_runner(
        GatewayConfig(
            platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="fake")},
        )
    )
    source = SessionSource(platform=Platform.TELEGRAM, chat_id="1", chat_type="dm", user_id="u")
    event = MessageEvent(text="/help", source=source)
    out = await runner._prepare_inbound_message_text(event=event, source=source, history=[])
    assert out == "/help"
